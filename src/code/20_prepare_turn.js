// Prepare Turn: reads the register_message result and decides the route for this message.
// Routes: answer (normal), limit (a message cap was reached), duplicate (WhatsApp redelivery).
const reg = $input.first().json;
const input = $('Config').first().json;
const settings = reg.settings || {};

const num = (key, fallback) => {
  const v = parseFloat(settings[key]);
  return Number.isFinite(v) ? v : fallback;
};

let route = 'answer';
if (reg.duplicate) route = 'duplicate';
else if (!reg.allowed) route = 'limit';

return [{
  json: {
    route,
    limit_reason: reg.limit_reason || null,
    input: {
      channel: input.channel,
      session_id: input.session_id,
      text: String(input.text || '').trim().slice(0, 2000),
      is_test: !!input.is_test,
      dry_run: !!input.dry_run,
      phone_number_id: input.phone_number_id || null,
    },
    settings,
    num: {
      top_k: num('top_k', 4),
      max_sources: num('max_sources', 5),
      min_similarity: num('min_similarity', 0.3),
      max_output_tokens: num('max_output_tokens', 1200),
      max_contact_asks: num('max_contact_asks', 2),
    },
    conversation: reg.conversation || {},
    history: Array.isArray(reg.history) ? reg.history : [],
    previous_user_message: reg.previous_user_message || null,
  },
}];
