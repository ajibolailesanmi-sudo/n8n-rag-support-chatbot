// Store Down Reply: Supabase could not be reached, so there are no settings and nothing can be
// logged. The customer still gets a reply and the team is alerted.
const cfg = $('Config').first().json;
const err = $input.first().json || {};
const message = (err.error && (err.error.message || err.error.description)) || err.message || 'Unknown error';
return [{
  json: {
    output: cfg.store_down_text,
    reply: cfg.store_down_text,
    skip: false,
    answer_status: 'error',
    action: 'none',
    reason: null,
    status: null,
    cited: [],
    sources: [],
    best_score: null,
    flags: { error: String(message).slice(0, 500), failed_node: 'Register Message' },
    session_id: cfg.session_id,
    phone_number_id: cfg.phone_number_id || null,
    alert: {
      workflow: '20 - Answer Message',
      node: 'Register Message',
      message: String(message).slice(0, 500),
      session_id: cfg.session_id,
      is_test: !!cfg.is_test,
      execution_url: `${cfg.n8n_url}/workflow/${$workflow.id}/executions/${$execution.id}`,
    },
  },
}];
