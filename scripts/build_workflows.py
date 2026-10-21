"""Generate the eight n8n workflows for the RAG support chatbot.

Usage
  python3 scripts/build_workflows.py --placeholders   # repo copies in workflows/ (no account values)
  python3 scripts/build_workflows.py                  # import-ready copies in out/live/ from scripts/live-ids.json

live-ids.json (never committed) holds the Supabase URL, n8n URL, alert addresses, real credential IDs
and, once the sub-workflows exist in n8n, their workflow IDs.
"""
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from n8n_helpers import (  # noqa: E402
    CREDS, RETRY, RETRY_SLOW, WF_IDS, WF_NAMES, Workflow, code, code_params, email_send, exec_ref, http,
    if_params, rl, set_params, sheet_columns, slack_post, switch_params, uid, write,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLACEHOLDERS = "--placeholders" in sys.argv
LOCAL = "--local" in sys.argv
TZ = "America/New_York"

DEFAULTS = {
    "supabase_url": "https://YOUR-PROJECT.supabase.co",
    "gemini_url": "https://generativelanguage.googleapis.com/v1beta",
    "openai_url": "https://api.openai.com/v1",
    "n8n_url": "https://YOUR-INSTANCE.app.n8n.cloud",
    "allowed_origins": "*",
    "alert_slack_channel": "#chat-escalations",
    "alert_email": "alerts@example.com",
    "from_email": "assistant@example.com",
    "credentials": {},
    "workflow_ids": {},
}
LIVE = dict(DEFAULTS)
if not PLACEHOLDERS:
    live_path = ROOT / "scripts" / ("local-ids.json" if LOCAL else "live-ids.json")
    if not live_path.exists():
        raise SystemExit(f"{live_path.name} not found (copy live-ids.example.json); or use --placeholders")
    LIVE.update(json.loads(live_path.read_text()))

OUT_DIR = ROOT / "workflows" if PLACEHOLDERS else ROOT / "out" / ("local" if LOCAL else "live")

RESPONSE_SCHEMA = json.loads((ROOT / "prompts" / "response-schema.json").read_text())


def to_gemini_schema(node):
    """Gemini's responseSchema is an OpenAPI subset: no additionalProperties, nullable instead of null types."""
    if isinstance(node, list):
        return [to_gemini_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k == "additionalProperties":
            continue
        if k == "type" and isinstance(v, list):
            types = [t for t in v if t != "null"]
            out["type"] = types[0] if types else "string"
            if "null" in v:
                out["nullable"] = True
            continue
        out[k] = to_gemini_schema(v)
    return out


GEMINI_SCHEMA = to_gemini_schema(RESPONSE_SCHEMA)
(ROOT / "prompts" / "response-schema.gemini.json").write_text(json.dumps(GEMINI_SCHEMA, indent=2) + "\n")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"

LOG_COLUMNS = ["session_id", "started_at", "last_message_at", "channel", "status", "handoff_reason", "name", "email",
               "phone", "issue_type", "messages", "not_sure_count", "first_question", "last_answer_status", "transcript"]
TEST_RESULT_COLUMNS = ["run_id", "run_group", "case_id", "group", "category", "result", "failed_checks", "turns",
                       "customer_messages", "last_reply", "answer_status", "actions", "final_status", "cited",
                       "best_score", "flags", "tokens_in", "tokens_out", "latency_ms", "model", "prompt_version"]
TEST_RUN_COLUMNS = ["run_id", "run_group", "finished_at", "cases", "passed", "failed", "by_category", "made_up_answers",
                    "failed_cases", "answer_best_score_min", "gap_best_score_max", "avg_latency_ms", "tokens_in",
                    "tokens_out", "model", "prompt_version"]

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
WELCOME = ("Hi! I'm the help desk assistant for this sample IT services firm.\n"
           "Ask me about passwords, MFA, the VPN, email, billing, plans or support hours. "
           "If I can't help, I'll pass you to a person.")
FALLBACK = "Sorry, I'm having trouble answering right now. Please try again in a few minutes."
CHAT_CSS = """:root {
  --chat--color--primary: #1f6feb;
  --chat--color--primary-shade-50: #1a5fcc;
  --chat--color--primary--shade-100: #154fa8;
  --chat--color--secondary: #101820;
  --chat--color-secondary-shade-50: #0b1117;
  --chat--color-white: #ffffff;
  --chat--color-light: #f7f8f6;
  --chat--color-light-shade-50: #eceee9;
  --chat--color-light-shade-100: #dfe3e8;
  --chat--color-medium: #c9ced4;
  --chat--color-dark: #101820;
  --chat--color-disabled: #8a929b;
  --chat--color-typing: #5b6470;
  --chat--font-family: Inter, 'Segoe UI', system-ui, sans-serif;
  --chat--header--background: #101820;
  --chat--header--color: #f7f8f6;
  --chat--message--bot--background: #ffffff;
  --chat--message--bot--color: #101820;
  --chat--message--user--background: #1f6feb;
  --chat--message--user--color: #ffffff;
}"""


def wf_id(key):
    return LIVE["workflow_ids"].get(key, WF_IDS[key]) if not (PLACEHOLDERS or LOCAL) else WF_IDS[key]


def ref(key, wait=True):
    r = exec_ref(key, wait)
    real = wf_id(key)
    r["workflowId"]["value"] = real
    r["workflowId"]["cachedResultUrl"] = f"/workflow/{real}"
    return r


def settings(error_workflow=True):
    s = {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "saveDataErrorExecution": "all",
        "saveDataSuccessExecution": "all",
        "saveExecutionProgress": True,
        "timezone": TZ,
        "callerPolicy": "workflowsFromSameOwner",
    }
    if error_workflow:
        s["errorWorkflow"] = wf_id("errors")
    return s


def load_cases():
    cases = []
    with open(ROOT / "eval" / "test-cases.csv", newline="") as f:
        for r in csv.DictReader(f):
            split = lambda s, sep: [x.strip() for x in s.split(sep) if x.strip()]  # noqa: E731
            actions = []
            for pair in split(r["expect_actions"], ";"):
                n, a = pair.split(":")
                actions.append([int(n), a.strip()])
            cases.append({
                "id": r["id"],
                "group": r["group"],
                "category": r["category"],
                "channel": r["channel"],
                "turns": split(r["turns"], "||"),
                "expect_status": r["expect_status"].strip(),
                "must_include": [split(g, "|") for g in split(r["must_include"], ";")],
                "must_cite": r["must_cite"].strip(),
                "must_not_include": split(r["must_not_include"], ";"),
                "expect_actions": actions,
                "expect_final_status": r["expect_final_status"].strip(),
                "expect_contact_email": r["expect_contact_email"].strip(),
                "expect_flags": split(r["expect_flags"], ";"),
            })
    return cases


SB = "$('Config').first().json.supabase_url"
GM = "$('Config').first().json.gemini_url"


def gemini_http(url_expr, body_expr, timeout=60000):
    p = http("POST", url_expr, body_expr, options={"timeout": timeout})
    p["authentication"] = "genericCredentialType"
    p["genericAuthType"] = "httpHeaderAuth"
    return p


# =====================================================================
# 20 - Answer Message
# =====================================================================
def build_answer():
    w = Workflow("answer")
    w.sticky("About", "## 20 - Answer Message\nShared by the website chat, WhatsApp and the test runner.\n"
             "1. Register the message: caps, memory and settings in one call.\n"
             "2. Search the help articles twice (the message, and with the previous message).\n"
             "3. Ask the model (Gemini) for a structured answer that cites its sources.\n"
             "4. Check the answer is grounded and apply the escalation rules.\n"
             "5. Log the reply, hand off to the team if needed, update the sheet.",
             (-40, -60), 560, 260, 4)
    w.add("When Called", "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, (0, 300))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([
        ("supabase_url", LIVE["supabase_url"], "string"),
        ("gemini_url", LIVE["gemini_url"], "string"),
        ("n8n_url", LIVE["n8n_url"], "string"),
        ("started_ms", "={{ Date.now() }}", "number"),
        ("store_down_text", "Sorry, I can't answer right now. Please try again in a few minutes, or contact the help desk through the client portal.", "string"),
    ], include_other=True), (220, 300))
    w.add("Register Message", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", "={{ $json.supabase_url }}/rest/v1/rpc/register_message",
        "={{ JSON.stringify({ p_session_id: $json.session_id, p_channel: $json.channel, "
        "p_text: String($json.text || '').slice(0, 2000), p_is_test: !!$json.is_test, "
        "p_contact_phone: $json.contact_phone || null, p_contact_name: $json.contact_name || null, "
        "p_external_id: $json.external_id || null }) }}",
        cred_type="supabaseApi", options={"timeout": 15000}),
        (440, 300), creds=["supabase"], onError="continueErrorOutput", **RETRY)
    w.add("Prepare Turn", "n8n-nodes-base.code", 2, code_params(code("20_prepare_turn.js")), (660, 300))
    w.add("Route", "n8n-nodes-base.switch", 3.2, switch_params("={{ $json.route }}", [
        ("answer", "answer"), ("limit", "limit"), ("duplicate", "duplicate")]), (880, 300))
    w.add("Search Queries", "n8n-nodes-base.code", 2, code_params(code("20_search_queries.js")), (1100, 200))
    w.add("Embed Query", "n8n-nodes-base.httpRequest", 4.2, gemini_http(
        f"={{{{ {GM} }}}}/models/{{{{ $('Prepare Turn').first().json.settings.embedding_model }}}}:embedContent",
        "={{ JSON.stringify($json.embed_body) }}", timeout=30000),
        (1320, 200), creds=["gemini"], onError="continueErrorOutput", **RETRY_SLOW)
    w.add("Search Knowledge Base", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", f"={{{{ {SB} }}}}/rest/v1/rpc/match_documents",
        "={{ JSON.stringify({ query_embedding: $json.embedding.values, "
        "match_count: $('Prepare Turn').first().json.num.top_k }) }}",
        cred_type="supabaseApi", options={"timeout": 15000}),
        (1540, 200), creds=["supabase"], alwaysOutputData=True, onError="continueErrorOutput", **RETRY)
    w.add("Merge Sources", "n8n-nodes-base.code", 2, code_params(code(
        "20_merge_sources.js", {"__RESPONSE_SCHEMA__": json.dumps(RESPONSE_SCHEMA),
                                "__GEMINI_SCHEMA__": json.dumps(GEMINI_SCHEMA)})), (1760, 200))
    w.add("Search OK?", "n8n-nodes-base.if", 2.2, if_params("={{ $json.search_failed !== true }}"), (1870, 200))
    w.add("Ask Model", "n8n-nodes-base.httpRequest", 4.2, gemini_http(
        f"={{{{ {GM} }}}}/models/{{{{ $json.model }}}}:generateContent",
        "={{ JSON.stringify($json.request_body) }}", timeout=60000),
        (2090, 200), creds=["gemini"], onError="continueErrorOutput", **RETRY_SLOW)
    w.add("Apply Rules", "n8n-nodes-base.code", 2, code_params(code("20_apply_rules.js")), (2310, 200))
    w.add("Limit Reply", "n8n-nodes-base.code", 2, code_params(code("20_limit_reply.js")), (1100, 440))
    w.add("Skip Duplicate", "n8n-nodes-base.code", 2, code_params(code("20_skip_duplicate.js")), (1100, 620))
    w.add("Fallback Reply", "n8n-nodes-base.code", 2, code_params(code("20_fallback_reply.js")), (1980, 440))
    w.add("Alert Team", "n8n-nodes-base.executeWorkflow", 1.2, ref("errors", wait=False), (2200, 440))
    w.add("Reply Data", "n8n-nodes-base.code", 2, code_params(code("20_reply_data.js")), (2420, 300))
    w.add("Log Reply", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", f"={{{{ {SB} }}}}/rest/v1/rpc/log_reply",
        "={{ JSON.stringify({ p_session_id: $json.session_id, p_reply: $json.reply, "
        "p_answer_status: $json.answer_status, p_sources: { retrieved: $json.retrieved, cited: $json.cited }, "
        "p_best_score: $json.best_score, p_flags: $json.flags, p_model: $json.model, "
        "p_prompt_version: $json.prompt_version, p_tokens_in: $json.tokens_in, p_tokens_out: $json.tokens_out, "
        "p_latency_ms: $json.latency_ms, p_state: $json.state }) }}",
        cred_type="supabaseApi", options={"timeout": 15000}),
        (2640, 300), creds=["supabase"], onError="continueRegularOutput", **RETRY)
    w.add("Needs Team?", "n8n-nodes-base.if", 2.2, if_params(
        "={{ ['handoff_now', 'handoff_followup'].includes($('Reply Data').first().json.action) }}"), (2860, 300))
    w.add("Escalation Input", "n8n-nodes-base.code", 2, code_params(code("20_escalation_input.js")), (3080, 200))
    w.add("Escalate", "n8n-nodes-base.executeWorkflow", 1.2, ref("escalate", wait=True), (3300, 200),
          onError="continueRegularOutput")
    w.add("Write Log Row?", "n8n-nodes-base.if", 2.2, if_params(
        "={{ !$('Reply Data').first().json.is_test && "
        "/^[A-Za-z0-9_-]{20,}$/.test(String($('Reply Data').first().json.delivery.sheet_id || '')) }}"),
        (3520, 300))
    w.add("Log Row", "n8n-nodes-base.code", 2, code_params(code("20_log_row.js")), (3740, 200))
    w.add("Log to Sheet", "n8n-nodes-base.googleSheets", 4.7, {
        "authentication": "serviceAccount",
        "operation": "appendOrUpdate",
        "documentId": rl("={{ $('Reply Data').first().json.delivery.sheet_id }}", "id"),
        "sheetName": rl("conversations", "name"),
        "columns": sheet_columns(LOG_COLUMNS, ["session_id"]),
        "options": {"cellFormat": "RAW", "handlingExtraData": "ignoreIt"},
    }, (3960, 200), creds=["google"], onError="continueRegularOutput", **RETRY_SLOW)
    w.add("Return Reply", "n8n-nodes-base.code", 2, code_params(code("20_return_reply.js")), (4180, 300))
    w.add("Store Down Reply", "n8n-nodes-base.code", 2, code_params(code("20_store_down_reply.js")), (660, 560))
    w.add("Alert Store Down", "n8n-nodes-base.executeWorkflow", 1.2, ref("errors", wait=False), (880, 800))
    w.add("Return Store Down", "n8n-nodes-base.code", 2, code_params("return $input.all();"), (1100, 800))

    w.chain("When Called", "Config", "Register Message")
    w.connect("Register Message", "Prepare Turn", 0)
    w.connect("Register Message", "Store Down Reply", 1)
    w.connect("Prepare Turn", "Route")
    w.connect("Route", "Search Queries", 0)
    w.connect("Route", "Limit Reply", 1)
    w.connect("Route", "Skip Duplicate", 2)
    w.connect("Search Queries", "Embed Query")
    w.connect("Embed Query", "Search Knowledge Base", 0)
    w.connect("Embed Query", "Fallback Reply", 1)
    w.connect("Search Knowledge Base", "Merge Sources", 0)
    w.connect("Search Knowledge Base", "Fallback Reply", 1)
    w.connect("Merge Sources", "Search OK?")
    w.connect("Search OK?", "Ask Model", 0)
    w.connect("Search OK?", "Fallback Reply", 1)
    w.connect("Ask Model", "Apply Rules", 0)
    w.connect("Ask Model", "Fallback Reply", 1)
    w.connect("Apply Rules", "Reply Data")
    w.connect("Limit Reply", "Reply Data")
    w.chain("Fallback Reply", "Alert Team", "Reply Data")
    w.chain("Reply Data", "Log Reply", "Needs Team?")
    w.connect("Needs Team?", "Escalation Input", 0)
    w.connect("Needs Team?", "Write Log Row?", 1)
    w.chain("Escalation Input", "Escalate", "Write Log Row?")
    w.connect("Write Log Row?", "Log Row", 0)
    w.connect("Write Log Row?", "Return Reply", 1)
    w.chain("Log Row", "Log to Sheet", "Return Reply")
    w.chain("Store Down Reply", "Alert Store Down", "Return Store Down")
    return w.to_json(settings())


