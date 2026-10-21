// Return Follow-up: reports whether the follow-up reached the Slack thread.
const dryRun = !!$('Config').first().json.dry_run;
const m = $('Follow-up Message').first().json;
let sent = null;
if (!dryRun && $('Post Follow-up').isExecuted) {
  const r = $('Post Follow-up').first().json || {};
  sent = r.ok === true;
}
return [{ json: { claimed: false, followup: true, dry_run: dryRun, sent_slack: sent, in_thread: m.has_thread } }];
