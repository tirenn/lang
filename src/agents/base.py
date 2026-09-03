"""
Base Agent Abstractions & SOLID Contracts.

Adheres to:
- Single Responsibility Principle (SRP): Isolates agent contract from node execution.
- Open/Closed Principle (OCP): New agents extend BaseAgent without altering core runners.
- Liskov Substitution Principle (LSP): Any BaseAgent subclass can be invoked interchangeably.
- Interface Segregation Principle (ISP): Minimal callable contract `execute(state)`.
- Dependency Inversion Principle (DIP): Agents depend on abstract LLM and tool interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Protocol
from src.state import AgentState, ResearchItem


class SearchToolInterface(Protocol):
    """Interface Segregation Principle: Minimal protocol for search/retrieval tools."""
    def search(self, query: str, max_results: int = 3) -> List[ResearchItem]:
        ...


class BaseAgent(ABC):
    """
    Abstract Base Class for all multi-agent workflow participants.
    Subclasses must implement `execute(state: AgentState) -> Dict[str, Any]`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for the agent role."""
        pass

    @abstractmethod
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the agent's core domain responsibility.
        
        Args:
            state: Current immutable AgentState snapshot.
            
        Returns:
            Dict containing the state update delta.
        """
        pass

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Allows direct invocation as a LangGraph node callable."""
        return self.execute(state)