# =====================================================================
# 30 - Escalate to Team
# =====================================================================
def build_escalate():
    w = Workflow("escalate")
    w.sticky("About", "## 30 - Escalate to Team\nClaims the handoff once (a second message cannot hand off twice), "
             "posts the transcript to Slack, saves the Slack thread and emails the team with reply-to set to the "
             "customer. A message after the handoff goes into the same Slack thread. Test runs (dry run) build "
             "everything but send nothing.", (-40, -40), 620, 200, 4)
    w.add("When Called", "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, (0, 300))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([
        ("supabase_url", LIVE["supabase_url"], "string"),
        ("n8n_url", LIVE["n8n_url"], "string"),
    ], include_other=True), (220, 300))
    w.add("Follow-up?", "n8n-nodes-base.if", 2.2, if_params("={{ $json.action === 'handoff_followup' }}"), (440, 300))
    w.add("Get Conversation", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", "={{ $json.supabase_url }}/rest/v1/conversations?session_id=eq.{{ encodeURIComponent($json.session_id) }}"
               "&select=session_id,slack_ts", cred_type="supabaseApi"),
        (660, 160), creds=["supabase"], alwaysOutputData=True, **RETRY)
    w.add("Follow-up Message", "n8n-nodes-base.code", 2, code_params(code("30_followup_message.js")), (880, 160))
    w.add("Dry Run Follow-up?", "n8n-nodes-base.if", 2.2, if_params("={{ !!$('Config').first().json.dry_run }}"), (1100, 160))
    w.add("Post Follow-up", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", "https://slack.com/api/chat.postMessage", "={{ JSON.stringify($json.body) }}", cred_type="slackApi"),
        (1320, 240), creds=["slack"], onError="continueRegularOutput", **RETRY)
    w.add("Return Follow-up", "n8n-nodes-base.code", 2, code_params(code("30_return_followup.js")), (1540, 160))
    w.add("Claim Handoff", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", "={{ $json.supabase_url }}/rest/v1/rpc/claim_handoff",
        "={{ JSON.stringify({ p_session_id: $json.session_id, p_reason: $json.reason || 'asked_for_person' }) }}",
        cred_type="supabaseApi"), (660, 440), creds=["supabase"], **RETRY)
    w.add("Claimed?", "n8n-nodes-base.if", 2.2, if_params("={{ $json.claimed === true }}"), (880, 440))
    w.add("Build Handoff", "n8n-nodes-base.code", 2, code_params(code("30_build_handoff.js")), (1100, 440))
    w.add("Dry Run?", "n8n-nodes-base.if", 2.2, if_params("={{ !!$('Config').first().json.dry_run }}"), (1320, 440))
    w.add("Post to Slack", "n8n-nodes-base.slack", 2.3, slack_post("={{ $json.slack_channel }}", "={{ $json.slack_text }}"),
          (1540, 540), creds=["slack"], onError="continueRegularOutput", **RETRY)
    w.add("Save Slack Thread", "n8n-nodes-base.httpRequest", 4.2, http(
        "PATCH", "={{ $('Config').first().json.supabase_url }}/rest/v1/conversations?session_id=eq."
                 "{{ encodeURIComponent($('Build Handoff').first().json.session_id) }}",
        "={{ JSON.stringify({ slack_ts: $json.ts || ($json.message && $json.message.ts) || null }) }}",
        cred_type="supabaseApi"), (1760, 540), creds=["supabase"], onError="continueRegularOutput")
    w.add("Email Team", "n8n-nodes-base.emailSend", 2.1, email_send(
        "={{ $('Build Handoff').first().json.from_email }}", "={{ $('Build Handoff').first().json.team_email }}",
        "={{ $('Build Handoff').first().json.subject }}", "={{ $('Build Handoff').first().json.html }}",
        reply_to="={{ $('Build Handoff').first().json.reply_to }}"),
        (1980, 540), creds=["smtp"], onError="continueRegularOutput", **RETRY)
    w.add("Return Handoff", "n8n-nodes-base.code", 2, code_params(code("30_return_handoff.js")), (2200, 440))
    w.add("Return Already", "n8n-nodes-base.code", 2, code_params(code("30_return_already.js")), (1100, 640))

    w.chain("When Called", "Config", "Follow-up?")
    w.connect("Follow-up?", "Get Conversation", 0)
    w.connect("Follow-up?", "Claim Handoff", 1)
    w.chain("Get Conversation", "Follow-up Message", "Dry Run Follow-up?")
    w.connect("Dry Run Follow-up?", "Return Follow-up", 0)
    w.connect("Dry Run Follow-up?", "Post Follow-up", 1)
    w.connect("Post Follow-up", "Return Follow-up")
    w.chain("Claim Handoff", "Claimed?")
    w.connect("Claimed?", "Build Handoff", 0)
    w.connect("Claimed?", "Return Already", 1)
    w.chain("Build Handoff", "Dry Run?")
    w.connect("Dry Run?", "Return Handoff", 0)
    w.connect("Dry Run?", "Post to Slack", 1)
    w.chain("Post to Slack", "Save Slack Thread", "Email Team", "Return Handoff")
    return w.to_json(settings())


