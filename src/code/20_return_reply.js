// Return Reply: the result handed back to the channel workflow (and to the test runner).
const r = $('Reply Data').first().json;
const logged = $('Log Reply').isExecuted ? $('Log Reply').first().json || {} : {};
const c = logged.conversation || {};
const esc = $('Escalate').isExecuted ? $('Escalate').first().json : null;

let status = c.status || (r.state && r.state.status) || null;
if (esc && esc.claimed) status = 'handed_off';
if (logged.error) r.flags.log_error = String(logged.error.message || logged.error).slice(0, 300);

return [{
  json: {
    output: r.reply,
    reply: r.reply,
    skip: false,
    session_id: r.session_id,
    phone_number_id: r.phone_number_id || null,
    answer_status: r.answer_status,
    model_answer_status: r.model_answer_status,
    action: r.action,
    reason: r.reason,
    status,
    cited: r.cited || [],
    cited_titles: (r.retrieved || []).filter((s) => (r.cited || []).includes(s.label)).map((s) => s.title),
    sources: (r.retrieved || []).map((s) => ({ label: s.label, title: s.title, score: s.score })),
    best_score: r.best_score,
    flags: r.flags || {},
    contact: r.contact,
    issue_type: r.issue_type,
    frustration: r.frustration,
    escalation: esc
      ? {
        claimed: esc.claimed ?? null,
        sent_slack: esc.sent_slack ?? null,
        sent_email: esc.sent_email ?? null,
        dry_run: esc.dry_run ?? null,
        transcript_lines: esc.transcript_lines ?? null,
        transcript_text: esc.transcript_text ? String(esc.transcript_text).slice(0, 4000) : null,
        followup: esc.followup ?? null,
      }
      : null,
    model: r.model,
    prompt_version: r.prompt_version,
    tokens_in: r.tokens_in,
    tokens_out: r.tokens_out,
    latency_ms: r.latency_ms,
  },
}];
