"""
FastAPI Server & Real-Time SSE Streaming Endpoint.

Exposes:
- GET /: Renders the editorial FactCheck AI web interface.
- GET /api/config: Returns system parameters, available models, and live client quota.
- GET /api/quota: Live rate-limit quota check.
- GET /api/stream: Server-Sent Events (SSE) streaming multi-agent execution steps and verdict.
"""

import os
import json
import uuid
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any, List
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from src.graph import build_research_graph
from src.config import is_langsmith_configured
from src.security import (
    SecurityHeadersMiddleware,
    rate_limiter,
    concurrency_guard,
    validate_claim_input,
    shield_error,
    MAX_INPUT_LENGTH,
    RATE_LIMIT_MAX_REQUESTS
)

app = FastAPI(
    title="FactCheck AI - Autonomous Misinformation Intelligence Engine",
    description="Multi-agent investigative fact-checking system adhering to IFCN standards.",
    version="1.0.0"
)

# Enforce browser security headers (CSP, X-Frame-Options, X-Content-Type-Options)
app.add_middleware(SecurityHeadersMiddleware)

# Enforce CORS rules
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Static assets serving
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ==============================================================================
# Helper Utilities
# ==============================================================================

def extract_client_ip(request: Request) -> str:
    """Extracts client IP, respecting X-Forwarded-For when behind Cloudflare Tunnel."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_available_models() -> List[str]:
    """Reads configured model list from environment with sensible fallbacks."""
    raw = os.getenv("AVAILABLE_MODELS", "")
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return [
        "minimax/minimax-m2.7:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "z-ai/glm-5.2:free",
        "meta-llama/llama-3.3-70b-instruct:free"
    ]


def format_node_log(node_name: str, node_output: Dict[str, Any], models: Dict[str, str]) -> Dict[str, Any]:
    """Formats raw LangGraph node output into clean event payload for UI audit-trail."""
    payload = {"node": node_name, "model": models.get(node_name, "")}

    if node_name == "planner":
        queries = node_output.get("plan", [])
        payload["title"] = "Claim Deconstructor & Query Strategist"
        payload["detail"] = f"Formulated {len(queries)} targeted fact-checking queries."
        payload["queries"] = queries

    elif node_name == "researcher":
        findings = node_output.get("research_data", [])
        payload["title"] = "Evidence & Source Investigation"
        payload["detail"] = f"Gathered {len(findings)} verified news and institutional sources."
        payload["sources"] = [
            {"title": f["title"], "url": f["source_url"], "snippet": f["snippet"]}
            for f in findings
        ]

    elif node_name == "fact_checker":
        verdict = node_output.get("verdict", "PARTLY TRUE")
        payload["title"] = f"Verification Board (Verdict: {verdict})"
        payload["passed"] = node_output.get("critique_passed", False)
        payload["verdict"] = verdict
        payload["confidence"] = node_output.get("confidence_score", 0.85)
        payload["status"] = verdict
        payload["detail"] = node_output.get("critique_feedback", "")

    elif node_name == "writer":
        payload["title"] = "Fact-Check Report Synthesizer"
        payload["detail"] = "Synthesizing IFCN-standard investigative fact-check report."

    return payload


# ==============================================================================
# Routes & Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main editorial FactCheck AI single-page interface."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "<h1>Index page not found. Ensure src/static/index.html exists.</h1>"


@app.get("/api/config")
async def get_system_config(request: Request):
    """Returns application status, available models, and client rate-limit quota."""
    provider = "OpenRouter" if os.getenv("OPENROUTER_API_KEY") else ("OpenAI" if os.getenv("OPENAI_API_KEY") else "Custom")
    models = get_available_models()
    default_model = models[0]
    client_ip = extract_client_ip(request)

    return {
        "langsmith_active": is_langsmith_configured(),
        "configured_model": default_model,
        "planner_model": default_model,
        "researcher_model": default_model,
        "fact_checker_model": models[1] if len(models) > 1 else default_model,
        "writer_model": default_model,
        "available_models": models,
        "max_input_length": MAX_INPUT_LENGTH,
        "rate_limit_max": RATE_LIMIT_MAX_REQUESTS,
        "quota": rate_limiter.get_status(client_ip),
        "provider": provider
    }


@app.get("/api/quota")
async def get_current_quota(request: Request):
    """Returns live sliding-window rate limit quota for client IP."""
    client_ip = extract_client_ip(request)
    return rate_limiter.get_status(client_ip)


@app.get("/api/stream")
async def stream_research(
    request: Request,
    task: str = Query(..., description="The viral claim, rumor, or headline to verify"),
    planner_model: Optional[str] = Query(None, description="Model override for Planner"),
    researcher_model: Optional[str] = Query(None, description="Model override for Researcher"),
    fact_checker_model: Optional[str] = Query(None, description="Model override for Fact-Checker"),
    writer_model: Optional[str] = Query(None, description="Model override for Writer")
):
    """
    Streams step-by-step fact-checking execution via Server-Sent Events (SSE).
    Protected by Rate Limiting, Input Sanitization, and Concurrency Guards.
    """
    client_ip = extract_client_ip(request)

    # 1. Rate Limiting Check (Sliding Window)
    is_allowed, retry_after = rate_limiter.check(client_ip)
    if not is_allowed:
        retry_msg = f"Rate limit reached (max {RATE_LIMIT_MAX_REQUESTS} verifications per hour). Please retry in {retry_after} seconds."
        async def rate_limit_event(msg=retry_msg):
            yield {"event": "message", "data": json.dumps({"type": "error", "message": msg})}
        return EventSourceResponse(rate_limit_event())

    # 2. Input Validation & Prompt Injection Defense
    try:
        sanitized_task = validate_claim_input(task)
    except ValueError as validation_error:
        err_msg = str(validation_error)
        async def validation_error_event(msg=err_msg):
            yield {"event": "message", "data": json.dumps({"type": "error", "message": msg})}
        return EventSourceResponse(validation_error_event())

    # 3. Server Concurrency Guard
    slot_acquired = await concurrency_guard.acquire()
    if not slot_acquired:
        async def busy_event():
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "message": "Verification engine is currently busy with concurrent analyses. Please wait a few moments and retry."
                })
            }
        return EventSourceResponse(busy_event())

    # 4. Multi-Agent Streaming Execution
    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            models = get_available_models()
            default_model = models[0]
            agent_models = {
                "planner": planner_model or default_model,
                "researcher": researcher_model or default_model,
                "fact_checker": fact_checker_model or (models[1] if len(models) > 1 else default_model),
                "writer": writer_model or default_model
            }

            # Emit initial session event
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "init",
                    "thread_id": thread_id,
                    "task": sanitized_task,
                    "models": agent_models,
                    "langsmith_active": is_langsmith_configured()
                })
            }

            # Build and initialize multi-agent graph
            graph = build_research_graph(checkpointer=True, human_in_the_loop=False)
            initial_state = {
                "task": sanitized_task,
                "plan": [],
                "research_data": [],
                "critique_feedback": None,
                "critique_passed": False,
                "revision_count": 0,
                "max_revisions": 2,
                "planner_model": agent_models["planner"],
                "researcher_model": agent_models["researcher"],
                "fact_checker_model": agent_models["fact_checker"],
                "writer_model": agent_models["writer"],
                "final_report": None
            }

            # Stream step updates as each agent completes its work
            for output in graph.stream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_output in output.items():
                    log_data = format_node_log(node_name, node_output, agent_models)
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "step",
                            "node": node_name,
                            "payload": log_data
                        })
                    }
                    await asyncio.sleep(0.05)

            # Retrieve final synthesized state
            final_state = graph.get_state(config).values
            report = final_state.get("final_report", "Unable to generate verification report.")
            verdict = final_state.get("verdict", "PARTLY TRUE")
            confidence = final_state.get("confidence_score", 0.85)

            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "complete",
                    "report": report,
                    "verdict": verdict,
                    "confidence": confidence,
                    "thread_id": thread_id
                })
            }

        except Exception as error:
            shielded_message = shield_error(error)
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "message": shielded_message
                })
            }
        finally:
            concurrency_guard.release()

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=True)
