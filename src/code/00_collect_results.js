// Collect Results: one PASS/FAIL line per check, posted to Slack and returned.
const results = [];
const add = (name, ok, detail) => results.push({ check: name, result: ok ? 'PASS' : 'FAIL', detail: String(detail ?? '').slice(0, 300) });
const get = (node) => ($(node).isExecuted ? $(node).all().map((i) => i.json) : null);
const errOf = (rows) => {
  const e = rows && rows.find((r) => r && r.error);
  return e ? (e.error.message || e.error.description || JSON.stringify(e.error)).slice(0, 300) : null;
};

// 1. Settings
const settingsRows = get('Read Settings') || [];
const settingsErr = errOf(settingsRows);
const S = Object.fromEntries(settingsRows.filter((r) => r && r.key).map((r) => [r.key, r.value]));
const placeholders = ['team_email', 'from_email', 'sheet_id', 'drive_folder_id']
  .filter((k) => !S[k] || /example\.com|^YOUR_/i.test(S[k]));
const required = ['system_prompt', 'model', 'min_similarity', 'slack_channel', 'fallback_text'].filter((k) => !S[k]);
if (settingsErr) add('1. Settings table', false, settingsErr);
else add('1. Settings table', !placeholders.length && !required.length,
  placeholders.length || required.length
    ? `Still to set: ${[...required, ...placeholders].join(', ')}`
    : `${Object.keys(S).length} settings, prompt version ${S.prompt_version}`);

// 2. Database functions
const reg = (get('Check Functions') || [])[0] || {};
add('2. Database functions', !reg.error && reg.allowed === true,
  reg.error ? errOf([reg]) : `register_message answered (history ${Array.isArray(reg.history) ? reg.history.length : '?'} messages)`);

// 3. Model
const mod = (get('Check Model') || [])[0] || {};
let modelOk = false;
let modelDetail = '';
if (mod.error) modelDetail = errOf([mod]);
else {
  let txt = null;
  const cand = (mod.candidates || [])[0];
  if (cand && cand.content) txt = (cand.content.parts || []).map((c) => c.text || '').join('');
  for (const it of mod.output || []) for (const c of it.content || []) if (c.type === 'output_text') txt = c.text;
  try { modelOk = JSON.parse(txt).ok === true; } catch (e) { modelOk = false; }
  modelDetail = modelOk ? `${mod.modelVersion || mod.model || S.model} returned valid structured output` : `Unexpected output: ${String(txt).slice(0, 120)}`;
}
add('3. Model and structured output', modelOk, modelDetail);

// 4. Embeddings
const emb = (get('Check Embeddings') || [])[0] || {};
const expected = ($('Settings Object').first().json || {}).expected_dims || 1536;
const vec = (emb.embedding && emb.embedding.values) || (emb.data && emb.data[0] && emb.data[0].embedding) || [];
add('4. Embeddings', !emb.error && vec.length === expected,
  emb.error ? errOf([emb]) : vec.length === expected ? `${vec.length} dimensions` : `${vec.length} dimensions, table expects ${expected}`);

// 5. Knowledge base
const kb = (get('Check Knowledge Base') || []).filter((r) => r && r.file_id);
const kbErr = errOf(get('Check Knowledge Base'));
const chunks = kb.reduce((a, r) => a + (r.chunk_count || 0), 0);
add('5. Knowledge base loaded', !kbErr && kb.length > 0 && chunks > 0,
  kbErr || (kb.length ? `${kb.length} articles, ${chunks} chunks` : 'Empty: run 40 - Sync Knowledge Base'));

// 6. Drive folder
const drive = (get('Check Drive Folder') || []).filter((r) => r && r.id);
const driveErr = errOf(get('Check Drive Folder'));
add('6. Google Drive folder', !driveErr && drive.length > 0, driveErr || `${drive.length} Google Docs in the folder`);

// 7. Sheet
const sheet = (get('Check Sheet') || [])[0] || {};
add('7. Google Sheets log', !sheet.error, sheet.error ? errOf([sheet]) : 'conversations tab readable');

const passed = results.filter((r) => r.result === 'PASS').length;
const lines = results.map((r) => `${r.result === 'PASS' ? 'PASS' : 'FAIL'}  ${r.check}: ${r.detail}`);
const headline = passed === results.length ? `Setup check: all ${results.length} checks passed` : `Setup check: ${passed} of ${results.length} passed`;
return [{ json: { headline, passed, total: results.length, results, slack_text: `*${headline}*\n${lines.join('\n')}\n(Slack posting works if you can read this.)` } }];
