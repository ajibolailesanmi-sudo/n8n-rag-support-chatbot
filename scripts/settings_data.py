"""Default rows for the bot_settings table.

One source of truth for sql/02-settings.sql, the docs and the test runner.
Account-specific values (emails, Slack channel, sheet and folder IDs) are placeholders here;
the live values are set once in Supabase after install (see docs/02-setup-guide.md).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYSTEM_PROMPT = (ROOT / "prompts" / "system-prompt.md").read_text().strip()

PROMPT_VERSION = "1.0"

# (key, value, description)
SETTINGS = [
    # Model and retrieval
    ("provider", "gemini", "Which API writes the replies: gemini (free tier) or openai. The workflow ships with the Gemini node; see docs/02-setup-guide.md for the OpenAI swap."),
    ("model", "gemini-3.5-flash-lite", "Model that writes the replies (a Gemini model name, or an OpenAI model name when provider is openai)."),
    ("embedding_model", "gemini-embedding-001", "Embedding model for the knowledge base and for searches. Changing it means a full re-embed (sync form, Re-embed every article)."),
    ("embedding_dimensions", "1536", "Length of the embedding vectors. Must match the documents table (vector(1536))."),
    ("chunk_size", "900", "Characters per knowledge base chunk. Changing it means a full re-embed."),
    ("chunk_overlap", "120", "Characters repeated from the previous chunk, so a fact split across two chunks is still found."),
    ("reasoning_effort", "", "OpenAI only: reasoning effort sent with the request. Leave empty for Gemini."),
    ("max_output_tokens", "1200", "Upper limit for the model's output."),
    ("top_k", "4", "Chunks retrieved per search. Two searches run per message (the message alone, and with the previous message)."),
    ("max_sources", "5", "Most chunks passed to the model as SOURCES after merging the two searches."),
    ("min_similarity", "0.30", "If the best match scores below this, an answer is not trusted and the reply becomes \"I'm not sure\"."),
    ("history_messages", "6", "How many earlier messages from the same chat the model sees (short conversation memory)."),
    ("number_check", "flag", "flag = log numbers in a reply that the cited articles do not contain; block = also replace the reply with \"I'm not sure\"; off = skip."),
    ("prompt_version", PROMPT_VERSION, "Label stored with every reply, so test results can be tied to a prompt version."),
    ("system_prompt", SYSTEM_PROMPT, "Instructions for the model. {{state}}, {{today}} and {{channel}} are filled in for each message."),

    # Escalation rules
    ("escalate_when_asked", "yes", "Hand off when the customer asks for a person (yes/no)."),
    ("escalate_when_frustrated", "high", "Hand off at this frustration level or above: mild, high, or off."),
    ("escalate_when_not_in_kb", "yes", "Hand off when a support question is not answered by the knowledge base (yes/no)."),
    ("handoff_keywords", "human, real person, a person, agent, representative, technician, call me, call me back, speak to someone, talk to someone",
     "Comma-separated phrases that count as asking for a person even if the model misses it."),
    ("max_contact_asks", "2", "How many times to ask for an email before handing off without one."),

    # Reply texts used by the escalation rules
    ("prefix_frustrated", "I'm sorry this has been frustrating. ", "Start of the handoff reply when the customer is frustrated."),
    ("prefix_outside_kb", "I'm not sure about that, and I don't want to guess. ", "Start of the handoff reply when the knowledge base has no answer."),
    ("ask_contact_text", "I can pass this to a member of our team. What's your name and the best email address to reach you?", "Asks for contact details before a handoff."),
    ("reask_email_text", "Could you share the best email address for the team to reach you?", "Asks again when no email address was given."),
    ("handoff_email_text", "I've passed our conversation to the team and someone will email you at {{email}}.", "Confirms a handoff when an email address is known."),
    ("handoff_phone_text", "I've passed our conversation to the team and someone will reply to you here.", "Confirms a handoff on WhatsApp, where the phone number is known."),
    ("handoff_no_contact_text", "I've passed our conversation to the team. You can also reach them through the client portal.", "Confirms a handoff when no email address was given."),
    ("already_handed_off_text", "The team already has our conversation and will be in touch. I've added your latest message for them.", "Reply when the chat was already handed off."),
    ("declined_text", "No problem, I won't pass it on. Is there anything else I can help with?", "Reply when the customer no longer wants a person."),
    ("not_sure_text", "I'm not sure about that, and I don't want to guess. You can ask the team through the client portal.", "Reply when the knowledge base has no answer and handoff for that case is off."),
    ("limit_text", "This demo chat has reached its message limit. Please try again tomorrow.", "Reply when a message cap is reached."),
    ("fallback_text", "Sorry, I'm having trouble answering right now. Please try again in a few minutes, or contact the help desk through the client portal.", "Reply when the model or the search fails."),

    # Limits for the public demo
    ("max_messages_per_chat", "30", "Customer messages allowed per chat in one window."),
    ("max_messages_per_day", "300", "Customer messages allowed across all chats in 24 hours (test chats excluded)."),
    ("session_window_hours", "24", "After this many quiet hours a chat starts fresh: counters reset and an old handoff is closed."),

    # Where handoffs and logs go (account-specific: placeholders until setup)
    ("slack_channel", "#chat-escalations", "Slack channel for handoffs. The n8n Slack app must be a member."),
    ("team_email", "support-team@example.com", "Address that receives handoff emails with the transcript."),
    ("from_email", "assistant@example.com", "Sender address for handoff emails (must match the SMTP account)."),
    ("sheet_id", "YOUR_GOOGLE_SHEET_ID", "Google Sheet that holds the conversation log (tab: conversations)."),
    ("drive_folder_id", "YOUR_DRIVE_FOLDER_ID", "Google Drive folder that holds the help articles as Google Docs."),
]

KEYS = [k for k, _, _ in SETTINGS]
assert len(KEYS) == len(set(KEYS)), "duplicate setting keys"


def as_dict():
    return {k: v for k, v, _ in SETTINGS}


def to_sql(overwrite=False):
    lines = [
        "-- Default settings for the support chatbot (generated by scripts/build_sql.py; edit there).",
        "-- Run after 01-schema.sql. Existing rows are kept, so your edits survive a re-run."
        if not overwrite else
        "-- Resets every setting to its default. Use only on a fresh install or to undo edits.",
        "",
    ]
    for key, value, desc in SETTINGS:
        tag = "$v$" if "$v$" not in value else "$val$"
        lines.append(
            f"insert into public.bot_settings (key, value, description) values ('{key}', {tag}{value}{tag}, $d${desc}$d$)"
        )
        if overwrite:
            lines.append("  on conflict (key) do update set value = excluded.value, description = excluded.description, updated_at = now();")
        else:
            lines.append("  on conflict (key) do nothing;")
    return "\n".join(lines) + "\n"
