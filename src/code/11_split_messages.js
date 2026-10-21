// Split Messages: one item per incoming WhatsApp message. Status updates are ignored.
// Text messages go to the assistant; other types (voice notes, images) get a short reply.
const out = [];
for (const item of $input.all()) {
  const ev = item.json || {};
  const phoneNumberId = ev.metadata && ev.metadata.phone_number_id;
  const contacts = Array.isArray(ev.contacts) ? ev.contacts : [];
  for (const msg of ev.messages || []) {
    const contact = contacts.find((c) => c.wa_id === msg.from) || contacts[0] || {};
    out.push({
      json: {
        kind: msg.type === 'text' ? 'text' : 'other',
        message_type: msg.type,
        channel: 'whatsapp',
        session_id: `wa:${msg.from}`,
        text: msg.type === 'text' ? String((msg.text && msg.text.body) || '') : '',
        contact_phone: `+${msg.from}`,
        recipient: msg.from,
        contact_name: (contact.profile && contact.profile.name) || null,
        external_id: msg.id || null,
        phone_number_id: phoneNumberId || null,
        is_test: false,
        dry_run: false,
      },
    });
  }
}
return out;
