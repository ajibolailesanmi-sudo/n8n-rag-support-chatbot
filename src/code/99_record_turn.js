// Record Turn: keeps the customer message and the assistant's result together.
const turn = $('Loop Turns').first().json;
const result = $input.first().json || {};
return [{ json: { ...turn, result } }];
