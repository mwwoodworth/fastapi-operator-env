export async function perplexityRelay(question: string): Promise<{status: string}> {
  console.log('Research question logged:', question);
  return { status: 'queued' };
}
