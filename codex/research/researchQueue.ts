export interface ResearchItem {
  question: string;
  status: 'pending' | 'completed';
  answer?: string;
}

export const queue: ResearchItem[] = [];

export function addResearch(question: string) {
  queue.push({ question, status: 'pending' });
}

export function listResearch(): ResearchItem[] {
  return queue;
}
