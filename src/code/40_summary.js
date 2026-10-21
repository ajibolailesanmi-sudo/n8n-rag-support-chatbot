// Summary: what the sync did, for Slack and for the form's result page.
const plan = $('Plan Sync').first().json;
const counted = $('Count Chunks').isExecuted ? $('Count Chunks').first().json : { rows: [], chunks_written: 0 };
const added = plan.upserts.filter((u) => u.is_new).map((u) => u.title);
const updated = plan.upserts.filter((u) => !u.is_new).map((u) => u.title);
const removed = plan.deletes.map((d) => d.title);
const embedded = counted.rows.map((r) => r.title);
const skipped = plan.upserts.map((u) => u.title).filter((t) => !embedded.includes(t));

const parts = [];
if (added.length) parts.push(`${added.length} new`);
if (updated.length) parts.push(`${updated.length} updated`);
if (removed.length) parts.push(`${removed.length} removed`);
const headline = parts.length ? `Knowledge base synced: ${parts.join(', ')}.` : 'Knowledge base checked: no changes.';

const detail = [
  added.length ? `New: ${added.join('; ')}` : null,
  updated.length ? `Updated: ${updated.join('; ')}` : null,
  removed.length ? `Removed: ${removed.join('; ')}` : null,
  skipped.length ? `Skipped (empty document): ${skipped.join('; ')}` : null,
  `${plan.article_count} articles in the folder, ${counted.chunks_written} chunks written this run${plan.forced ? ' (full re-embed)' : ''}.`,
].filter(Boolean);

return [{
  json: {
    headline,
    detail: detail.join('\n'),
    slack_text: `*${headline}*\n${detail.join('\n')}`,
    changed: parts.length > 0,
    article_count: plan.article_count,
    chunks_written: counted.chunks_written,
  },
}];
