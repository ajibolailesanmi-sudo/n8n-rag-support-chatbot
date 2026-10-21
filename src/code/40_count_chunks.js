// Count Chunks: one kb_files row per embedded article, with its chunk count.
const now = new Date().toISOString();
const rows = $('Build Rows').all().map((i) => i.json).map((a) => ({
  file_id: a.file_id,
  title: a.title,
  url: a.url,
  modified_time: a.modified_time,
  content_hash: a.hash,
  chunk_count: a.chunk_count,
  synced_at: now,
}));
return [{ json: { rows, chunks_written: rows.reduce((sum, r) => sum + r.chunk_count, 0) } }];
