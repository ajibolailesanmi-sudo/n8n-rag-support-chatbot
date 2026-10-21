// Plan Sync: compares the Drive folder with the kb_files index.
// New or edited articles are re-embedded; articles removed from the folder are deleted.
const cfg = $('Settings').first().json;
const files = $('List Articles').all().map((i) => i.json).filter((j) => j && j.id && j.name);
const index = $('Get Index').all().map((i) => i.json).filter((j) => j && j.file_id);
const byId = Object.fromEntries(index.map((r) => [r.file_id, r]));
const sameTime = (a, b) => !!a && !!b && new Date(a).getTime() === new Date(b).getTime();

const upserts = [];
let unchanged = 0;
for (const f of files) {
  const known = byId[f.id];
  const changed = cfg.force || !known || !sameTime(known.modified_time, f.modifiedTime) || known.title !== f.name;
  if (changed) {
    upserts.push({
      file_id: f.id,
      title: f.name,
      url: f.webViewLink || `https://docs.google.com/document/d/${f.id}/edit`,
      modified_time: f.modifiedTime || null,
      is_new: !known,
    });
  } else {
    unchanged += 1;
  }
}

const inFolder = new Set(files.map((f) => f.id));
const deletes = index.filter((r) => !inFolder.has(r.file_id)).map((r) => ({ file_id: r.file_id, title: r.title }));
const quoted = (ids) => `(${ids.map((id) => `"${String(id).replace(/"/g, '')}"`).join(',')})`;

return [{
  json: {
    upserts,
    deletes,
    delete_filter: deletes.length ? encodeURIComponent(quoted(deletes.map((d) => d.file_id))) : null,
    unchanged,
    article_count: files.length,
    forced: !!cfg.force,
  },
}];
