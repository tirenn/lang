import os
import uuid
from langsmith import Client
from langsmith.evaluation import evaluate
from src.graph import build_research_graph
from src.config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# 1. Benchmark Test Dataset
BENCHMARK_EXAMPLES = [
    {
        "inputs": {"task": "State of Quantum Computing in 2026: Key Breakthroughs and Scalability Roadmaps"},
        "outputs": {"expected_facets": "Error correction, logical qubits, commercial hardware providers, timeline to quantum advantage"}
    },
    {
        "inputs": {"task": "Agentic AI Architecture Patterns: ReAct vs Plan-and-Solve vs Multi-Agent Graphs"},
        "outputs": {"expected_facets": "State machines, human-in-the-loop, cyclical workflows, tool calling benchmarks"}
    }
]

DATASET_NAME = "autonomous-research-agent-benchmark"

def create_or_get_dataset(client: Client) -> str:
    """Creates benchmark dataset in LangSmith if it doesn't exist."""
    if not client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Benchmark questions evaluating autonomous multi-agent research accuracy and depth."
        )
        for ex in BENCHMARK_EXAMPLES:
            client.create_example(
                inputs=ex["inputs"],
                outputs=ex["outputs"],
                dataset_id=dataset.id
            )
        print(f"Created LangSmith Dataset: {DATASET_NAME}")
    else:
        print(f"Found existing LangSmith Dataset: {DATASET_NAME}")
    return DATASET_NAME

# 2. Custom LLM-as-a-Judge Evaluator for Hallucination & Completeness
class EvalGrade(BaseModel):
    score: float = Field(description="Score between 0.0 and 1.0 evaluating quality.")
    reasoning: str = Field(description="Explanation of why this score was awarded.")

EVAL_PROMPT = """You are an Expert AI Evaluator judging a research report.
User Topic: {task}
Expected Core Facets: {expected_facets}

Generated Report:
{report}

Evaluate:
1. Did the report address all expected core facets?
2. Is the report rigorous, clear, and cite sources properly?
Give a score between 0.0 and 1.0 and explain.
"""

def report_quality_evaluator(run, example) -> dict:
    """Custom LangSmith evaluator assessing report coverage and quality."""
    task = example.inputs.get("task", "")
    expected = example.outputs.get("expected_facets", "")
    final_report = run.outputs.get("final_report", "")
    
    llm = get_llm().with_structured_output(EvalGrade)
    prompt = ChatPromptTemplate.from_template(EVAL_PROMPT)
    chain = prompt | llm
    
    res: EvalGrade = chain.invoke({
        "task": task,
        "expected_facets": expected,
        "report": final_report
    })
    
    return {
        "key": "report_quality",
        "score": res.score,
        "comment": res.reasoning
    }

def target_graph_runner(inputs: dict) -> dict:
    """Target function for evaluation runs."""
    app = build_research_graph(checkpointer=False, human_in_the_loop=False)
    state = {
        "task": inputs["task"],
        "plan": [],
        "research_data": [],
        "critique_feedback": None,
        "critique_passed": False,
        "revision_count": 0,
        "max_revisions": 1,
        "final_report": None
    }
    result = app.invoke(state)
    return {"final_report": result.get("final_report", "")}

def run_evaluation():
    """Triggers automated evaluation suite on LangSmith."""
    client = Client()
    dataset_name = create_or_get_dataset(client)
    
    print("Starting LangSmith evaluation run...")
    results = evaluate(
        target_graph_runner,
        data=dataset_name,
        evaluators=[report_quality_evaluator],
        experiment_prefix="multi-agent-eval",
        max_concurrency=1
    )
    print("Evaluation completed! View detailed trace and scores in your LangSmith dashboard.")

if __name__ == "__main__":
    run_evaluation()
