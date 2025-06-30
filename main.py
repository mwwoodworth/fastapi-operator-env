from fastapi import FastAPI, Request
from pydantic import BaseModel
from claude_utils import run_claude

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Operator dev server is live"}

class RunPayload(BaseModel):
    task: str
    input: dict

@app.post("/run")
async def run_task(payload: RunPayload):
    task_type = payload.task
    input_data = payload.input

    try:
        if task_type == "echo":
            return {"result": input_data}

        elif task_type == "claude":
            prompt = input_data.get("prompt", "")
            response = await run_claude(prompt)
            return {"result": response}

        else:
            return {"error": f"Unknown task: {task_type}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}