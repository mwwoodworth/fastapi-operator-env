"""
AI agent modules for BrainOps backend.
"""

from .claude_agent import claude_agent

# Create simple gemini wrapper for testing
class GeminiWrapper:
    def __init__(self):
        self.name = "gemini"
        
    async def generate(self, prompt, temperature=0.7, max_tokens=None):
        return "Mock Gemini response"
        
    async def stream(self, prompt, temperature=0.7, max_tokens=None):
        for word in "Mock Gemini streaming response".split():
            yield word + " "
            
    async def analyze_image(self, image_data, prompt):
        return "Mock Gemini vision response"

# Create simple codex wrapper for testing
class CodexWrapper:
    def __init__(self):
        self.name = "codex"
        
    async def generate(self, prompt, temperature=0.7, max_tokens=None):
        return "Mock Codex response"
        
    async def stream(self, prompt, temperature=0.7, max_tokens=None):
        for word in "Mock Codex streaming response".split():
            yield word + " "

gemini = GeminiWrapper()
codex = CodexWrapper()

__all__ = ["claude_agent", "gemini", "codex"]