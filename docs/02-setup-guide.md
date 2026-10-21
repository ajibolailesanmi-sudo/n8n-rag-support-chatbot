# Setup guide

How to install the support chatbot in your own accounts, keep its knowledge base up to date and change how it behaves. Allow about two hours the first time (most of it is WhatsApp's account setup).

## 1. What you need

| Service | Plan | Used for |
|---|---|---|
| n8n | Cloud or self-hosted, version 2.41 or later | Runs the eight workflows |
| Supabase | Free | Knowledge base vectors, conversations, messages, settings |
| Gemini API (Google AI Studio) | Free tier | Replies (gemini-3.5-flash-lite) and embeddings (gemini-embedding-001). No card needed |
| Google Workspace or Gmail | Free | Help articles (Google Docs in a Drive folder) and the conversation log (Google Sheet) |
| Google Cloud service account | Free | Lets n8n read the folder and write the sheet |
| Slack | Free | Handoffs and alerts (a bot token with `chat:write`) |
| SMTP mailbox | Any | Handoff and alert emails (for Gmail, an app password) |
| Meta for Developers | Free test number | WhatsApp (optional) |

## 2. Supabase

1. Create a project. Pick the region closest to your n8n instance.
2. Open the SQL editor and run `sql/01-schema.sql`, then `sql/02-settings.sql`. Both can be run again safely.
3. Open Table Editor > `bot_settings` and set the account values:
   - `team_email`: where handoff emails go
   - `from_email`: the sender address (must match your SMTP account)
   - `slack_channel`: channel name or ID for handoffs, for example `#chat-escalations`
   - `sheet_id`: the ID in your Google Sheet's address (`/spreadsheets/d/<this part>/edit`)
   - `drive_folder_id`: the ID in your Drive folder's address (`/folders/<this part>`)
4. From Project Settings > API keys, copy the project URL and a secret key for the n8n credential.

Row level security is on for every table and no public policies exist, so the publishable (anon) key can read nothing. n8n uses the secret key.

## 3. Google

1. Create a Drive folder and put one help article in each Google Doc. Give each doc a clear title; the title is shown to the assistant as the source name.
2. Create a Google Sheet with three tabs and these header rows (row 1):
   - `conversations`: session_id, started_at, last_message_at, channel, status, handoff_reason, name, email, phone, issue_type, messages, not_sure_count, first_question, last_answer_status, transcript
   - `test_results`: run_id, run_group, case_id, group, category, result, failed_checks, turns, customer_messages, last_reply, answer_status, actions, final_status, cited, best_score, flags, tokens_in, tokens_out, latency_ms, model, prompt_version
   - `test_runs`: run_id, run_group, finished_at, cases, passed, failed, by_category, made_up_answers, failed_cases, answer_best_score_min, gap_best_score_max, avg_latency_ms, tokens_in, tokens_out, model, prompt_version
3. In Google Cloud, enable the Google Drive API and Google Sheets API, and create a service account with a JSON key.
4. Share the folder with the service account's email as Viewer, and the sheet as Editor.

## 4. n8n credentials

Create these credentials (the names match the workflow files; any names work if you reselect them after import). The Supabase, Slack, Google and SMTP ones can be shared with other workflows on the same instance:

| Credential type | Name in the workflows | What to enter |
|---|---|---|
| Header Auth | Gemini - Support Chatbot | Name `x-goog-api-key`, Value = your Gemini API key (in a header, so it never appears in a URL or log) |
| Supabase API | Supabase - Support Chatbot | Project URL and secret key |
| Google Service Account API | Google Service Account | Service account email and private key |
| Slack API | Slack Bot | Bot token (the bot must be in the handoff channel) |
| SMTP | SMTP | Host, port, user, password |
| WhatsApp OAuth API | WhatsApp OAuth - Support Chatbot | Meta App ID and App Secret |
| WhatsApp API | WhatsApp API - Support Chatbot | System user access token and WhatsApp Business Account ID |

## 5. Import the workflows

The files in `workflows/` contain placeholder values. Either edit them after import, or fill in `scripts/live-ids.json` (copy `live-ids.example.json`) and run `python3 scripts/build_workflows.py`, which writes import-ready copies to `out/live/` with your Supabase URL, alert addresses and credential IDs.

1. Import in this order, because later workflows call earlier ones: `90-error-alerts`, `30-escalate-to-team`, `20-answer-message`, then `10-website-chat`, `11-whatsapp`, `40-sync-knowledge-base`, `00-setup-check`, `99-test-runner`.
2. n8n gives each imported workflow a new ID. In every "Execute Workflow" node (Alert Team, Alert Store Down, Escalate, Answer, Call Answer), pick the workflow by name again. With `build_workflows.py`, put the new IDs of 90, 30 and 20 into `workflow_ids` and rebuild the rest instead.
3. Open each workflow's Settings and set Error workflow to `90 - Error Alerts` (an import does not keep this setting).
4. Check the Supabase URL in each `Config` node.
5. Publish `90`, `30` and `20` first. In n8n 2.x a sub-workflow that is not published silently does nothing. Then publish `10`, `11` and `40`.

## 6. First run

1. Run `40 - Sync Knowledge Base` from the editor. Slack shows how many articles and chunks were written.
2. Run `00 - Setup Check`. Every line should say PASS. A FAIL line names what to fix.

Gemini's free tier has per-minute and per-day request limits. The sync embeds one article per request and the assistant makes three requests per message (two embeddings, one reply), which stays well inside them for a demo; a busy production chat would use the paid tier or a cheaper plan of searches.
3. Open the Chat Trigger node in `10 - Website Chat` and copy the production chat URL. Open it in a browser and ask a question.

## 7. Website widget

The Chat Trigger serves its own chat page. To put the chat bubble on your website, add this before `</body>` and set the URL:

```html
<link href="https://cdn.jsdelivr.net/npm/@n8n/chat@1.42.4/dist/style.css" rel="stylesheet">
<script type="module">
  import { createChat } from 'https://cdn.jsdelivr.net/npm/@n8n/chat@1.42.4/dist/chat.bundle.es.js';
  createChat({ webhookUrl: 'YOUR CHAT URL', mode: 'window', loadPreviousSession: false });
</script>
```

Add your website's address to Allowed Origins in the Chat Trigger options, so other websites cannot embed your assistant. `docs/index.html` is a complete example page.

## 8. WhatsApp

1. At developers.facebook.com, create an app with the WhatsApp use case. Meta gives you a test phone number.
2. Under API Setup, add the phone numbers that may message the test number (up to five).
3. Create a system user in Business Settings, assign it the app, and generate a token with `whatsapp_business_messaging` and `whatsapp_business_management`. Temporary tokens expire after 24 hours.
4. Create the two WhatsApp credentials in n8n, then publish `11 - WhatsApp`. Publishing registers the webhook with Meta; an app can have only one.
5. Send a message to the test number from a verified phone.

On WhatsApp the assistant hands off straight away when a person is needed, because the team can reply on WhatsApp; it doesn't ask for an email.

## 9. Updating the knowledge base

1. Edit, add or delete Google Docs in the help articles folder.
2. Open the sync form at `https://YOUR-INSTANCE/form/kb-sync` and press Sync now (or run `40 - Sync Knowledge Base` in n8n).
3. The result page and Slack say what changed. Only new or edited articles are re-embedded; deleted articles are removed from the assistant's knowledge.

Tips: keep one topic per article, put exact facts in plain sentences (prices, times, steps), and use headings. If an answer is missing, the fix is almost always a clearer article rather than a prompt change. Choose "Re-embed every article" only after changing the chunk settings in the workflow.

## 10. Changing behaviour

Everything below lives in the `bot_settings` table. Edit the `value` cell; the next message uses it.

| Setting | What it changes |
|---|---|
| system_prompt | The assistant's instructions. Keep `{{state}}`, `{{today}}` and `{{channel}}`. Raise `prompt_version` when you change it, then re-run the tests |
| provider, model, max_output_tokens | Which API answers (gemini, or openai after the swap below), the model name, and the output limit |
| embedding_model, embedding_dimensions, chunk_size, chunk_overlap | How articles are embedded. Changing any of them means a full re-embed (sync form, "Re-embed every article") |
| min_similarity | How strong the best article match must be before an answer is trusted |
| number_check | `flag` logs numbers the cited articles don't contain; `block` also replaces such answers with "I'm not sure" |
| escalate_when_asked, escalate_when_frustrated, escalate_when_not_in_kb | When to hand off (yes/no; frustration level mild or high, or off) |
| handoff_keywords | Phrases that always count as asking for a person |
| max_contact_asks | How often to ask for an email before handing off without one |
| prefix_*, *_text | Every fixed reply the assistant sends (handoff, fallback, caps) |
| max_messages_per_chat, max_messages_per_day, session_window_hours | Message caps and when a chat starts fresh |

## 11. Using OpenAI instead of Gemini

The reply logic reads both response shapes. To switch: set `provider` to `openai` and `model` to an OpenAI model name in `bot_settings`; in `20 - Answer Message` point the `Ask Model` node at `https://api.openai.com/v1/responses` with an OpenAI credential; and for embeddings either keep Gemini (the knowledge base and the searches must use the same model) or replace the two embedding nodes with OpenAI's `/v1/embeddings` calls and re-embed everything.

## 12. Running the tests

Open `99 - Test Runner`, set `group` in Run Options to A, B or C (or list case IDs in `case_ids`), and run it. Each case gets its own test session and handoffs are built but not sent. Results go to the `test_results` and `test_runs` tabs and to Slack. The cases are in `eval/test-cases.csv`; `scripts/build_workflows.py` embeds them into the runner.

## 13. Privacy and safety notes

- Messages and replies are stored in Supabase and in n8n's execution history. Shorten n8n's execution retention, or stop saving successful executions, if your policy requires it.
- The sheet is written as raw values, so a message that starts with `=` or `+` is never run as a formula.
- The assistant never asks for passwords or card numbers and tells customers not to share them.
- Message caps limit cost if someone floods the public chat.

## 14. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Every answer is the fallback reply and the alert names Embed Query or Ask Model | The Gemini key is wrong or its daily quota is used up: run the setup check |
| The fallback reply and an alert that the search returned no rows | The knowledge base is empty: run `40 - Sync Knowledge Base` |
| "Workflow is not active" in an execution | A sub-workflow (`20`, `30` or `90`) is not published |
| Handoffs reach email but not Slack | The Slack bot is not a member of the channel |
| The sheet stays empty | The sheet is not shared with the service account as Editor, or `sheet_id` is wrong |
| The sync finds no articles | The folder is not shared with the service account, or `drive_folder_id` is wrong |
| WhatsApp messages get no reply | The token expired (use a system user token), or the sender is not a verified test number |
