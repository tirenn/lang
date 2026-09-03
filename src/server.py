import os
import json
import uuid
import asyncio
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from src.graph import build_research_graph
from src.config import is_langsmith_configured

app = FastAPI(title="Autonomous Multi-Agent Research Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "<h1>Index page not found. Check src/static/index.html</h1>"

@app.get("/api/config")
async def get_system_config():
    provider = "OpenRouter" if os.getenv("OPENROUTER_API_KEY") else ("OpenAI" if os.getenv("OPENAI_API_KEY") else "Custom")
    raw_models = os.getenv("AVAILABLE_MODELS", "")
    if raw_models:
        available_models = [m.strip() for m in raw_models.split(",") if m.strip()]
    else:
        available_models = [
            "minimax/minimax-m2.7:free",
            "google/gemma-4-31b-it:free",
            "nvidia/nemotron-3.5-lightning:free",
            "z-ai/glm-5.2:free",
            "meta-llama/llama-3.3-70b-instruct:free"
        ]

    default_model = available_models[0]
    return {
        "langsmith_active": is_langsmith_configured(),
        "configured_model": default_model,
        "planner_model": default_model,
        "researcher_model": default_model,
        "fact_checker_model": available_models[1] if len(available_models) > 1 else default_model,
        "writer_model": default_model,
        "available_models": available_models,
        "provider": provider
    }

@app.get("/api/stream")
async def stream_research(
    task: str = Query(..., description="Research topic or question"),
    planner_model: Optional[str] = Query(None, description="Model override for Planner"),
    researcher_model: Optional[str] = Query(None, description="Model override for Researcher"),
    fact_checker_model: Optional[str] = Query(None, description="Model override for Fact-Checker"),
    writer_model: Optional[str] = Query(None, description="Model override for Writer")
):
    """
    Streams LangGraph step-by-step execution events using Server-Sent Events (SSE).
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        raw_models = os.getenv("AVAILABLE_MODELS", "")
        fallback_models = [m.strip() for m in raw_models.split(",") if m.strip()] if raw_models else ["minimax/minimax-m2.7:free"]
        def_m = fallback_models[0]
        
        act_planner = planner_model or def_m
        act_researcher = researcher_model or def_m
        act_checker = fact_checker_model or (fallback_models[1] if len(fallback_models) > 1 else def_m)
        act_writer = writer_model or def_m
        
        # Initial event
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "init",
                "thread_id": thread_id,
                "task": task,
                "models": {
                    "planner": act_planner,
                    "researcher": act_researcher,
                    "fact_checker": act_checker,
                    "writer": act_writer
                },
                "langsmith_active": is_langsmith_configured()
            })
        }
        
        # Build research graph
        graph = build_research_graph(checkpointer=True, human_in_the_loop=False)
        initial_state = {
            "task": task,
            "plan": [],
            "research_data": [],
            "critique_feedback": None,
            "critique_passed": False,
            "revision_count": 0,
            "max_revisions": 2,
            "planner_model": act_planner,
            "researcher_model": act_researcher,
            "fact_checker_model": act_checker,
            "writer_model": act_writer,
            "final_report": None
        }
        
        try:
            for output in graph.stream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_output in output.items():
                    log_data = {"node": node_name}
                    
                    if node_name == "planner":
                        log_data["model"] = act_planner
                        log_data["title"] = "Claim Deconstructor & Query Strategist"
                        log_data["detail"] = f"Formulated {len(node_output.get('plan', []))} targeted fact-checking queries."
                        log_data["queries"] = node_output.get("plan", [])
                        
                    elif node_name == "researcher":
                        findings = node_output.get("research_data", [])
                        log_data["model"] = act_researcher
                        log_data["title"] = "Evidence & Source Investigation"
                        log_data["detail"] = f"Gathered {len(findings)} verified news and institutional sources."
                        log_data["sources"] = [{"title": f["title"], "url": f["source_url"], "snippet": f["snippet"]} for f in findings]
                        
                    elif node_name == "fact_checker":
                        passed = node_output.get("critique_passed", False)
                        feedback = node_output.get("critique_feedback", "")
                        rev = node_output.get("revision_count", 0)
                        verdict = node_output.get("verdict", "PARTLY TRUE")
                        confidence = node_output.get("confidence_score", 0.85)
                        log_data["model"] = act_checker
                        log_data["title"] = f"Verification Board (Verdict: {verdict})"
                        log_data["passed"] = passed
                        log_data["verdict"] = verdict
                        log_data["confidence"] = confidence
                        log_data["status"] = verdict
                        log_data["detail"] = feedback
                        
                    elif node_name == "writer":
                        log_data["model"] = act_writer
                        log_data["title"] = "Fact-Check Report Synthesizer"
                        log_data["detail"] = "Synthesizing IFCN-standard investigative fact-check report."
                    
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "step",
                            "node": node_name,
                            "payload": log_data
                        })
                    }
                    await asyncio.sleep(0.05)
            
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
            
        except Exception as e:
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "message": str(e)
                })
            }

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=True)