# =====================================================================
# 10 - Website Chat
# =====================================================================
def build_web():
    w = Workflow("web")
    w.sticky("About", "## 10 - Website Chat\nPublic chat for the website widget and the hosted chat page. "
             "Allowed origins limit which websites can embed it. Every message goes to 20 - Answer Message; "
             "if that fails, the visitor still gets a polite reply.", (-40, -20), 520, 180, 4)
    w.add("Chat Trigger", "@n8n/n8n-nodes-langchain.chatTrigger", 1.3, {
        "public": True,
        "mode": "hostedChat",
        "authentication": "none",
        "initialMessages": WELCOME,
        "options": {
            "allowedOrigins": LIVE["allowed_origins"],
            "title": "IT Help Desk",
            "subtitle": "Sample help centre. Solvant Labs demo build.",
            "inputPlaceholder": "Ask about passwords, VPN, billing...",
            "loadPreviousSession": "notSupported",
            "responseMode": "lastNode",
            "customCss": CHAT_CSS,
        },
    }, (0, 300), webhookId=uid("web", "chat-webhook"))
    w.add("Normalize", "n8n-nodes-base.set", 3.4, set_params([
        ("channel", "web", "string"),
        ("session_id", "={{ 'web:' + $json.sessionId }}", "string"),
        ("text", "={{ $json.chatInput }}", "string"),
        ("is_test", False, "boolean"),
        ("dry_run", False, "boolean"),
    ]), (220, 300))
    w.add("Answer", "n8n-nodes-base.executeWorkflow", 1.2, ref("answer", wait=True), (440, 300),
          onError="continueErrorOutput")
    w.add("Chat Reply", "n8n-nodes-base.set", 3.4, set_params([
        ("output", "={{ $json.reply || $json.output || '' }}", "string")]), (660, 220))
    w.add("Chat Fallback", "n8n-nodes-base.set", 3.4, set_params([("output", FALLBACK, "string")]), (660, 420))
    w.chain("Chat Trigger", "Normalize", "Answer")
    w.connect("Answer", "Chat Reply", 0)
    w.connect("Answer", "Chat Fallback", 1)
    return w.to_json(settings())


