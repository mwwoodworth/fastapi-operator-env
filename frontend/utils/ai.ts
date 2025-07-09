export async function promptClaude(prompt: string) {
  return fetch('/api/claude', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  }).then(r => r.json());
}

export async function promptChatGPT(prompt: string) {
  return fetch('/api/chatgpt', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  }).then(r => r.json());
}
