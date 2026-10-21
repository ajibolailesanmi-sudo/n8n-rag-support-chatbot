// Format Error: turns either kind of failure into one alert.
// Unhandled: a workflow failed and n8n called this workflow through its Error Trigger.
// Handled: 20 - Answer Message caught a failure, replied to the customer and asked for an alert.
const cfg = $('Config').first().json;
let a;
if ($('Error Trigger').isExecuted) {
  const e = $('Error Trigger').first().json;
  const ex = e.execution || {};
  a = {
    kind: 'Workflow failed',
    workflow: (e.workflow && e.workflow.name) || 'Unknown workflow',
    node: ex.lastNodeExecuted || (ex.error && ex.error.node && ex.error.node.name) || 'unknown',
    message: (ex.error && (ex.error.message || ex.error.description)) || (e.trigger && e.trigger.error && e.trigger.error.message) || 'No error message',
    url: ex.url || null,
    session_id: null,
    is_test: false,
  };
} else {
  const h = $('When Called').first().json;
  const al = h.alert || h;
  a = {
    kind: 'Customer got the fallback reply',
    workflow: al.workflow || '20 - Answer Message',
    node: al.node || 'unknown',
    message: al.message || 'No error message',
    url: al.execution_url || null,
    session_id: al.session_id || null,
    is_test: !!al.is_test,
  };
}
const when = new Date().toLocaleString('en-US', { timeZone: cfg.timezone || 'America/New_York' });
const lines = [
  `*${a.kind}:* ${a.workflow}`,
  `*Node:* ${a.node}`,
  `*Error:* ${String(a.message).slice(0, 600)}`,
  a.session_id ? `*Session:* \`${a.session_id}\`${a.is_test ? ' (test)' : ''}` : null,
  a.url ? `*Execution:* ${a.url}` : null,
  `*When:* ${when}`,
].filter(Boolean);
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const html = `<div style="font-family:Inter,Segoe UI,Arial,sans-serif;color:#101820">
<p><strong>${esc(a.kind)}:</strong> ${esc(a.workflow)}</p>
<p>Node: ${esc(a.node)}<br>Error: ${esc(a.message)}<br>${a.session_id ? `Session: ${esc(a.session_id)}<br>` : ''}When: ${esc(when)}</p>
${a.url ? `<p><a href="${esc(a.url)}">Open the execution in n8n</a></p>` : ''}
<p style="color:#5b6470;font-size:12px">Sent by the support chat assistant's error workflow. Solvant Labs demo build.</p></div>`;
return [{ json: { ...a, slack_text: lines.join('\n'), subject: `[Chat assistant alert] ${a.workflow}: ${String(a.message).slice(0, 80)}`, html } }];
