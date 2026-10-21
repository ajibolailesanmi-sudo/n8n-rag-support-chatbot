// Return Already: another message handed this chat off first, so nothing is sent twice.
return [{ json: { claimed: false, already_handed_off: true, dry_run: !!$('Config').first().json.dry_run } }];