# =====================================================================
# 11 - WhatsApp
# =====================================================================
def whatsapp_send(text_expr):
    return {
        "resource": "message",
        "operation": "send",
        "phoneNumberId": "={{ $('Loop Messages').first().json.phone_number_id }}",
        "recipientPhoneNumber": "={{ $('Loop Messages').first().json.recipient }}",
        "messageType": "text",
        "textBody": text_expr,
        "additionalFields": {},
    }


def build_whatsapp():
    w = Workflow("whatsapp")
    w.sticky("About", "## 11 - WhatsApp\nMeta signs every webhook; n8n checks the signature with the app secret. "
             "Each text message goes to 20 - Answer Message and the reply is sent back on WhatsApp. "
             "Redelivered messages are ignored, and voice notes or images get a short text-only notice.",
             (-40, -20), 560, 180, 4)
    w.add("WhatsApp Trigger", "n8n-nodes-base.whatsAppTrigger", 1, {
        "updates": ["messages"], "options": {"messageStatusUpdates": []}},
        (0, 300), creds=["wa_trigger"], webhookId=uid("whatsapp", "trigger-webhook"))
    w.add("Split Messages", "n8n-nodes-base.code", 2, code_params(code("11_split_messages.js")), (220, 300))
    w.add("Loop Messages", "n8n-nodes-base.splitInBatches", 3, {"batchSize": 1, "options": {}}, (440, 300))
    w.add("Done", "n8n-nodes-base.noOp", 1, {}, (660, 120))
    w.add("Text Message?", "n8n-nodes-base.if", 2.2, if_params(
        "={{ $json.kind === 'text' && String($json.text || '').trim().length > 0 }}"), (660, 380))
    w.add("Answer", "n8n-nodes-base.executeWorkflow", 1.2, ref("answer", wait=True), (880, 300),
          onError="continueErrorOutput")
    w.add("Skip?", "n8n-nodes-base.if", 2.2, if_params("={{ $json.skip === true }}"), (1100, 240))
    w.add("Send Reply", "n8n-nodes-base.whatsApp", 1.1, whatsapp_send("={{ $json.reply }}"), (1320, 300),
          creds=["wa_api"], onError="continueRegularOutput", **RETRY)
    w.add("Send Fallback", "n8n-nodes-base.whatsApp", 1.1, whatsapp_send(FALLBACK), (1100, 460),
          creds=["wa_api"], onError="continueRegularOutput", **RETRY)
    w.add("Send Text-Only Notice", "n8n-nodes-base.whatsApp", 1.1, whatsapp_send(
        "I can only read text messages at the moment. Please type your question."), (880, 560),
        creds=["wa_api"], onError="continueRegularOutput", **RETRY)
    w.chain("WhatsApp Trigger", "Split Messages", "Loop Messages")
    w.connect("Loop Messages", "Done", 0)
    w.connect("Loop Messages", "Text Message?", 1)
    w.connect("Text Message?", "Answer", 0)
    w.connect("Text Message?", "Send Text-Only Notice", 1)
    w.connect("Answer", "Skip?", 0)
    w.connect("Answer", "Send Fallback", 1)
    w.connect("Skip?", "Loop Messages", 0)
    w.connect("Skip?", "Send Reply", 1)
    w.connect("Send Reply", "Loop Messages")
    w.connect("Send Fallback", "Loop Messages")
    w.connect("Send Text-Only Notice", "Loop Messages")
    return w.to_json(settings())


