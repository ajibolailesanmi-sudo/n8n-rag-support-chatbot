"""Small helpers for building n8n workflow JSON (adapted from the lead router build)."""
import json
import os
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE_DIR = ROOT / "src" / "code"
NS = uuid.UUID("2b7a6c1e-49f0-4a8d-8a61-5c0e9d3f7b21")

# Credential references. Repo files use these names and placeholder IDs; scripts/patch_live.py
# swaps in the real IDs from scripts/live-ids.json (not committed) before importing to n8n.
CREDS = {
    "gemini": {"httpHeaderAuth": {"id": "scGeminiHdrCred1", "name": "Gemini - Support Chatbot"}},
    "openai": {"openAiApi": {"id": "scOpenAiCred0001", "name": "OpenAI - Support Chatbot"}},
    "supabase": {"supabaseApi": {"id": "scSupabaseCred01", "name": "Supabase - Support Chatbot"}},
    "google": {"googleApi": {"id": "scGoogleSACred01", "name": "Google Service Account"}},
    "slack": {"slackApi": {"id": "scSlackCred00001", "name": "Slack Bot"}},
    "smtp": {"smtp": {"id": "scSmtpCred000001", "name": "SMTP"}},
    "wa_trigger": {"whatsAppTriggerApi": {"id": "scWaTriggerCred1", "name": "WhatsApp OAuth - Support Chatbot"}},
    "wa_api": {"whatsAppApi": {"id": "scWaApiCred00001", "name": "WhatsApp API - Support Chatbot"}},
}

WF_IDS = {
    "setup": "scSetupCheck0000",
    "web": "scWebsiteChat000",
    "whatsapp": "scWhatsApp000000",
    "answer": "scAnswerMessage0",
    "escalate": "scEscalate000000",
    "sync": "scSyncKnowledge0",
    "errors": "scErrorAlerts000",
    "tests": "scTestRunner0000",
}
WF_NAMES = {
    "setup": "00 - Setup Check",
    "web": "10 - Website Chat",
    "whatsapp": "11 - WhatsApp",
    "answer": "20 - Answer Message",
    "escalate": "30 - Escalate to Team",
    "sync": "40 - Sync Knowledge Base",
    "errors": "90 - Error Alerts",
    "tests": "99 - Test Runner",
}

RETRY = {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}
RETRY_SLOW = {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 5000}


def uid(*parts):
    return str(uuid.uuid5(NS, "|".join(parts)))


def code(filename, replacements=None):
    src = (CODE_DIR / filename).read_text()
    for k, v in (replacements or {}).items():
        if k not in src:
            raise SystemExit(f"placeholder {k} not found in {filename}")
        src = src.replace(k, v)
    return src


class Workflow:
    def __init__(self, key):
        self.key = key
        self.nodes = []
        self.connections = {}

    def add(self, name, type_, version, params, pos, creds=None, **extra):
        if any(n["name"] == name for n in self.nodes):
            raise SystemExit(f"duplicate node name {name} in {self.key}")
        node = {
            "parameters": params,
            "id": uid(self.key, name),
            "name": name,
            "type": type_,
            "typeVersion": version,
            "position": list(pos),
        }
        if creds:
            node["credentials"] = {}
            for c in creds:
                node["credentials"].update(CREDS[c])
        node.update(extra)
        self.nodes.append(node)
        return name

    def sticky(self, name, content, pos, width, height, color=7):
        self.nodes.append({
            "parameters": {"content": content, "height": height, "width": width, "color": color},
            "id": uid(self.key, "sticky", name),
            "name": name,
            "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1,
            "position": list(pos),
        })

    def connect(self, src, dst, out=0, inp=0, kind="main"):
        conns = self.connections.setdefault(src, {}).setdefault(kind, [])
        while len(conns) <= out:
            conns.append([])
        conns[out].append({"node": dst, "type": kind, "index": inp})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.connect(a, b)

    def to_json(self, settings):
        names = {n["name"] for n in self.nodes}
        for src, kinds in self.connections.items():
            if src not in names:
                raise SystemExit(f"{self.key}: connection from unknown node {src}")
            for outs in kinds.values():
                for out in outs:
                    for c in out:
                        if c["node"] not in names:
                            raise SystemExit(f"{self.key}: connection to unknown node {c['node']}")
        return {
            "name": WF_NAMES[self.key],
            "nodes": self.nodes,
            "connections": self.connections,
            "active": False,
            "settings": settings,
            "versionId": uid(self.key, "version"),
            "id": WF_IDS[self.key],
            "meta": {"templateCredsSetupCompleted": False},
            "pinData": {},
            "tags": [],
        }


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------- parameter helpers ----------

