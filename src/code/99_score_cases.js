// Score Cases: every case passes only if all of its checks pass. One row per case for the sheet.
const CASES = Object.fromEntries(__TEST_CASES__.map((c) => [c.id, c]));
const turns = $input.all().map((i) => i.json).filter((t) => t && t.case_id);

const norm = (s) => String(s ?? '')
  .toLowerCase()
  .replace(/[‘’]/g, "'")
  .replace(/[“”]/g, '"')
  .replace(/ /g, ' ')
  .replace(/(\d),(\d{3})/g, '$1$2')
  .replace(/a\.m\./g, 'am')
  .replace(/p\.m\./g, 'pm')
  .replace(/[–—]/g, '-')
  .replace(/\s+/g, ' ')
  .trim();

const byCase = {};
for (const t of turns) (byCase[t.case_id] = byCase[t.case_id] || []).push(t);

const rows = [];
for (const [id, list] of Object.entries(byCase)) {
  const c = CASES[id];
  list.sort((a, b) => a.turn - b.turn);
  const last = list[list.length - 1].result || {};
  const reply = norm(last.reply);
  const failed = [];

  for (const t of list) {
    const r = t.result || {};
    if (r.error || r.answer_status === 'error') failed.push(`turn ${t.turn} error: ${String((r.error && r.error.message) || (r.flags && r.flags.error) || '').slice(0, 120)}`);
  }
  if (c.expect_status && c.expect_status !== 'any' && last.answer_status !== c.expect_status) {
    failed.push(`status ${last.answer_status} (expected ${c.expect_status})`);
  }
  for (const group of c.must_include) {
    if (!group.some((alt) => reply.includes(norm(alt)))) failed.push(`missing "${group.join(' | ')}"`);
  }
  for (const phrase of c.must_not_include) {
    if (reply.includes(norm(phrase))) failed.push(`contains "${phrase}"`);
  }
  if (c.must_cite && !(last.cited_titles || []).includes(c.must_cite)) failed.push(`did not cite "${c.must_cite}"`);
  for (const [turnNo, action] of c.expect_actions) {
    const t = list.find((x) => x.turn === turnNo);
    const got = t && t.result ? t.result.action : 'missing';
    if (got !== action) failed.push(`turn ${turnNo} action ${got} (expected ${action})`);
  }
  if (c.expect_final_status && last.status !== c.expect_final_status) {
    failed.push(`final status ${last.status} (expected ${c.expect_final_status})`);
  }
  if (c.expect_contact_email && (!last.contact || last.contact.email !== c.expect_contact_email)) {
    failed.push(`contact email ${last.contact ? last.contact.email : 'none'} (expected ${c.expect_contact_email})`);
  }
  for (const f of c.expect_flags) {
    if (!last.flags || !last.flags[f]) failed.push(`flag "${f}" not set`);
  }

  // A handoff must carry every customer message up to that point.
  const handoff = list.find((t) => t.result && t.result.action === 'handoff_now');
  if (handoff) {
    const esc = handoff.result.escalation || {};
    if (!esc.claimed) failed.push('handoff not claimed');
    const tx = norm(esc.transcript_text);
    for (const t of list.filter((x) => x.turn <= handoff.turn)) {
      if (!tx.includes(norm(t.text).slice(0, 40))) failed.push(`transcript missing turn ${t.turn}`);
    }
  }

  const sum = (k) => list.reduce((a, t) => a + (Number(t.result && t.result[k]) || 0), 0);
  rows.push({
    run_id: list[0].run_id,
    run_group: list[0].run_group,
    case_id: id,
    group: c.group,
    category: c.category,
    result: failed.length ? 'FAIL' : 'PASS',
    failed_checks: failed.join('; '),
    turns: list.length,
    customer_messages: list.map((t) => t.text).join(' || '),
    last_reply: String(last.reply || '').slice(0, 1000),
    answer_status: last.answer_status || '',
    actions: list.map((t) => (t.result && t.result.action) || '?').join(' > '),
    final_status: last.status || '',
    cited: (last.cited_titles || []).join('; '),
    best_score: last.best_score ?? '',
    flags: Object.keys(last.flags || {}).join(', '),
    tokens_in: sum('tokens_in'),
    tokens_out: sum('tokens_out'),
    latency_ms: Math.round(sum('latency_ms') / list.length),
    model: last.model || '',
    prompt_version: last.prompt_version || '',
  });
}
rows.sort((a, b) => a.case_id.localeCompare(b.case_id));
return rows.map((r) => ({ json: r }));
