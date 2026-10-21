// Merge Sources: combines both searches, keeps the best score per chunk, labels the top chunks
// S1..Sn and builds the model request. The provider setting picks the request shape:
// gemini (generateContent with a response schema) or openai (Responses API with a JSON schema).
const p = $('Prepare Turn').first().json;
const S = p.settings;
const N = p.num;
const SCHEMA = __RESPONSE_SCHEMA__;
const GEMINI_SCHEMA = __GEMINI_SCHEMA__;

// Rows come from the match_documents function: { id, content, metadata, similarity }.
const rows = $input.all()
  .map((i) => i.json)
  .filter((j) => j && typeof j.content === 'string' && j.content.length);

// match_documents returns its top matches whenever the knowledge base has content, so no rows at all
// means the knowledge base is empty. The next node routes this to the fallback reply and an alert.
if (!rows.length) {
  return [{ json: { search_failed: true, error: { message: 'Knowledge base search returned no rows: the knowledge base is empty or the search failed.' } } }];
}

const best = new Map();
for (const r of rows) {
  const md = r.metadata || {};
  const key = `${md.file_id || md.title || ''}|${r.content.slice(0, 200)}`;
  const seen = best.get(key);
  if (!seen || (r.similarity ?? 0) > (seen.similarity ?? 0)) best.set(key, r);
}

const top = [...best.values()]
  .sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0))
  .slice(0, N.max_sources);

const sources = top.map((r, i) => {
  const md = r.metadata || {};
  return {
    label: `S${i + 1}`,
    title: md.title || 'Help article',
    file_id: md.file_id || null,
    url: md.url || null,
    score: Math.round((r.similarity ?? 0) * 1000) / 1000,
    text: r.content,
  };
});
const bestScore = sources.length ? sources[0].score : 0;

const sourcesBlock = sources.length
  ? sources.map((s) => `[${s.label}] ${s.title}\n${s.text}`).join('\n\n')
  : '(No help articles matched this message.)';

const stateText = {
  bot: 'normal conversation',
  collecting_contact: "waiting for the customer's name and email address so a person on the team can follow up",
  handed_off: 'this conversation has already been passed to a person on the team',
}[p.conversation.status] || 'normal conversation';

const today = new Date().toISOString().slice(0, 10);
const system = String(S.system_prompt || '')
  .split('{{state}}').join(stateText)
  .split('{{today}}').join(today)
  .split('{{channel}}').join(p.input.channel === 'whatsapp' ? 'WhatsApp' : 'website chat');
const sourcesMessage = `SOURCES (the only facts you may use):\n\n${sourcesBlock}`;

const history = p.history
  .filter((h) => h && h.content)
  .map((h) => ({ role: h.role === 'assistant' ? 'assistant' : 'user', content: String(h.content).slice(0, 1500) }));

const provider = String(S.provider || 'gemini').toLowerCase();
let body;
if (provider === 'openai') {
  body = {
    model: S.model,
    input: [
      { role: 'system', content: system },
      { role: 'system', content: sourcesMessage },
      ...history,
      { role: 'user', content: p.input.text },
    ],
    max_output_tokens: N.max_output_tokens,
    text: { format: { type: 'json_schema', name: 'support_reply', strict: true, schema: SCHEMA } },
  };
  if (S.reasoning_effort) body.reasoning = { effort: S.reasoning_effort };
} else {
  // Gemini wants alternating user and model turns that start with the user.
  const contents = [];
  for (const h of history) {
    const role = h.role === 'assistant' ? 'model' : 'user';
    if (!contents.length && role === 'model') continue;
    const last = contents[contents.length - 1];
    if (last && last.role === role) last.parts[0].text += `\n${h.content}`;
    else contents.push({ role, parts: [{ text: h.content }] });
  }
  const last = contents[contents.length - 1];
  if (last && last.role === 'user') last.parts[0].text += `\n${p.input.text}`;
  else contents.push({ role: 'user', parts: [{ text: p.input.text }] });
  body = {
    systemInstruction: { parts: [{ text: `${system}\n\n${sourcesMessage}` }] },
    contents,
    generationConfig: {
      temperature: 0,
      maxOutputTokens: N.max_output_tokens,
      responseMimeType: 'application/json',
      responseSchema: GEMINI_SCHEMA,
    },
  };
}

return [{
  json: {
    search_failed: false,
    provider,
    model: S.model,
    request_body: body,
    sources: sources.map(({ text, ...rest }) => rest),
    sources_text: Object.fromEntries(sources.map((s) => [s.label, s.text])),
    best_score: bestScore,
  },
}];
