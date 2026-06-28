from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import google.generativeai as genai
import uuid, uvicorn
from pathlib import Path
from dotenv import load_dotenv
import os, json
from datetime import datetime

from config import (
    LEAD_CAPTURE, SYSTEM_PROMPT, MODEL_NAME,
    SOCIAL_LINKS
)
from modules.rag import retrieve, compose_context

if LEAD_CAPTURE:
    from modules.lead_capture import (
        handle_lead_flow, get_goodbye_message,
        is_goodbye, validate_email, validate_name
    )

load_dotenv()
genai.configure(api_key=os.getenv("GEN_API_KEY"))

# ... (session store, Pydantic models, CORS — same as before)

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session = sessions[request.session_id]
    user_input = request.user_input.strip()
    user_info = session["user_info"]
    session["messages"].append({"role": "user", "content": user_input})

    # Goodbye
    if LEAD_CAPTURE and is_goodbye(user_input):
        msg = get_goodbye_message(user_info["name"])
        session["messages"].append({"role": "assistant", "content": msg})
        return ChatResponse(response=msg, conversation_ended=True, show_new_chat=True)

    # Lead flow (only if enabled)
    if LEAD_CAPTURE:
        result = handle_lead_flow(user_input, session, user_info)
        if result:
            response_text, ended = result
            session["messages"].append({"role": "assistant", "content": response_text})
            return ChatResponse(response=response_text, conversation_ended=ended)

    # Default: RAG answer
    retrieved = retrieve(user_input, k=3)
    answer = generate_answer(user_input, retrieved, session["messages"][:-1], user_info)
    session["messages"].append({"role": "assistant", "content": answer})
    return ChatResponse(response=answer)