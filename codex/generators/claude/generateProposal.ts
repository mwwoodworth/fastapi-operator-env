export async function generateProposal(topic: string): Promise<string> {
  return `# ${topic} Proposal\n\nThis is a simulated Claude proposal for ${topic}.`;
}