# =====================================================================
# 40 - Sync Knowledge Base
# =====================================================================
def build_sync():
    w = Workflow("sync")
    w.sticky("About", "## 40 - Sync Knowledge Base\nReads the Google Drive folder of help articles (Google Docs). "
             "New or edited articles are exported as Markdown, split into chunks, embedded with Gemini and stored in Supabase; "
             "articles removed from the folder are deleted. Run it from the editor or from the sync form.",
             (-40, 0), 600, 180, 4)
    w.add("Run Sync", "n8n-nodes-base.manualTrigger", 1, {}, (0, 260))
    w.add("Run Options", "n8n-nodes-base.set", 3.4, set_params([("force_full", False, "boolean")]), (220, 260))
    w.add("Sync Form", "n8n-nodes-base.formTrigger", 2.5, {
        "formTitle": "Sync the help centre",
        "formDescription": "Re-reads the Google Drive folder of help articles and updates what the chat assistant "
                           "knows. Only new or edited articles are re-embedded.",
        "formFields": {"values": [{
            "fieldLabel": "Re-embed every article?",
            "fieldName": "reembed_all",
            "fieldType": "dropdown",
            "fieldOptions": {"values": [{"option": "No"}, {"option": "Yes"}]},
            "requiredField": True,
        }]},
        "responseMode": "lastNode",
        "options": {"path": "kb-sync", "buttonLabel": "Sync now", "appendAttribution": False},
    }, (0, 460), webhookId=uid("sync", "form-webhook"))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([
        ("supabase_url", LIVE["supabase_url"], "string"),
        ("gemini_url", LIVE["gemini_url"], "string"),
    ]), (440, 360))
    w.add("Get Settings", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", "={{ $json.supabase_url }}/rest/v1/bot_settings?select=key,value", cred_type="supabaseApi"),
        (660, 360), creds=["supabase"], **RETRY)
    w.add("Settings", "n8n-nodes-base.code", 2, code_params(code("40_settings.js")), (880, 360))
    w.add("List Articles", "n8n-nodes-base.googleDrive", 3, {
        "authentication": "serviceAccount",
        "resource": "fileFolder",
        "searchMethod": "query",
        "queryString": "",
        "returnAll": True,
        "filter": {
            "folderId": rl("={{ $json.drive_folder_id }}", "id"),
            "whatToSearch": "files",
            "fileTypes": [GOOGLE_DOC_MIME],
            "includeTrashed": False,
        },
        "options": {"fields": ["*"]},
    }, (1100, 360), creds=["google"], alwaysOutputData=True, **RETRY)
    w.add("Get Index", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", f"={{{{ {SB} }}}}/rest/v1/kb_files?select=*", cred_type="supabaseApi"),
        (1320, 360), creds=["supabase"], alwaysOutputData=True, executeOnce=True, **RETRY)
    w.add("Plan Sync", "n8n-nodes-base.code", 2, code_params(code("40_plan_sync.js")), (1540, 360))
    w.add("Any Removed?", "n8n-nodes-base.if", 2.2, if_params("={{ $json.deletes.length > 0 }}"), (1760, 360))
    w.add("Delete Removed Chunks", "n8n-nodes-base.httpRequest", 4.2, http(
        "DELETE", f"={{{{ {SB} }}}}/rest/v1/documents?file_id=in.{{{{ $json.delete_filter }}}}", cred_type="supabaseApi"),
        (1980, 260), creds=["supabase"], **RETRY)
    w.add("Delete Removed Index", "n8n-nodes-base.httpRequest", 4.2, http(
        "DELETE", f"={{{{ {SB} }}}}/rest/v1/kb_files?file_id=in.{{{{ $('Plan Sync').first().json.delete_filter }}}}",
        cred_type="supabaseApi"), (2200, 260), creds=["supabase"], executeOnce=True, **RETRY)
    w.add("Any Changed?", "n8n-nodes-base.if", 2.2, if_params("={{ $('Plan Sync').first().json.upserts.length > 0 }}"),
          (2420, 360))
    w.add("Upsert Items", "n8n-nodes-base.code", 2, code_params(code("40_upsert_items.js")), (2640, 260))
    w.add("Download Article", "n8n-nodes-base.googleDrive", 3, {
        "authentication": "serviceAccount",
        "operation": "download",
        "fileId": rl("={{ $json.file_id }}", "id"),
        "options": {"googleFileConversion": {"conversion": {"docsToFormat": "text/markdown"}}},
    }, (2860, 260), creds=["google"], **RETRY)
    w.add("Prepare Article", "n8n-nodes-base.code", 2, code_params(code("40_prepare_article.js")), (3080, 260))
    w.add("Remove Old Chunks", "n8n-nodes-base.httpRequest", 4.2, http(
        "DELETE", f"={{{{ {SB} }}}}/rest/v1/documents?file_id=eq.{{{{ encodeURIComponent($json.file_id) }}}}",
        cred_type="supabaseApi"), (3300, 260), creds=["supabase"], **RETRY)
    w.add("Chunk Articles", "n8n-nodes-base.code", 2, code_params(code("40_chunk_articles.js")), (3520, 260))
    w.add("Embed Chunks", "n8n-nodes-base.httpRequest", 4.2, gemini_http(
        f"={{{{ {GM} }}}}/models/{{{{ $('Settings').first().json.settings.embedding_model }}}}:batchEmbedContents",
        "={{ JSON.stringify($json.embed_body) }}", timeout=60000),
        (3740, 260), creds=["gemini"], **RETRY_SLOW)
    w.add("Build Rows", "n8n-nodes-base.code", 2, code_params(code("40_build_rows.js")), (3960, 260))
    w.add("Store Chunks", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", f"={{{{ {SB} }}}}/rest/v1/documents", "={{ JSON.stringify($json.rows) }}",
        cred_type="supabaseApi", headers=[("Prefer", "return=minimal")]),
        (4180, 260), creds=["supabase"], **RETRY)
    w.add("Count Chunks", "n8n-nodes-base.code", 2, code_params(code("40_count_chunks.js")), (4400, 260))
    w.add("Update Index", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", f"={{{{ {SB} }}}}/rest/v1/kb_files?on_conflict=file_id", "={{ JSON.stringify($json.rows) }}",
        cred_type="supabaseApi", headers=[("Prefer", "resolution=merge-duplicates,return=minimal")]),
        (4620, 260), creds=["supabase"], **RETRY)
    w.add("Summary", "n8n-nodes-base.code", 2, code_params(code("40_summary.js")), (4840, 360))
    w.add("Post Summary", "n8n-nodes-base.slack", 2.3, slack_post(
        "={{ $('Settings').first().json.slack_channel }}", "={{ $json.slack_text }}"),
        (5060, 360), creds=["slack"], onError="continueRegularOutput", **RETRY)
    w.add("From Form?", "n8n-nodes-base.if", 2.2, if_params("={{ $('Sync Form').isExecuted }}"), (5280, 360))
    w.add("Show Result", "n8n-nodes-base.form", 2.3, {
        "operation": "completion",
        "respondWith": "text",
        "completionTitle": "={{ $('Summary').first().json.headline }}",
        "completionMessage": "={{ $('Summary').first().json.detail }}",
        "options": {},
    }, (5500, 300))

    w.chain("Run Sync", "Run Options", "Config")
    w.connect("Sync Form", "Config")
    w.chain("Config", "Get Settings", "Settings", "List Articles", "Get Index", "Plan Sync", "Any Removed?")
    w.connect("Any Removed?", "Delete Removed Chunks", 0)
    w.connect("Any Removed?", "Any Changed?", 1)
    w.chain("Delete Removed Chunks", "Delete Removed Index", "Any Changed?")
    w.connect("Any Changed?", "Upsert Items", 0)
    w.connect("Any Changed?", "Summary", 1)
    w.chain("Upsert Items", "Download Article", "Prepare Article", "Remove Old Chunks", "Chunk Articles",
            "Embed Chunks", "Build Rows", "Store Chunks", "Count Chunks", "Update Index", "Summary")
    w.chain("Summary", "Post Summary", "From Form?")
    w.connect("From Form?", "Show Result", 0)
    return w.to_json(settings())


