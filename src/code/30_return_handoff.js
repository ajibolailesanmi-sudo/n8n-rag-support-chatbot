// Return Handoff: reports what was delivered. If neither Slack nor email worked, the run fails
// on purpose so the error workflow alerts the team with the session ID.
const b = $('Build Handoff').first().json;
const dryRun = !!$('Config').first().json.dry_run;
let sentSlack = null;
let sentEmail = null;
let slackTs = null;
const errors = [];

if (!dryRun) {
  if ($('Post to Slack').isExecuted) {
    const s = $('Post to Slack').first().json || {};
    sentSlack = !s.error && s.ok !== false;
    slackTs = s.ts || (s.message && s.message.ts) || null;
    if (s.error) errors.push(`Slack: ${s.error.message || JSON.stringify(s.error).slice(0, 200)}`);
  }
  if ($('Email Team').isExecuted) {
    const e = $('Email Team').first().json || {};
    sentEmail = !e.error;
    if (e.error) errors.push(`Email: ${e.error.message || JSON.stringify(e.error).slice(0, 200)}`);
  }
  if (!sentSlack && !sentEmail) {
    throw new Error(`Handoff for ${b.session_id} could not be delivered. ${errors.join(' | ')}`);
  }
}

return [{
  json: {
    claimed: true,
    dry_run: dryRun,
    sent_slack: sentSlack,
    sent_email: sentEmail,
    slack_ts: slackTs,
    errors,
    transcript_lines: b.transcript_lines,
    transcript_text: b.transcript_text,
    slack_text: b.slack_text,
    email_subject: b.subject,
  },
}];
