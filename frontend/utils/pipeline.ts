import { promptClaude } from './ai';
import { postMemoryWrite } from './memory';

export async function runPipeline(type: string, topic: string): Promise<string> {
  const res = await promptClaude(`${type}: ${topic}`);
  const text = res.result || res.response || res.completion || '';
  await postMemoryWrite({
    project_id: 'products',
    title: topic,
    content: text,
    author_id: 'claude',
  });
  return text;
}

export async function suggestSEO(input: string) {
  const data = {
    title: `Optimized title for ${input}`,
    meta: `Meta description for ${input}`,
    headings: [`H1 for ${input}`],
    faqs: [`FAQ about ${input}`],
  };
  await postMemoryWrite({
    project_id: 'seo-insights',
    title: input,
    content: JSON.stringify(data, null, 2),
    author_id: 'gemini',
  });
  return data;
}

const researchQueue: { question: string; status: 'pending' | 'completed'; answer?: string }[] = [];

export function addResearch(question: string) {
  researchQueue.push({ question, status: 'pending' });
}

export function listResearch() {
  return researchQueue;
}
