import os
from typing import Optional
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_FREE_FALLBACKS = [
    "minimax/minimax-m2.7:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free"
]

def get_default_model() -> str:
    raw = os.getenv("AVAILABLE_MODELS", "")
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models[0]
    return "minimax/minimax-m2.7:free"

def get_agent_llm(agent_name: str, temperature: float = 0.2, model_override: Optional[str] = None) -> BaseChatModel:
    """
    Initializes and returns the Chat Model assigned to an agent.
    Priority: model_override (from UI) -> <AGENT>_MODEL -> first model in AVAILABLE_MODELS.
    """
    assigned_model = model_override or os.getenv(f"{agent_name.upper()}_MODEL") or get_default_model()
    return get_llm(temperature=temperature, model_override=assigned_model)

def get_llm(temperature: float = 0.2, model_override: Optional[str] = None) -> BaseChatModel:
    """
    Base LLM initializer with OpenRouter 3-model fallback cascade.
    """
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    primary_model = model_override or get_default_model()
    
    if openrouter_api_key:
        models_list = [primary_model]
        for m in DEFAULT_FREE_FALLBACKS:
            if m not in models_list and len(models_list) < 3:
                models_list.append(m)
                
        return ChatOpenAI(
            model=primary_model,
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            extra_body={"models": models_list},
            default_headers={
                "HTTP-Referer": "https://github.com/langgraph-researcher",
                "X-Title": "LangGraph Autonomous Researcher"
            }
        )
    elif os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(
            model=model_override or os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=temperature
        )
    elif os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        gemini_model = model_override or os.getenv("MODEL_NAME", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(model=gemini_model, temperature=temperature)
    else:
        return ChatOpenAI(
            model=primary_model,
            api_key=openrouter_api_key or os.getenv("OPENAI_API_KEY", "dummy"),
            base_url="https://openrouter.ai/api/v1" if openrouter_api_key else None,
            temperature=temperature
        )

def is_langsmith_configured() -> bool:
    return bool(os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGCHAIN_TRACING_V2") == "true")
