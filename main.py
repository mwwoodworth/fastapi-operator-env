# main.py
from fastapi import FastAPI, Request
from claude_utils import run_claude
from gpt_utils import run_gpt
from utils import log_task
import uvicorn

app = FastAPI()

@app.post("/run")
async def run_task(req: Request):
    data = await req.json()
    task = data.get("task")
    input_data = data.get("input")
    
    try:
        if task == "claude":
            prompt = input_data.get("prompt")
            result = await run_claude(prompt)
        elif task == "gpt":
            prompt = input_data.get("prompt")
            result = await run_gpt(prompt)
        elif task == "summarize":
            text = input_data.get("text")
            result = await run_claude(f"Summarize the following: {text}")
        elif task == "echo":
            result = {"message": input_data.get("message")}
        else:
            return {"error": f"Unknown task type: {task}"}

        await log_task(task, input_data, result)
        return {"result": result}

    except Exception as e:
        await log_task(task, input_data, {"error": str(e)})
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=True)