# =====================================================================
# 90 - Error Alerts
# =====================================================================
def build_errors():
    w = Workflow("errors")
    w.sticky("About", "## 90 - Error Alerts\nSet as the error workflow of every other workflow, and also called "
             "directly when 20 - Answer Message catches a failure. Alerts go to Slack and email with a link to the "
             "failed execution. Settings are fixed here so alerts still work if Supabase is down.",
             (-40, 0), 580, 180, 4)
    w.add("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, (0, 260))
    w.add("When Called", "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, (0, 460))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([
        ("slack_channel", LIVE["alert_slack_channel"], "string"),
        ("alert_email", LIVE["alert_email"], "string"),
        ("from_email", LIVE["from_email"], "string"),
        ("timezone", TZ, "string"),
    ]), (220, 360))
    w.add("Format Error", "n8n-nodes-base.code", 2, code_params(code("90_format_error.js")), (440, 360))
    w.add("Post Alert", "n8n-nodes-base.slack", 2.3, slack_post(
        "={{ $('Config').first().json.slack_channel }}", "={{ $json.slack_text }}"),
        (660, 360), creds=["slack"], onError="continueRegularOutput", **RETRY)
    w.add("Email Alert", "n8n-nodes-base.emailSend", 2.1, email_send(
        "={{ $('Config').first().json.from_email }}", "={{ $('Config').first().json.alert_email }}",
        "={{ $('Format Error').first().json.subject }}", "={{ $('Format Error').first().json.html }}"),
        (880, 360), creds=["smtp"], onError="continueRegularOutput", **RETRY)
    w.connect("Error Trigger", "Config")
    w.connect("When Called", "Config")
    w.chain("Config", "Format Error", "Post Alert", "Email Alert")
    return w.to_json(settings(error_workflow=False))


