// Apply Rules: reads the model's JSON, checks that an answer is grounded in the retrieved
// articles, applies the escalation rules from bot_settings and writes the final reply.
// The model suggests; this node decides. Handoff replies come from editable templates.
const p = $('Prepare Turn').first().json;
const ms = $('Merge Sources').first().json;
const res = $input.first().json;
const S = p.settings;
const N = p.num;
const conv = p.conversation || {};
const channel = p.input.channel;
const text = p.input.text;
const flags = {};

// ---------- 1. Read the model output (Gemini or OpenAI) ----------
function outputText(r) {
  if (Array.isArray(r.candidates)) {
    const cand = r.candidates[0] || {};
    if (cand.finishReason && cand.finishReason !== 'STOP') flags.incomplete = cand.finishReason;
    if (r.promptFeedback && r.promptFeedback.blockReason) flags.blocked = r.promptFeedback.blockReason;
    const parts = (cand.content && cand.content.parts) || [];
    const texts = parts.filter((c) => typeof c.text === 'string' && !c.thought).map((c) => c.text);
    return texts.length ? texts.join('') : null;
  }
  if (typeof r.output_text === 'string') return r.output_text;
  for (const item of r.output || []) {
    if (item.type !== 'message') continue;
    for (const c of item.content || []) {
      if (c.type === 'output_text' && typeof c.text === 'string') return c.text;
      if (c.type === 'refusal') flags.model_refusal = String(c.refusal || '').slice(0, 200);
    }
  }
  return null;
}

const EMPTY = {
  reply: '', answer_status: 'not_in_kb', cited_sources: [], wants_human: false, declines_handoff: false,
  frustration: 'none', issue_type: 'other', contact_name: null, contact_email: null, injection_detected: false,
};
let m = null;
const raw = outputText(res);
try {
  m = raw ? JSON.parse(raw) : null;
} catch (e) {
  flags.parse_error = String(e.message).slice(0, 200);
}
if (!m || typeof m !== 'object') {
  flags.unreadable = true;
  m = { ...EMPTY };
}
if (res.status === 'incomplete') flags.incomplete = (res.incomplete_details && res.incomplete_details.reason) || 'incomplete';
m.reply = String(m.reply || '').trim();

// ---------- 2. Grounding check ----------
const labels = ms.sources.map((s) => s.label);
const citedRaw = Array.isArray(m.cited_sources) ? m.cited_sources : [];
const cited = [...new Set(citedRaw.filter((l) => labels.includes(l)))];
const badCites = citedRaw.filter((l) => !labels.includes(l));
let status = m.answer_status;

if (status === 'answered') {
  if (!cited.length) flags.no_citation = true;
  if (badCites.length) flags.invalid_citation = badCites;
  if (ms.best_score < N.min_similarity) flags.low_similarity = ms.best_score;
  if (flags.no_citation || flags.invalid_citation || flags.low_similarity !== undefined) {
    status = 'not_in_kb';
    flags.grounding_override = true;
  }
}

// Numbers in an answer should appear in the cited articles (or in the customer's own message).
const numberMode = String(S.number_check || 'flag').toLowerCase();
if (status === 'answered' && numberMode !== 'off') {
  const numbersIn = (s) => new Set((String(s).replace(/(\d),(\d{3})/g, '$1$2').match(/\d+(?:\.\d+)?/g)) || []);
  const allowed = numbersIn(cited.map((l) => ms.sources_text[l] || '').join(' ') + ' ' + text);
  const replyNoLists = m.reply.replace(/^\s*\d+[.)]\s/gm, '');
  const unsupported = [...numbersIn(replyNoLists)].filter((n) => !allowed.has(n));
  if (unsupported.length) {
    flags.unsupported_numbers = unsupported;
    if (numberMode === 'block') {
      status = 'not_in_kb';
      flags.grounding_override = true;
    }
  }
}
if (status === 'not_in_kb') flags.not_sure = true;

