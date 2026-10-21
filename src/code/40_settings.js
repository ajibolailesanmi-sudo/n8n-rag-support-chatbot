// Settings: turns the bot_settings rows into one object and checks the Drive folder is set.
const rows = $input.all().map((i) => i.json).filter((j) => j && j.key);
const settings = Object.fromEntries(rows.map((r) => [r.key, r.value]));
const folder = String(settings.drive_folder_id || '');
if (!folder || folder.startsWith('YOUR_')) {
  throw new Error('Set drive_folder_id in the bot_settings table to the ID of the Google Drive folder with the help articles.');
}
const force = $('Sync Form').isExecuted
  ? String(($('Sync Form').first().json || {}).reembed_all || '').toLowerCase() === 'yes'
  : !!$('Run Options').first().json.force_full;
return [{ json: { settings, drive_folder_id: folder, slack_channel: settings.slack_channel || null, force } }];
