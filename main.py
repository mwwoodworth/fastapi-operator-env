from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Operator Dev Env is live!"}
