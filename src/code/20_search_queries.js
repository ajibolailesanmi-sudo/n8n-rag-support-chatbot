// Search Queries: one search for the message itself, and one that adds the previous customer
// message so follow-ups like "does it include weekends?" still find the right article.
// Each item carries the embedding request for Gemini's embedContent endpoint.
const p = $('Prepare Turn').first().json;
const S = p.settings;
const dims = parseInt(S.embedding_dimensions, 10) || 1536;
const text = p.input.text;

const item = (query, kind) => ({
  json: {
    query,
    kind,
    embed_body: {
      content: { parts: [{ text: query }] },
      taskType: 'RETRIEVAL_QUERY',
      outputDimensionality: dims,
    },
  },
});

const queries = [item(text, 'message')];
const prev = (p.previous_user_message || '').trim();
if (prev && prev !== text) {
  queries.push(item(`${prev.slice(0, 500)}\n${text}`, 'with_previous'));
}
return queries;
