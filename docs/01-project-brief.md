# Project brief: RAG support chatbot on n8n

Solvant Labs demo build, October 2026. Built to the requirements of a real Upwork job post ("AI Support Chatbot Developer: n8n + RAG Knowledge Base for WhatsApp & Website") for a sample managed IT services firm. The firm is fictional and never named; its 15 help articles are sample content.

## The problem

A small support team answers the same questions all day, and customers who write outside working hours wait until the next morning. The team wants an assistant that answers common questions at once, 24/7, from the team's own help articles, says "I'm not sure" rather than guessing, and hands anything it can't handle to a person with the whole conversation attached.

## What gets built

| Part | What it does |
|---|---|
| Website chat | n8n's chat widget, as a hosted page and embedded on a demo help page. Only listed websites can embed it. |
| WhatsApp | Meta's WhatsApp Cloud API (free test number). n8n checks Meta's signature on every webhook and ignores redelivered messages. |
| Answering | One shared workflow: search the help articles in Supabase (pgvector, Gemini embeddings), ask Gemini for a structured answer that cites its sources, then n8n checks the answer before sending it. |
| Handoff | When the customer asks for a person, is frustrated, or asks something the articles don't cover: ask for name and email, then post the transcript to Slack and email it to the team (reply-to set to the customer). Once per conversation; later messages join the same Slack thread. |
| Logging | Every message and reply in Supabase, with sources, scores, tokens and timing. One row per conversation in Google Sheets (name, email, issue type, status, transcript). |
| Knowledge base | Help articles are Google Docs in one Drive folder. A sync workflow (button or form) re-embeds only new or edited articles and removes deleted ones. |
| Settings | The system prompt, escalation rules, reply texts, thresholds and caps live in one Supabase table, editable without touching the workflows. |
| Failures | Retries on every external call. If search or the model still fails, the customer gets a polite reply and the team gets a Slack and email alert with a link to the failed run. |
| Tests | 57 scripted conversations scored automatically, plus live checks on the real services. |

## The job post, line by line

| The job asks for | How this build does it | Evidence |
|---|---|---|
| Answer from FAQs, help articles and documents with RAG and a vector database | Supabase pgvector, Gemini embeddings (1,536 dimensions), two searches per message, top 5 chunks as numbered sources | ANS-01 to ANS-25, L-02 |
| WhatsApp, Telegram or a website widget | Website widget (hosted page and embed) and WhatsApp, both through the same answering workflow | L-03, L-04 |
| Answer only from approved content; say "I'm not sure" instead of guessing | Prompt rules, plus n8n replaces any answer that cites no retrieved source, cites a source that was not retrieved, or rests on a weak match | NKB-01 to NKB-10, INJ-01 to INJ-04 |
| Escalate when asked, when frustrated, or when outside the knowledge base, with the full chat history to Slack or email | Escalation rules in settings; transcript to Slack and email | ESC-01 to ESC-09, L-05, L-06 |
| Collect name, email, issue type; log each conversation in Google Sheets or a CRM | Contact details captured when given and asked for before a handoff; issue type classified on every message; one sheet row per conversation | CON-01, CON-02, L-07 |
| Short conversation memory | The last 6 messages of the chat go to the model, and follow-ups are searched together with the previous message | MEM-01 to MEM-04 |
| Log every conversation and alert on failure | Supabase messages table; error workflow with Slack and email alerts | L-09, L-14 |
| A tested n8n workflow exported as JSON | 8 workflows in `workflows/` | Setup check L-01 |
| Knowledge base loaded, with simple update instructions | 15 articles synced from Drive; "Updating the knowledge base" in the setup guide | L-02, L-08 |
| Editable system prompts and escalation rules | bot_settings table | L-13 |
| Error handling and retry logic | Retries, fallback replies, error workflow | L-09, local failure tests |
| Loom walkthrough or written documentation | Docs in `docs/` and a captioned walkthrough video | |

## Acceptance criteria

| ID | Criterion |
|---|---|
| AC-01 | Answers to questions the articles cover give the right facts and cite the right article |
| AC-02 | The assistant works on the website widget and on WhatsApp |
| AC-03 | Questions the articles don't cover get "I'm not sure" and no invented facts |
| AC-04 | Asking for a person, frustration and questions outside the articles lead to one handoff with the full transcript in Slack and email |
| AC-05 | Name, email and issue type are captured and every conversation has a row in the sheet |
| AC-06 | Follow-up questions are answered in context |
| AC-07 | Every message is logged, and failures alert the team with a link to the run |
| AC-08 | Prompt, rules and texts can be changed without editing workflows |
| AC-09 | An edited or removed article is reflected after one sync |
| AC-10 | Attempts to change the assistant's rules or extract its prompt are refused |

## Out of scope

- Two-way human chat inside the widget. The team replies by email (or on WhatsApp); the assistant tells the customer how they'll hear back.
- Production WhatsApp. Meta's test number only messages up to five verified numbers; going live needs a verified business and a real number.
- A CRM. The sheet is the conversation log; a HubSpot step could reuse the pattern from the lead router build.
- Languages other than English.

## Costs (demo scale)

Gemini's API is used on its free tier (the job post names OpenAI or Claude; the reply logic reads both OpenAI's and Gemini's response shapes, and the setup guide describes the swap). Supabase, Slack, Google and Meta's test number are on free plans. n8n Cloud runs on the trial; the repo also works on self-hosted n8n. Message caps (30 per chat, 300 per day, both settings) keep a public demo from running up a bill.
