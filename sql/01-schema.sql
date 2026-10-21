-- Support chatbot: database setup for Supabase (Postgres + pgvector)
-- Solvant Labs demo build. Run once in the Supabase SQL editor; safe to run again.
--
-- What it creates
--   documents       knowledge base chunks with embeddings (the shape n8n's Supabase Vector Store expects)
--   kb_files        one row per help article, so the sync only re-embeds articles that changed
--   bot_settings    the system prompt, escalation rules and reply texts, editable in the Table Editor
--   conversations   one row per chat: channel, status, contact details, issue type, handoff
--   messages        every customer message and assistant reply, with sources and scores
--   functions       match_documents, register_message, log_reply, claim_handoff
--
-- Access: row level security is on for every table and no policies are added, so the public
-- (anon) key can read nothing. n8n connects with the project's secret key, which bypasses RLS.

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Knowledge base
-- ---------------------------------------------------------------------------

create table if not exists public.documents (
  id         bigserial primary key,
  content    text,
  metadata   jsonb,
  embedding  extensions.vector(1536),
  file_id    text generated always as (metadata ->> 'file_id') stored,
  created_at timestamptz not null default now()
);

create index if not exists documents_file_id_idx on public.documents (file_id);
create index if not exists documents_embedding_idx
  on public.documents using hnsw (embedding extensions.vector_cosine_ops);

-- Called by n8n's Supabase Vector Store node (LangChain signature). Returns cosine similarity.
create or replace function public.match_documents (
  query_embedding extensions.vector(1536),
  match_count     int default null,
  filter          jsonb default '{}'
) returns table (id bigint, content text, metadata jsonb, similarity float)
language plpgsql
set search_path = public, extensions
as $$
begin
  return query
  select d.id, d.content, d.metadata,
         (1 - (d.embedding <=> query_embedding))::float as similarity
  from public.documents d
  where d.metadata @> filter
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;

create table if not exists public.kb_files (
  file_id       text primary key,
  title         text not null,
  url           text,
  modified_time timestamptz,
  content_hash  text,
  chunk_count   int not null default 0,
  synced_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Settings: prompt, escalation rules and reply texts (seeded by 02-settings.sql)
-- ---------------------------------------------------------------------------

create table if not exists public.bot_settings (
  key         text primary key,
  value       text not null,
  description text,
  updated_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Conversations and messages
-- ---------------------------------------------------------------------------

create table if not exists public.conversations (
  session_id         text primary key,
  channel            text not null,                       -- web | whatsapp | test
  status             text not null default 'bot'
                     check (status in ('bot', 'collecting_contact', 'handed_off')),
  pending_reason     text,                                -- why a handoff is waiting for contact details
  contact_asks       int  not null default 0,
  handoff_reason     text,                                -- asked_for_person | frustrated | outside_kb
  handoff_at         timestamptz,
  slack_ts           text,                                -- Slack message of the handoff, for follow-ups
  contact_name       text,
  contact_email      text,
  contact_phone      text,
  issue_type         text,
  last_answer_status text,
  not_sure_count     int  not null default 0,
  message_count      int  not null default 0,             -- customer messages, all time
  window_count       int  not null default 0,             -- customer messages in the current window
  window_started_at  timestamptz not null default now(),
  first_question     text,
  is_test            boolean not null default false,
  started_at         timestamptz not null default now(),
  last_message_at    timestamptz not null default now()
);

create table if not exists public.messages (
  id             bigserial primary key,
  session_id     text not null references public.conversations (session_id) on delete cascade,
  role           text not null check (role in ('user', 'assistant')),
  content        text not null,
  external_id    text unique,                             -- WhatsApp message id, for duplicate deliveries
  answer_status  text,
  sources        jsonb,
  best_score     real,
  flags          jsonb,
  model          text,
  prompt_version text,
  tokens_in      int,
  tokens_out     int,
  latency_ms     int,
  created_at     timestamptz not null default now()
);

create index if not exists messages_session_idx on public.messages (session_id, id);
create index if not exists messages_created_idx on public.messages (created_at);

-- ---------------------------------------------------------------------------
-- register_message: called first for every customer message.
-- Creates or updates the conversation, applies the message caps, stores the message and
-- returns the conversation, recent history and all settings in one round trip.
-- ---------------------------------------------------------------------------

create or replace function public.register_message (
  p_session_id    text,
  p_channel       text,
  p_text          text,
  p_is_test       boolean default false,
  p_contact_phone text default null,
  p_contact_name  text default null,
  p_external_id   text default null
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_settings jsonb := coalesce((select jsonb_object_agg(key, value) from bot_settings), '{}'::jsonb);
  v_max      int := coalesce(nullif(v_settings ->> 'max_messages_per_chat', '')::int, 30);
  v_global   int := coalesce(nullif(v_settings ->> 'max_messages_per_day', '')::int, 300);
  v_window   int := coalesce(nullif(v_settings ->> 'session_window_hours', '')::int, 24);
  v_hist     int := coalesce(nullif(v_settings ->> 'history_messages', '')::int, 6);
  c          conversations%rowtype;
  v_reason   text := null;
  v_history  jsonb;
  v_prev     text;
  v_today    int;
begin
  if p_external_id is not null and exists (select 1 from messages where external_id = p_external_id) then
    return jsonb_build_object('duplicate', true, 'allowed', false);
  end if;

  insert into conversations (session_id, channel, is_test, contact_phone, contact_name, first_question)
  values (p_session_id, p_channel, p_is_test, p_contact_phone, p_contact_name, left(p_text, 300))
  on conflict (session_id) do nothing;

  select * into c from conversations where session_id = p_session_id for update;

  -- A long gap starts a new window: counters reset and an old handoff is closed.
  if c.last_message_at < now() - make_interval(hours => v_window) then
    update conversations
       set window_started_at = now(), window_count = 0, not_sure_count = 0,
           status = 'bot', pending_reason = null, contact_asks = 0
     where session_id = p_session_id;
  end if;

  update conversations
     set message_count   = message_count + 1,
         window_count    = window_count + 1,
         last_message_at = now(),
         contact_phone   = coalesce(contact_phone, p_contact_phone),
         contact_name    = coalesce(contact_name, p_contact_name)
   where session_id = p_session_id
  returning * into c;

  select count(*) into v_today
    from messages m join conversations x using (session_id)
   where m.role = 'user' and m.created_at > now() - interval '24 hours' and not x.is_test;

  if c.window_count > v_max then
    v_reason := 'chat_limit';
  elsif not p_is_test and v_today >= v_global then
    v_reason := 'daily_limit';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object('role', h.role, 'content', h.content) order by h.id), '[]'::jsonb)
    into v_history
    from (select id, role, content
            from messages
           where session_id = p_session_id
             and created_at > now() - make_interval(hours => v_window)
           order by id desc
           limit v_hist) h;

  select content into v_prev
    from messages
   where session_id = p_session_id and role = 'user'
     and created_at > now() - make_interval(hours => v_window)
   order by id desc
   limit 1;

  insert into messages (session_id, role, content, external_id)
  values (p_session_id, 'user', p_text, p_external_id);

  return jsonb_build_object(
    'duplicate', false,
    'allowed', v_reason is null,
    'limit_reason', v_reason,
    'conversation', to_jsonb(c),
    'history', v_history,
    'previous_user_message', v_prev,
    'settings', v_settings
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- log_reply: stores the assistant reply and the conversation changes decided by n8n.
-- Returns the updated conversation and a plain-text transcript for the Google Sheets log.
-- ---------------------------------------------------------------------------

create or replace function public.log_reply (
  p_session_id     text,
  p_reply          text,
  p_answer_status  text default null,
  p_sources        jsonb default null,
  p_best_score     real default null,
  p_flags          jsonb default null,
  p_model          text default null,
  p_prompt_version text default null,
  p_tokens_in      int default null,
  p_tokens_out     int default null,
  p_latency_ms     int default null,
  p_state          jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  c            conversations%rowtype;
  v_transcript text;
begin
  update conversations
     set status             = coalesce(nullif(p_state ->> 'status', ''), status),
         pending_reason     = case when p_state ? 'pending_reason' then p_state ->> 'pending_reason' else pending_reason end,
         contact_asks       = coalesce((p_state ->> 'contact_asks')::int, contact_asks),
         contact_name       = coalesce(nullif(p_state ->> 'contact_name', ''), contact_name),
         contact_email      = coalesce(nullif(p_state ->> 'contact_email', ''), contact_email),
         issue_type         = coalesce(nullif(p_state ->> 'issue_type', ''), issue_type),
         not_sure_count     = not_sure_count + coalesce((p_state ->> 'not_sure_inc')::int, 0),
         last_answer_status = coalesce(p_answer_status, last_answer_status)
   where session_id = p_session_id
  returning * into c;

  if not found then
    raise exception 'Unknown session %', p_session_id;
  end if;

  insert into messages (session_id, role, content, answer_status, sources, best_score, flags,
                        model, prompt_version, tokens_in, tokens_out, latency_ms)
  values (p_session_id, 'assistant', p_reply, p_answer_status, p_sources, p_best_score, p_flags,
          p_model, p_prompt_version, p_tokens_in, p_tokens_out, p_latency_ms);

  select string_agg(case when t.role = 'user' then 'Customer: ' else 'Assistant: ' end || t.content, E'\n' order by t.id)
    into v_transcript
    from (select id, role, content from messages where session_id = p_session_id order by id desc limit 20) t;

  return jsonb_build_object('conversation', to_jsonb(c), 'transcript_text', left(coalesce(v_transcript, ''), 45000));
end;
$$;

-- ---------------------------------------------------------------------------
-- claim_handoff: marks the conversation as handed off exactly once and returns the full
-- transcript. A second call for the same conversation returns claimed = false.
-- ---------------------------------------------------------------------------

create or replace function public.claim_handoff (
  p_session_id text,
  p_reason     text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  c            conversations%rowtype;
  v_claimed    boolean;
  v_transcript jsonb;
begin
  update conversations
     set status = 'handed_off', handoff_reason = p_reason, handoff_at = now(), pending_reason = null
   where session_id = p_session_id and status <> 'handed_off'
  returning * into c;
  v_claimed := found;

  if not v_claimed then
    select * into c from conversations where session_id = p_session_id;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object('role', role, 'content', content, 'at', created_at) order by id), '[]'::jsonb)
    into v_transcript
    from messages
   where session_id = p_session_id;

  return jsonb_build_object('claimed', v_claimed, 'conversation', to_jsonb(c), 'transcript', v_transcript);
end;
$$;

-- ---------------------------------------------------------------------------
-- A readable view of conversations for the Table Editor and screenshots
-- ---------------------------------------------------------------------------

create or replace view public.conversation_overview
with (security_invoker = true) as
select session_id, channel, status, handoff_reason, contact_name, contact_email, issue_type,
       message_count, not_sure_count, first_question, started_at, last_message_at, handoff_at, is_test
  from public.conversations
 order by last_message_at desc;

-- ---------------------------------------------------------------------------
-- Lock it down
-- ---------------------------------------------------------------------------

alter table public.documents     enable row level security;
alter table public.kb_files      enable row level security;
alter table public.bot_settings  enable row level security;
alter table public.conversations enable row level security;
alter table public.messages      enable row level security;

revoke all on table public.documents, public.kb_files, public.bot_settings,
                    public.conversations, public.messages, public.conversation_overview
  from anon, authenticated;

revoke execute on function public.match_documents(extensions.vector, int, jsonb) from public, anon, authenticated;
revoke execute on function public.register_message(text, text, text, boolean, text, text, text) from public, anon, authenticated;
revoke execute on function public.log_reply(text, text, text, jsonb, real, jsonb, text, text, int, int, int, jsonb) from public, anon, authenticated;
revoke execute on function public.claim_handoff(text, text) from public, anon, authenticated;

grant execute on function public.match_documents(extensions.vector, int, jsonb) to service_role;
grant execute on function public.register_message(text, text, text, boolean, text, text, text) to service_role;
grant execute on function public.log_reply(text, text, text, jsonb, real, jsonb, text, text, int, int, int, jsonb) to service_role;
grant execute on function public.claim_handoff(text, text) to service_role;
