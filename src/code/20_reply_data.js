// Reply Data: picks the reply from whichever path produced it (answer, message cap or fallback).
for (const name of ['Apply Rules', 'Limit Reply', 'Fallback Reply']) {
  if ($(name).isExecuted) return [{ json: $(name).first().json }];
}
throw new Error('No reply was produced for this message');
