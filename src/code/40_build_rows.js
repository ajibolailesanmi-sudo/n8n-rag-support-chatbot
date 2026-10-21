// Build Rows: pairs each chunk with its embedding and prepares the rows for the documents table.
const articles = $('Chunk Articles').all().map((i) => i.json);
const out = [];
for (let i = 0; i < $input.all().length; i++) {
  const res = $input.all()[i].json || {};
  const a = articles[i];
  const embeddings = Array.isArray(res.embeddings) ? res.embeddings : [];
  if (!a) throw new Error(`No article for embedding result ${i}`);
  if (embeddings.length !== a.chunks.length) {
    throw new Error(`"${a.title}": ${a.chunks.length} chunks but ${embeddings.length} embeddings came back`);
  }
  const rows = a.chunks.map((content, idx) => ({
    content,
    metadata: { file_id: a.file_id, title: a.title, url: a.url, content_hash: a.hash, chunk_index: idx },
    embedding: embeddings[idx].values,
  }));
  out.push({ json: { file_id: a.file_id, title: a.title, url: a.url, modified_time: a.modified_time, hash: a.hash, rows, chunk_count: rows.length } });
}
return out;
