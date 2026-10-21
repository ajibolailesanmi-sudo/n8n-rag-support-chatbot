// Limit Reply: a message cap was reached, so no search or model call is made.
const p = $('Prepare Turn').first().json;
const S = p.settings;
const conv = p.conversation || {};
return [{
  json: {
    session_id: p.input.session_id,
    channel: p.input.channel,
    is_test: p.input.is_test,
    dry_run: p.input.dry_run,
    phone_number_id: p.input.phone_number_id,
    reply: S.limit_text || 'This chat has reached its message limit. Please try again later.',
    answer_status: 'limit',
    model_answer_status: null,
    action: 'none',
    reason: null,
    state: {},
    flags: { limit_reason: p.limit_reason },
    retrieved: [],
    cited: [],
    best_score: null,
    model: null,
    prompt_version: S.prompt_version || null,
    tokens_in: null,
    tokens_out: null,
    latency_ms: Date.now() - Number($('Config').first().json.started_ms || Date.now()),
    contact: { name: conv.contact_name || null, email: conv.contact_email || null, phone: conv.contact_phone || null },
    issue_type: conv.issue_type || null,
    frustration: 'none',
    latest_text: p.input.text,
    delivery: {
      slack_channel: S.slack_channel || null,
      team_email: S.team_email || null,
      from_email: S.from_email || null,
      sheet_id: S.sheet_id || null,
    },
  },
}];
