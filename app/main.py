from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import traceback # 에러 추적용
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.intent_service import classify_intent, REJECTION_TEMPLATES
from services.rag_service import generate_rag_response

app = FastAPI()

class Status(BaseModel):
    suspicionScore: int
    affectionScore: int
    isConfessed: bool

class Log(BaseModel):
    role: str
    message: str

class Context(BaseModel):
    summary: str
    recentLogs: List[Log]

class InventoryItem(BaseModel):
    itemId: str
    name: str
    obtainedAt: str

class RagRequest(BaseModel):
    npcName: str
    userMessage: str
    sessionId: int
    status: Status
    userInventory :List[InventoryItem]
    context: Context

class SummaryRequest(BaseModel):
    npcName: str
    summary: str
    recentLogs: List[Log]

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)

# RAG 파이프라인 응답 API

@app.post("/api/response")
async def handle_response(req: RagRequest):
    try:
        intent_data = classify_intent(req.userMessage)
        
        intent_code = intent_data.get("intent_code")
        detected_item = intent_data.get("detected_item")
        is_critical_evidence = intent_data.get("is_critical_evidence", False)

        if intent_code == 2:
            template = REJECTION_TEMPLATES.get(req.npcName, REJECTION_TEMPLATES["라이언"])
            return {
                "npcResponse": template["text"],
                "statChanges": template.get("stat_effect", {"suspicion": 0, "affection": 0}),
                "isConfessed": False,
                "acquiredItem": None
            }
        final_result = generate_rag_response(
            npc_name=req.npcName,
            user_msg=req.userMessage,
            intent_code=intent_code,
            is_critical_evidence=is_critical_evidence,
            detected_item=detected_item,
            suspicion_score=req.status.suspicionScore,
            affection_score=req.status.affectionScore,
            user_inventory=[item.model_dump() for item in req.userInventory],
            conversation_summary=req.context.summary,
            recent_logs=[log.model_dump() for log in req.context.recentLogs]
        )

        return final_result

    except Exception as e:
        print("Detailed Error Traceback:")
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# 요약 API (백엔드 제공용)
@app.post("/api/summary")
async def handle_summary(req: SummaryRequest):
    try:
        history_str = "\n".join([f"{log.role}: {log.message}" for log in req.recentLogs])
        
        from services.summary_service import update_summary
        
        updated_summary = update_summary(
            npc_name=req.npcName,
            old_summary=req.summary,
            history_str=history_str
        )
        
        return {
            "npcName": req.npcName,
            "updatedSummary": updated_summary
        }
    except Exception as e:
        print("Summary Error Traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)