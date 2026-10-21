// Run Summary: totals by category, the "made-up answer" count and the score ranges used to
// calibrate min_similarity. One row for the test_runs tab and one Slack message.
const rows = $('Score Cases').all().map((i) => i.json);
const cats = {};
for (const r of rows) {
  cats[r.category] = cats[r.category] || { pass: 0, total: 0 };
  cats[r.category].total += 1;
  if (r.result === 'PASS') cats[r.category].pass += 1;
}
const passed = rows.filter((r) => r.result === 'PASS').length;
const nkb = rows.filter((r) => r.category === 'not_in_kb');
const madeUp = nkb.filter((r) => r.answer_status === 'answered').length;
const scores = (cat) => rows.filter((r) => r.category === cat && r.best_score !== '').map((r) => Number(r.best_score));
const ans = scores('answer');
const gap = scores('not_in_kb');
const fmt = (n) => (Number.isFinite(n) ? n.toFixed(3) : 'n/a');
const tokensIn = rows.reduce((a, r) => a + (Number(r.tokens_in) || 0), 0);
const tokensOut = rows.reduce((a, r) => a + (Number(r.tokens_out) || 0), 0);
const latency = rows.length ? Math.round(rows.reduce((a, r) => a + (Number(r.latency_ms) || 0), 0) / rows.length) : 0;
const order = ['answer', 'not_in_kb', 'escalation', 'injection', 'memory', 'contact', 'off_topic'];
const byCategory = order.filter((k) => cats[k]).map((k) => `${k} ${cats[k].pass}/${cats[k].total}`).join(', ');
const failedIds = rows.filter((r) => r.result === 'FAIL').map((r) => r.case_id).join(', ');
const first = rows[0] || {};

const summary = {
  run_id: first.run_id || '',
  run_group: first.run_group || '',
  finished_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
  cases: rows.length,
  passed,
  failed: rows.length - passed,
  by_category: byCategory,
  made_up_answers: `${madeUp} of ${nkb.length}`,
  failed_cases: failedIds,
  answer_best_score_min: fmt(ans.length ? Math.min(...ans) : NaN),
  gap_best_score_max: fmt(gap.length ? Math.max(...gap) : NaN),
  avg_latency_ms: latency,
  tokens_in: tokensIn,
  tokens_out: tokensOut,
  model: first.model || '',
  prompt_version: first.prompt_version || '',
};
summary.slack_text = [
  `*Test run ${summary.run_id} (${summary.run_group}): ${passed} of ${rows.length} cases passed*`,
  `By category: ${byCategory}`,
  `Questions outside the articles answered anyway: ${summary.made_up_answers}`,
  failedIds ? `Failed: ${failedIds}` : 'No failures.',
  `Best-match score: answerable min ${summary.answer_best_score_min}, outside-the-articles max ${summary.gap_best_score_max}`,
  `Average ${latency} ms per message, ${tokensIn} input and ${tokensOut} output tokens, model ${summary.model}, prompt ${summary.prompt_version}`,
].join('\n');
return [{ json: summary }];