def rl(value, mode, **extra):
    d = {"__rl": True, "value": value, "mode": mode}
    d.update(extra)
    return d


def set_params(fields, include_other=False):
    """fields: list of (name, value, type)."""
    return {
        "mode": "manual",
        "assignments": {"assignments": [
            {"id": uid("assign", name, str(value)), "name": name, "value": value, "type": t}
            for name, value, t in fields
        ]},
        "includeOtherFields": include_other,
        "options": {},
    }


def if_params(expression):
    """IF condition: a single boolean expression that must be true."""
    return {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": uid("cond", expression),
                "leftValue": expression,
                "rightValue": "",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "looseTypeValidation": True,
        "options": {},
    }


def switch_params(value_expr, outputs):
    """Switch on a string value; outputs: list of (output_name, equals_value)."""
    rules = []
    for out_name, equals in outputs:
        rules.append({
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [{
                    "id": uid("switch", out_name, equals),
                    "leftValue": value_expr,
                    "rightValue": equals,
                    "operator": {"type": "string", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": out_name,
        })
    return {"rules": {"values": rules}, "options": {}}


def code_params(js, mode=None):
    p = {"jsCode": js}
    if mode:
        p["mode"] = mode
    return p


def http(method, url, body_expr=None, cred_type=None, options=None, headers=None, query=None):
    p = {"method": method, "url": url}
    if cred_type:
        p["authentication"] = "predefinedCredentialType"
        p["nodeCredentialType"] = cred_type
    if headers:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers]}
    if query:
        p["sendQuery"] = True
        p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query]}
    if body_expr is not None:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_expr
    p["options"] = options or {}
    return p


def slack_post(channel_expr, text_expr):
    return {
        "authentication": "accessToken",
        "select": "channel",
        "channelId": rl(channel_expr, "id"),
        "text": text_expr,
        "otherOptions": {"includeLinkToWorkflow": False, "unfurl_links": False, "mrkdwn": True},
    }


def email_send(from_expr, to_expr, subject_expr, html_expr, reply_to=None):
    opts = {"appendAttribution": False}
    if reply_to:
        opts["replyTo"] = reply_to
    return {
        "fromEmail": from_expr,
        "toEmail": to_expr,
        "subject": subject_expr,
        "emailFormat": "html",
        "html": html_expr,
        "options": opts,
    }


def sheet_columns(columns, matching=None):
    schema = [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True,
               "type": "string", "canBeUsedToMatch": True} for c in columns]
    return {
        "mappingMode": "autoMapInputData",
        "value": {},
        "matchingColumns": matching or [],
        "schema": schema,
        "attemptToConvertTypes": False,
        "convertFieldsToString": True,
    }


def exec_ref(key, wait=True):
    return {
        "workflowId": rl(WF_IDS[key], "list", cachedResultName=WF_NAMES[key], cachedResultUrl=f"/workflow/{WF_IDS[key]}"),
        "workflowInputs": {"mappingMode": "defineBelow", "value": {}, "matchingColumns": [], "schema": [],
                           "attemptToConvertTypes": False, "convertFieldsToString": True},
        "mode": "once",
        "options": {"waitForSubWorkflow": wait},
    }