# =====================================================================
# 00 - Setup Check
# =====================================================================
SETTINGS_OBJECT_JS = r"""// Settings Object: settings as one object, plus the two tiny requests for the model and embedding checks.
const rows = $input.all().map((i) => i.json).filter((j) => j && j.key);
const settings = Object.fromEntries(rows.map((r) => [r.key, r.value]));
const dims = parseInt(settings.embedding_dimensions, 10) || 1536;
const model_body = {
  systemInstruction: { parts: [{ text: 'You are a setup check. Reply as JSON.' }] },
  contents: [{ role: 'user', parts: [{ text: 'Setup check. Reply with ok set to true.' }] }],
  generationConfig: { temperature: 0, maxOutputTokens: 200, responseMimeType: 'application/json',
    responseSchema: { type: 'object', required: ['ok'], properties: { ok: { type: 'boolean' } } } },
};
const embed_body = { content: { parts: [{ text: 'setup check' }] }, taskType: 'RETRIEVAL_QUERY', outputDimensionality: dims };
return [{ json: { settings, model_body, embed_body, expected_dims: dims, ok: rows.length > 0 } }];
"""


def build_setup():
    w = Workflow("setup")
    w.sticky("About", "## 00 - Setup Check\nRun after setup and after any credential change. Checks the settings, "
             "the database functions, the Gemini model with structured output, embeddings, the knowledge base, "
             "the Drive folder and the Google Sheet, then posts PASS/FAIL lines to Slack.", (-40, 0), 600, 180, 4)
    w.add("Run Check", "n8n-nodes-base.manualTrigger", 1, {}, (0, 360))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([
        ("supabase_url", LIVE["supabase_url"], "string"),
        ("gemini_url", LIVE["gemini_url"], "string"),
    ]), (220, 360))
    w.add("Read Settings", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", "={{ $json.supabase_url }}/rest/v1/bot_settings?select=key,value", cred_type="supabaseApi"),
        (440, 360), creds=["supabase"], onError="continueRegularOutput", alwaysOutputData=True)
    w.add("Settings Object", "n8n-nodes-base.code", 2, code_params(SETTINGS_OBJECT_JS), (660, 360))
    w.add("Check Functions", "n8n-nodes-base.httpRequest", 4.2, http(
        "POST", f"={{{{ {SB} }}}}/rest/v1/rpc/register_message",
        "={{ JSON.stringify({ p_session_id: 'setup-check-' + Date.now(), p_channel: 'test', "
        "p_text: 'Setup check', p_is_test: true }) }}", cred_type="supabaseApi"),
        (880, 360), creds=["supabase"], onError="continueRegularOutput", executeOnce=True)
    w.add("Check Model", "n8n-nodes-base.httpRequest", 4.2, gemini_http(
        f"={{{{ {GM} }}}}/models/{{{{ $('Settings Object').first().json.settings.model }}}}:generateContent",
        "={{ JSON.stringify($('Settings Object').first().json.model_body) }}", timeout=60000),
        (1100, 360), creds=["gemini"], onError="continueRegularOutput", executeOnce=True)
    w.add("Check Embeddings", "n8n-nodes-base.httpRequest", 4.2, gemini_http(
        f"={{{{ {GM} }}}}/models/{{{{ $('Settings Object').first().json.settings.embedding_model }}}}:embedContent",
        "={{ JSON.stringify($('Settings Object').first().json.embed_body) }}", timeout=30000),
        (1320, 360), creds=["gemini"], onError="continueRegularOutput", executeOnce=True)
    w.add("Check Knowledge Base", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", f"={{{{ {SB} }}}}/rest/v1/kb_files?select=file_id,title,chunk_count", cred_type="supabaseApi"),
        (1540, 360), creds=["supabase"], onError="continueRegularOutput", alwaysOutputData=True, executeOnce=True)
    w.add("Check Drive Folder", "n8n-nodes-base.googleDrive", 3, {
        "authentication": "serviceAccount",
        "resource": "fileFolder",
        "searchMethod": "query",
        "queryString": "",
        "returnAll": True,
        "filter": {
            "folderId": rl("={{ $('Settings Object').first().json.settings.drive_folder_id }}", "id"),
            "whatToSearch": "files",
            "fileTypes": [GOOGLE_DOC_MIME],
            "includeTrashed": False,
        },
        "options": {},
    }, (1760, 360), creds=["google"], onError="continueRegularOutput", alwaysOutputData=True, executeOnce=True)
    w.add("Check Sheet", "n8n-nodes-base.googleSheets", 4.7, {
        "authentication": "serviceAccount",
        "operation": "read",
        "documentId": rl("={{ $('Settings Object').first().json.settings.sheet_id }}", "id"),
        "sheetName": rl("conversations", "name"),
        "options": {},
    }, (1980, 360), creds=["google"], onError="continueRegularOutput", alwaysOutputData=True, executeOnce=True)
    w.add("Collect Results", "n8n-nodes-base.code", 2, code_params(code("00_collect_results.js")), (2200, 360))
    w.add("Post Results", "n8n-nodes-base.slack", 2.3, slack_post(
        "={{ $('Settings Object').first().json.settings.slack_channel }}", "={{ $json.slack_text }}"),
        (2420, 360), creds=["slack"], onError="continueRegularOutput")
    w.chain("Run Check", "Config", "Read Settings", "Settings Object", "Check Functions", "Check Model",
            "Check Embeddings", "Check Knowledge Base", "Check Drive Folder", "Check Sheet", "Collect Results",
            "Post Results")
    return w.to_json(settings())


# =====================================================================
# 99 - Test Runner
# =====================================================================
RUNNER_SETTINGS_JS = r"""// Runner Settings: where results go (same sheet as the conversation log, tabs test_results and test_runs).
const rows = $input.all().map((i) => i.json).filter((j) => j && j.key);
const s = Object.fromEntries(rows.map((r) => [r.key, r.value]));
return [{ json: { sheet_id: s.sheet_id || '', slack_channel: s.slack_channel || '', has_sheet: /^[A-Za-z0-9_-]{20,}$/.test(String(s.sheet_id || '')) } }];
"""


