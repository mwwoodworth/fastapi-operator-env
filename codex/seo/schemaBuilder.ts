export async function buildSchema(data: Record<string, any>): Promise<string> {
  return JSON.stringify({ '@context': 'https://schema.org', ...data }, null, 2);
}
