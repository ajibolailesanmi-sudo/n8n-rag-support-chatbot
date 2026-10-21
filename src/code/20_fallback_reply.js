// Fallback Reply: the knowledge base search or the model call failed after its retries.
// The customer gets a polite reply, the turn is logged, and the team is alerted.
const p = $('Prepare Turn').first().json;
const S = p.settings;
const conv = p.conversation || {};
const err = $input.first().json || {};
const message = (err.error && (err.error.message || err.error.description)) || err.message || 'Unknown error';
const failedNode = $('Ask Model').isExecuted ? 'Ask Model'
  : $('Search Knowledge Base').isExecuted ? 'Search Knowledge Base'
  : $('Embed Query').isExecuted ? 'Embed Query' : 'Search Queries';
const cfg = $('Config').first().json;

return [{
  json: {
    session_id: p.input.session_id,
    channel: p.input.channel,
    is_test: p.input.is_test,
    dry_run: p.input.dry_run,
    phone_number_id: p.input.phone_number_id,
    reply: S.fallback_text || 'Sorry, I am having trouble answering right now. Please try again in a few minutes.',
    answer_status: 'error',
    model_answer_status: null,
    action: 'none',
    reason: null,
    state: {},
    flags: { error: String(message).slice(0, 500), failed_node: failedNode },
    retrieved: [],
    cited: [],
    best_score: null,
    model: S.model || null,
    prompt_version: S.prompt_version || null,
    tokens_in: null,
    tokens_out: null,
    latency_ms: Date.now() - Number(cfg.started_ms || Date.now()),
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
    alert: {
      workflow: '20 - Answer Message',
      node: failedNode,
      message: String(message).slice(0, 500),
      session_id: p.input.session_id,
      is_test: p.input.is_test,
      execution_url: `${cfg.n8n_url}/workflow/${$workflow.id}/executions/${$execution.id}`,
    },
  },
}];