def build_tests():
    w = Workflow("tests")
    cases = load_cases()
    cases_json = json.dumps(cases, ensure_ascii=False)
    w.sticky("About", f"## 99 - Test Runner\n{len(cases)} scripted conversations in groups A, B and C "
             "(run one group at a time, or list case IDs; the pause between turns keeps inside Gemini's free-tier limits). Each case gets its own session and runs through "
             "20 - Answer Message in dry-run mode, so handoffs are built but nothing is sent. Results go to the "
             "test_results and test_runs tabs and to Slack.", (-40, 0), 620, 200, 4)
    w.add("Run Tests", "n8n-nodes-base.manualTrigger", 1, {}, (0, 360))
    w.add("Run Options", "n8n-nodes-base.set", 3.4, set_params([
        ("group", "A", "string"),
        ("case_ids", "", "string"),
        ("run_id", "={{ $now.toFormat('yyyyLLdd-HHmmss') }}", "string"),
        ("pause_seconds", 4, "number"),
    ]), (220, 360))
    w.add("Config", "n8n-nodes-base.set", 3.4, set_params([("supabase_url", LIVE["supabase_url"], "string")]), (440, 360))
    w.add("Read Settings", "n8n-nodes-base.httpRequest", 4.2, http(
        "GET", "={{ $json.supabase_url }}/rest/v1/bot_settings?select=key,value", cred_type="supabaseApi"),
        (660, 360), creds=["supabase"], **RETRY)
    w.add("Runner Settings", "n8n-nodes-base.code", 2, code_params(RUNNER_SETTINGS_JS), (880, 360))
    w.add("Test Turns", "n8n-nodes-base.code", 2, code_params(code("99_test_turns.js", {"__TEST_CASES__": cases_json})),
          (1100, 360))
    w.add("Loop Turns", "n8n-nodes-base.splitInBatches", 3, {"batchSize": 1, "options": {}}, (1320, 360))
    w.add("Call Answer", "n8n-nodes-base.executeWorkflow", 1.2, ref("answer", wait=True), (1540, 460),
          onError="continueRegularOutput")
    w.add("Record Turn", "n8n-nodes-base.code", 2, code_params(code("99_record_turn.js")), (1760, 460))
    w.add("Pause", "n8n-nodes-base.wait", 1.1, {"amount": "={{ $('Run Options').first().json.pause_seconds }}", "unit": "seconds"},
          (1980, 460), webhookId=uid("tests", "pause-webhook"))
    w.add("Score Cases", "n8n-nodes-base.code", 2, code_params(code("99_score_cases.js", {"__TEST_CASES__": cases_json})),
          (1540, 220))
    w.add("Write Results", "n8n-nodes-base.googleSheets", 4.7, {
        "authentication": "serviceAccount",
        "operation": "append",
        "documentId": rl("={{ $('Runner Settings').first().json.sheet_id }}", "id"),
        "sheetName": rl("test_results", "name"),
        "columns": sheet_columns(TEST_RESULT_COLUMNS),
        "options": {"cellFormat": "RAW", "handlingExtraData": "ignoreIt"},
    }, (1760, 220), creds=["google"], onError="continueRegularOutput", **RETRY_SLOW)
    w.add("Run Summary", "n8n-nodes-base.code", 2, code_params(code("99_run_summary.js")), (1980, 220))
    w.add("Write Run", "n8n-nodes-base.googleSheets", 4.7, {
        "authentication": "serviceAccount",
        "operation": "append",
        "documentId": rl("={{ $('Runner Settings').first().json.sheet_id }}", "id"),
        "sheetName": rl("test_runs", "name"),
        "columns": sheet_columns(TEST_RUN_COLUMNS),
        "options": {"cellFormat": "RAW", "handlingExtraData": "ignoreIt"},
    }, (2200, 220), creds=["google"], onError="continueRegularOutput", **RETRY_SLOW)
    w.add("Post Summary", "n8n-nodes-base.slack", 2.3, slack_post(
        "={{ $('Runner Settings').first().json.slack_channel }}", "={{ $('Run Summary').first().json.slack_text }}"),
        (2420, 220), creds=["slack"], onError="continueRegularOutput")
    w.chain("Run Tests", "Run Options", "Config", "Read Settings", "Runner Settings", "Test Turns", "Loop Turns")
    w.connect("Loop Turns", "Score Cases", 0)
    w.connect("Loop Turns", "Call Answer", 1)
    w.chain("Call Answer", "Record Turn", "Pause", "Loop Turns")
    w.chain("Score Cases", "Write Results", "Run Summary", "Write Run", "Post Summary")
    return w.to_json(settings())


# =====================================================================

BUILDERS = {
    "errors": ("90-error-alerts.json", build_errors),
    "escalate": ("30-escalate-to-team.json", build_escalate),
    "answer": ("20-answer-message.json", build_answer),
    "web": ("10-website-chat.json", build_web),
    "whatsapp": ("11-whatsapp.json", build_whatsapp),
    "sync": ("40-sync-knowledge-base.json", build_sync),
    "setup": ("00-setup-check.json", build_setup),
    "tests": ("99-test-runner.json", build_tests),
}


def patch_live(wf):
    """Real credential IDs; drop our workflow ID so the import assigns its own."""
    creds = LIVE.get("credentials", {})
    for node in wf["nodes"]:
        for ctype, refd in (node.get("credentials") or {}).items():
            name = refd["name"]
            if name in creds:
                refd["id"] = creds[name]["id"]
                refd["name"] = creds[name].get("name", name)
    wf.pop("id", None)
    return wf


def main():
    keys = [a for a in sys.argv[1:] if not a.startswith("--")] or list(BUILDERS)
    for key in keys:
        fname, fn = BUILDERS[key]
        wf = fn()
        if not (PLACEHOLDERS or LOCAL):
            wf = patch_live(wf)
        write(OUT_DIR / fname, wf)
        print("wrote", (OUT_DIR / fname).relative_to(ROOT), f"({len(wf['nodes'])} nodes)")


if __name__ == "__main__":
    main()
