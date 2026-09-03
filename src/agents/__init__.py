"""
Multi-Agent Module (SOLID Architecture).
"""

from src.agents.base import BaseAgent, SearchToolInterface
from src.agents.planner import PlannerAgent, planner_node
from src.agents.researcher import ResearcherAgent, researcher_node
from src.agents.fact_checker import FactCheckerAgent, fact_checker_node
from src.agents.writer import WriterAgent, writer_node

__all__ = [
    "BaseAgent",
    "SearchToolInterface",
    "PlannerAgent",
    "planner_node",
    "ResearcherAgent",
    "researcher_node",
    "FactCheckerAgent",
    "fact_checker_node",
    "WriterAgent",
    "writer_node",
]
