// Escalation Input: what 30 - Escalate to Team needs to hand the chat to a person.
const r = $('Reply Data').first().json;
return [{
  json: {
    session_id: r.session_id,
    channel: r.channel,
    action: r.action,
    reason: r.reason,
    latest_text: r.latest_text,
    reply: r.reply,
    contact: r.contact,
    issue_type: r.issue_type,
    dry_run: !!r.dry_run,
    slack_channel: r.delivery.slack_channel,
    team_email: r.delivery.team_email,
    from_email: r.delivery.from_email,
  },
}];
