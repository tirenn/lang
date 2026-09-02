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
    model_name = os.getenv("MODEL_NAME", "google/gemma-4-31b-it:free")
    provider = "OpenRouter" if os.getenv("OPENROUTER_API_KEY") else ("OpenAI" if os.getenv("OPENAI_API_KEY") else "Custom")
    return {
        "langsmith_active": is_langsmith_configured(),
        "configured_model": model_name,
        "provider": provider
    }

@app.get("/api/stream")
async def stream_research(
    task: str = Query(..., description="Research topic or question"),
    model: Optional[str] = Query(None, description="Optional model override")
):
    """
    Streams LangGraph step-by-step execution events using Server-Sent Events (SSE).
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        active_model = model or os.getenv("MODEL_NAME", "google/gemma-4-31b-it:free")
        
        # Initial event
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "init",
                "thread_id": thread_id,
                "task": task,
                "model": active_model,
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
            "final_report": None
        }
        
        try:
            for output in graph.stream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_output in output.items():
                    log_data = {"node": node_name}
                    
                    if node_name == "planner":
                        log_data["title"] = "Strategic Research Planner"
                        log_data["detail"] = f"Generated {len(node_output.get('plan', []))} search sub-queries."
                        log_data["queries"] = node_output.get("plan", [])
                        
                    elif node_name == "researcher":
                        findings = node_output.get("research_data", [])
                        log_data["title"] = "Live Web Researcher"
                        log_data["detail"] = f"Gathered {len(findings)} source snippets from web search."
                        log_data["sources"] = [{"title": f["title"], "url": f["source_url"], "snippet": f["snippet"]} for f in findings]
                        
                    elif node_name == "fact_checker":
                        passed = node_output.get("critique_passed", False)
                        feedback = node_output.get("critique_feedback", "")
                        rev = node_output.get("revision_count", 0)
                        log_data["title"] = f"Fact-Checker & Critic (Iteration {rev})"
                        log_data["passed"] = passed
                        log_data["status"] = "PASSED" if passed else "REVISION NEEDED"
                        log_data["detail"] = feedback
                        
                    elif node_name == "writer":
                        log_data["title"] = "Executive Intelligence Writer"
                        log_data["detail"] = "Synthesized comprehensive final report."
                    
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
            report = final_state.get("final_report", "No report generated.")
            
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "complete",
                    "report": report,
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
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
