// Log Row: one row per conversation in the Google Sheets log, updated after every reply.
// Column names match the header row of the "conversations" tab.
const r = $('Reply Data').first().json;
const logged = $('Log Reply').first().json || {};
const c = logged.conversation || {};
const esc = $('Escalate').isExecuted ? $('Escalate').first().json : null;

let status = c.status || (r.state && r.state.status) || 'bot';
if (esc && esc.claimed) status = 'handed_off';

const maskPhone = (ph) => (ph ? `${String(ph).slice(0, 2)}****${String(ph).slice(-4)}` : '');
const iso = (t) => (t ? new Date(t).toISOString().replace('T', ' ').slice(0, 19) : '');

return [{
  json: {
    session_id: r.session_id,
    started_at: iso(c.started_at),
    last_message_at: iso(c.last_message_at || Date.now()),
    channel: r.channel,
    status,
    handoff_reason: (esc && esc.claimed ? r.reason : c.handoff_reason) || '',
    name: c.contact_name || (r.contact && r.contact.name) || '',
    email: c.contact_email || (r.contact && r.contact.email) || '',
    phone: maskPhone(c.contact_phone),
    issue_type: c.issue_type || r.issue_type || '',
    messages: c.message_count || '',
    not_sure_count: c.not_sure_count ?? '',
    first_question: c.first_question || '',
    last_answer_status: r.answer_status || '',
    transcript: logged.transcript_text || '',
  },
}];
