// Build Handoff: the Slack message and the email for the team, with the full transcript.
const inp = $('Config').first().json;
const claim = $input.first().json;
const c = claim.conversation || {};
const transcript = Array.isArray(claim.transcript) ? claim.transcript : [];

const reasonLabel = {
  asked_for_person: 'Customer asked for a person',
  frustrated: 'Customer seems frustrated',
  outside_kb: 'Question not covered by the help articles',
}[inp.reason] || String(inp.reason || 'Handoff');
const channelLabel = { web: 'Website chat', whatsapp: 'WhatsApp', test: 'Test' }[c.channel || inp.channel] || c.channel || inp.channel;
const who = [c.contact_name || 'Name not given', c.contact_email || 'no email given', c.contact_phone || null]
  .filter(Boolean)
  .join(' | ');

const lines = transcript.map((t) => `${t.role === 'user' ? 'Customer' : 'Assistant'}: ${String(t.content).replace(/\s+/g, ' ').trim()}`);
const transcriptText = lines.join('\n');

// Slack shows the latest lines that fit; the email always has everything.
const slackLines = [];
let used = 0;
for (let i = lines.length - 1; i >= 0; i--) {
  const line = `> ${lines[i].slice(0, 600)}`;
  if (used + line.length > 3000) {
    slackLines.unshift('> (earlier messages are in the email)');
    break;
  }
  slackLines.unshift(line);
  used += line.length + 1;
}

const slackText = [
  `*Chat handoff:* ${reasonLabel}`,
  `*Customer:* ${who}`,
  `*Channel:* ${channelLabel}    *Issue:* ${c.issue_type || 'not classified'}    *Customer messages:* ${c.message_count ?? ''}`,
  `*Session:* \`${c.session_id || inp.session_id}\``,
  '',
  '*Conversation*',
  ...slackLines,
].join('\n');

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const rows = transcript.map((t) => `
  <tr>
    <td style="padding:8px 12px;vertical-align:top;color:#5b6470;white-space:nowrap;font-weight:600">${t.role === 'user' ? 'Customer' : 'Assistant'}</td>
    <td style="padding:8px 12px;vertical-align:top;color:#101820">${esc(t.content).replace(/\n/g, '<br>')}</td>
  </tr>`).join('');

const html = `<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:680px;color:#101820">
  <p style="font-size:16px;margin:0 0 4px"><strong>Chat handoff:</strong> ${esc(reasonLabel)}</p>
  <p style="margin:0 0 16px;color:#5b6470">Reply to this email to reach the customer directly${c.contact_email ? '' : ' (no email address was given)'}.</p>
  <table style="border-collapse:collapse;margin-bottom:16px">
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Customer</td><td>${esc(c.contact_name || 'Name not given')}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Email</td><td>${esc(c.contact_email || 'not given')}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Phone</td><td>${esc(c.contact_phone || 'not given')}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Channel</td><td>${esc(channelLabel)}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Issue type</td><td>${esc(c.issue_type || 'not classified')}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#5b6470">Session</td><td>${esc(c.session_id || inp.session_id)}</td></tr>
  </table>
  <table style="border-collapse:collapse;width:100%;border-top:1px solid #dfe3e8">${rows}</table>
  <p style="margin-top:16px;color:#5b6470;font-size:12px">Sent by the support chat assistant. Solvant Labs demo build.</p>
</div>`;

const subject = `[Chat handoff] ${reasonLabel}: ${c.contact_name || c.contact_email || c.session_id || inp.session_id}`;

return [{
  json: {
    session_id: c.session_id || inp.session_id,
    slack_channel: inp.slack_channel,
    team_email: inp.team_email,
    from_email: inp.from_email,
    reply_to: c.contact_email || '',
    slack_text: slackText,
    subject,
    html,
    transcript_text: transcriptText,
    transcript_lines: lines.length,
  },
}];
