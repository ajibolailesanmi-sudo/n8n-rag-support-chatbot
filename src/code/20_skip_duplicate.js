// Skip Duplicate: WhatsApp delivered the same message twice; nothing is sent the second time.
const p = $('Prepare Turn').first().json;
return [{ json: { output: '', reply: '', skip: true, session_id: p.input.session_id, answer_status: 'duplicate', action: 'none' } }];
