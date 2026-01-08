from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    character: str
    message: str

@app.get("/")
def read_root():
    return {"status": "AI 서버 구동중"}

