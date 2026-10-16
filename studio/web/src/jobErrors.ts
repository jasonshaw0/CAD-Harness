export function jobErrorMessage(error: string): string {
  let message = error.trim();
  try {
    const parsed = JSON.parse(message);
    if (typeof parsed.message === 'string') message = parsed.message;
  } catch { /* Worker stderr can also be plain text. */ }
  if (/workflow evaluator changed|saved evidence is stale/.test(message)) {
    return `${message}. Rebuild current source to create fresh evidence, then export again.`;
  }
  return message;
}
