// Test Turns: expands the chosen test cases into one item per customer message, in order.
// Every case gets its own session, so cases never share memory or handoff state.
const CASES = __TEST_CASES__;
const opt = $('Run Options').first().json;
const group = String(opt.group || 'all').trim().toUpperCase();
const only = String(opt.case_ids || '').split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
const runId = opt.run_id;

const chosen = CASES.filter((c) => (only.length ? only.includes(c.id) : group === 'ALL' || c.group === group));
if (!chosen.length) throw new Error(`No test cases match group "${group}" / ids "${only.join(',')}"`);

const items = [];
for (const c of chosen) {
  c.turns.forEach((text, i) => {
    items.push({
      json: {
        run_id: runId,
        run_group: only.length ? `ids:${only.join(',')}` : group,
        case_id: c.id,
        turn: i + 1,
        turns_total: c.turns.length,
        channel: c.channel === 'whatsapp' ? 'whatsapp' : 'web',
        session_id: `test-${runId}-${c.id}`,
        text,
        is_test: true,
        dry_run: true,
        contact_phone: c.channel === 'whatsapp' ? '+15550100999' : null,
        contact_name: c.channel === 'whatsapp' ? 'Test Customer' : null,
      },
    });
  });
}
return items;
