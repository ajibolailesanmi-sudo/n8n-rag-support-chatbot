// Follow-up Message: the chat was already handed off, so the customer's new message goes into
// the same Slack thread instead of creating a second handoff.
const inp = $('Config').first().json;
const conv = $input.all().map((i) => i.json).find((j) => j && j.session_id) || {};
const text = `*Follow-up from the customer* (session \`${inp.session_id}\`)\n> ${String(inp.latest_text || '').slice(0, 1500)}`;
const body = { channel: inp.slack_channel, text, unfurl_links: false };
if (conv.slack_ts) body.thread_ts = String(conv.slack_ts);
return [{ json: { body, has_thread: !!conv.slack_ts } }];
