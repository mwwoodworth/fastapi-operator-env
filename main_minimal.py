"""Minimal FastAPI app for debugging imports"""

from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI(
    title="BrainOps Backend",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "BrainOps Backend is running", "status": "ok"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_minimal:app", host="0.0.0.0", port=8000)