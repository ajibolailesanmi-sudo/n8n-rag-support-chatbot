// Upsert Items: one item per article to (re)embed.
return $('Plan Sync').first().json.upserts.map((u) => ({ json: u }));