// ---------- 3. Escalation signals ----------
const lower = text.toLowerCase();
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const keywords = String(S.handoff_keywords || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
const keywordHit = keywords.find((k) => new RegExp(`(^|[^a-z])${escapeRe(k)}([^a-z]|$)`).test(lower)) || null;

const injection = !!m.injection_detected;
if (injection) flags.injection = true;

const askedRule = String(S.escalate_when_asked || 'yes').toLowerCase() === 'yes';
const keywordCounts = keywordHit && (status !== 'answered' || text.length < 80);
const wantsHuman = askedRule && !injection && (m.wants_human === true || !!keywordCounts);
if (keywordCounts && m.wants_human !== true) flags.keyword_handoff = keywordHit;

const rank = { none: 0, mild: 1, high: 2 };
const frustrationRule = String(S.escalate_when_frustrated || 'high').toLowerCase();
const threshold = frustrationRule in rank ? rank[frustrationRule] : 99;
const frustrated = !injection && threshold > 0 && threshold < 99 && (rank[m.frustration] || 0) >= threshold;

const outsideRule = String(S.escalate_when_not_in_kb || 'yes').toLowerCase() === 'yes';
const outside = status === 'not_in_kb' && outsideRule && !injection;

let reason = wantsHuman ? 'asked_for_person' : frustrated ? 'frustrated' : outside ? 'outside_kb' : null;

// ---------- 4. Contact details (only if the customer actually wrote them) ----------
const customerText = [text, ...p.history.filter((h) => h.role === 'user').map((h) => String(h.content))]
  .join('\n').toLowerCase();
const emailRe = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i;
const asEmail = (v) => {
  const hit = typeof v === 'string' ? v.match(emailRe) : null;
  const e = hit ? hit[0].toLowerCase() : null;
  return e && customerText.includes(e) ? e : null;
};
const newEmail = asEmail(m.contact_email) || asEmail(text);
const email = newEmail || conv.contact_email || null;

let newName = null;
if (typeof m.contact_name === 'string' && m.contact_name.trim()) {
  const candidate = m.contact_name.trim().slice(0, 80);
  if (customerText.includes(candidate.toLowerCase().split(' ')[0])) newName = candidate;
}
const name = newName || conv.contact_name || null;
const phone = conv.contact_phone || null;
const reachable = !!email || (channel === 'whatsapp' && !!phone);

// ---------- 5. Decide the reply and the action ----------
const fill = (t) => String(t || '').split('{{email}}').join(email || '').split('{{name}}').join(name || '');
const prefixFor = (r) => (r === 'frustrated' ? S.prefix_frustrated || '' : r === 'outside_kb' ? S.prefix_outside_kb || '' : '');
const firstName = name ? String(name).split(' ')[0] : null;
const thanks = firstName ? `Thanks, ${firstName}. ` : 'Thanks. ';
const handoffText = () => (email
  ? fill(S.handoff_email_text)
  : channel === 'whatsapp' && phone ? fill(S.handoff_phone_text) : fill(S.handoff_no_contact_text));
const answerPart = status === 'answered' && m.reply ? `${m.reply} ` : '';

let reply = m.reply;
let action = 'none';
const state = {};
const current = conv.status || 'bot';
const pending = conv.pending_reason || null;
const asks = conv.contact_asks || 0;

if (current === 'handed_off') {
  if (reason) {
    action = 'handoff_followup';
    reply = answerPart + (reason === 'outside_kb' ? prefixFor(reason) : '') + fill(S.already_handed_off_text);
  } else if (status === 'not_in_kb') {
    reply = fill(S.not_sure_text);
  }
} else if (current === 'collecting_contact') {
  if (m.declines_handoff === true && !wantsHuman) {
    reply = fill(S.declined_text);
    state.status = 'bot';
    state.pending_reason = null;
    state.contact_asks = 0;
    reason = null;
  } else if (reachable) {
    action = 'handoff_now';
    reason = pending || reason || 'asked_for_person';
    reply = (newEmail ? thanks : '') + answerPart + handoffText();
  } else if (asks >= N.max_contact_asks) {
    action = 'handoff_now';
    reason = pending || reason || 'asked_for_person';
    reply = answerPart + fill(S.handoff_no_contact_text);
  } else {
    state.contact_asks = asks + 1;
    reply = answerPart + fill(S.reask_email_text);
    reason = null;
  }
} else if (reason) {
  if (reachable) {
    action = 'handoff_now';
    reply = (newEmail && firstName ? thanks : '') + answerPart + prefixFor(reason) + handoffText();
  } else {
    action = 'ask_contact';
    state.status = 'collecting_contact';
    state.pending_reason = reason;
    state.contact_asks = 1;
    reply = answerPart + prefixFor(reason) + fill(S.ask_contact_text);
  }
} else if (status === 'not_in_kb') {
  reply = fill(S.not_sure_text);
}

if (!reply) reply = fill(S.not_sure_text);

// ---------- 6. Conversation changes for log_reply ----------
if (newEmail) state.contact_email = newEmail;
if (newName) state.contact_name = newName;
if (m.issue_type && m.issue_type !== 'other') state.issue_type = m.issue_type;
else if (!conv.issue_type && m.issue_type) state.issue_type = 'other';
if (status === 'not_in_kb') state.not_sure_inc = 1;

const usage = res.usage || (res.usageMetadata
  ? { input_tokens: res.usageMetadata.promptTokenCount, output_tokens: res.usageMetadata.candidatesTokenCount }
  : {});
return [{
  json: {
    session_id: p.input.session_id,
    channel,
    is_test: p.input.is_test,
    dry_run: p.input.dry_run,
    phone_number_id: p.input.phone_number_id,
    reply: reply.replace(/\s+\n/g, '\n').trim(),
    answer_status: status,
    model_answer_status: m.answer_status,
    action,
    reason: action === 'none' ? null : reason,
    state,
    flags,
    retrieved: ms.sources,
    cited,
    best_score: ms.best_score,
    model: res.model || res.modelVersion || S.model || null,
    prompt_version: S.prompt_version || null,
    tokens_in: usage.input_tokens ?? null,
    tokens_out: usage.output_tokens ?? null,
    latency_ms: Date.now() - Number($('Config').first().json.started_ms || Date.now()),
    contact: { name, email, phone },
    issue_type: state.issue_type || conv.issue_type || null,
    frustration: m.frustration || 'none',
    latest_text: text,
    delivery: {
      slack_channel: S.slack_channel || null,
      team_email: S.team_email || null,
      from_email: S.from_email || null,
      sheet_id: S.sheet_id || null,
    },
  },
}];
