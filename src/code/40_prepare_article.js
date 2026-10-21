// Prepare Article: reads each exported Google Doc (Markdown), tidies it and fingerprints it.
const metas = $('Upsert Items').all().map((i) => i.json);
const items = $input.all();

// FNV-1a, 32-bit, twice with different seeds: enough to tell whether an article changed.
function fnv(str, seed) {
  let h = seed >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

const out = [];
for (let i = 0; i < items.length; i++) {
  const meta = metas[i] || {};
  let text = '';
  try {
    const buf = await this.helpers.getBinaryDataBuffer(i, 'data');
    text = buf.toString('utf8');
  } catch (e) {
    text = '';
  }
  // Google's Markdown export escapes characters (\$65) and bolds headings (# **Title**).
  text = text
    .replace(/\r\n/g, '\n')
    .replace(/\\([\\`*_{}\[\]()#+\-.!$|>~])/g, '$1')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\n\n(\* |\d+\. )/g, '\n$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  if (!text) continue;
  const fingerprint = fnv(`${meta.title}\n${text}`, 2166136261) + fnv(text, 33554467);
  out.push({ json: { ...meta, text, hash: fingerprint, chars: text.length } });
}
return out;
