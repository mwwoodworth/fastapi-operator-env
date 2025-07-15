import { generateSOP } from './claude/generateSOP';
import { generateProposal } from './claude/generateProposal';
import { generateToolkit } from './claude/generateToolkit';

export async function runBlueprint(type: string, topic: string): Promise<string> {
  switch (type.toLowerCase()) {
    case 'sop':
      return generateSOP(topic);
    case 'proposal':
      return generateProposal(topic);
    case 'toolkit':
      return generateToolkit(topic);
    default:
      return '';
  }
}
