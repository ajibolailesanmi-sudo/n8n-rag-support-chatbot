// Chunk Articles: splits each article into chunks of about chunk_size characters, breaking at
// headings first, then paragraphs, then lines, with an overlap so a fact split across two chunks
// is still found. Builds the batch embedding request for Gemini (one request per article).
const settings = $('Settings').first().json.settings || {};
const CHUNK = parseInt(settings.chunk_size, 10) || 900;
const OVERLAP = parseInt(settings.chunk_overlap, 10) || 120;
const DIMS = parseInt(settings.embedding_dimensions, 10) || 1536;
const MODEL = settings.embedding_model || 'gemini-embedding-001';

function splitRecursive(text, separators) {
  if (text.length <= CHUNK) return [text];
  const [sep, ...rest] = separators;
  if (sep === undefined) {
    const out = [];
    for (let i = 0; i < text.length; i += CHUNK) out.push(text.slice(i, i + CHUNK));
    return out;
  }
  const pieces = text.split(sep).map((s, i) => (i === 0 ? s : sep + s)).filter((s) => s.trim());
  const out = [];
  let current = '';
  for (const piece of pieces) {
    const candidate = current ? current + piece : piece;
    if (candidate.length <= CHUNK) {
      current = candidate;
      continue;
    }
    if (current) out.push(current);
    if (piece.length > CHUNK) {
      const sub = splitRecursive(piece, rest);
      out.push(...sub.slice(0, -1));
      current = sub[sub.length - 1];
    } else {
      current = piece;
    }
  }
  if (current) out.push(current);
  return out;
}

function withOverlap(chunks) {
  return chunks.map((c, i) => {
    if (i === 0 || OVERLAP <= 0) return c.trim();
    const prev = chunks[i - 1];
    const tail = prev.slice(Math.max(0, prev.length - OVERLAP));
    const cut = tail.search(/\s/);
    return ((cut >= 0 ? tail.slice(cut + 1) : tail) + '\n' + c).trim();
  });
}

// Remove Old Chunks outputs the delete responses, so the articles are read from Prepare Article.
const out = [];
for (const item of $('Prepare Article').all()) {
  const a = item.json;
  const pieces = withOverlap(splitRecursive(a.text, ['\n## ', '\n### ', '\n\n', '\n', ' ']));
  const chunks = pieces.filter((c) => c.length > 20);
  out.push({
    json: {
      ...a,
      chunks,
      embed_body: {
        requests: chunks.map((c) => ({
          model: `models/${MODEL}`,
          content: { parts: [{ text: `${a.title}\n${c}` }] },
          taskType: 'RETRIEVAL_DOCUMENT',
          title: a.title,
          outputDimensionality: DIMS,
        })),
      },
    },
  });
}
return out;
