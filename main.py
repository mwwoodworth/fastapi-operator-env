from fastapi import FastAPI
from pydantic import BaseModel
from codex import brainops_operator

app = FastAPI()


class TanaRequest(BaseModel):
    content: str


@app.post("/tana/create-node")
async def create_tana_node(request: TanaRequest):
    brainops_operator.run_task("create_tana_node", {"content": request.content})
    return {"status": "submitted", "content": request.content}
