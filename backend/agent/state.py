import operator
from typing import Annotated

from typing_extensions import NotRequired, TypedDict

from langchain_core.messages import BaseMessage


class Step(TypedDict):
    thought: str
    action: str
    action_input: str
    observation: str
    timestamp: str
    elapsed_ms: NotRequired[int]
    run_id: NotRequired[str]
    status: NotRequired[str]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    intermediate_steps: list[Step]
    iteration_count: int
    final_answer: str | None


class MaxIterationsError(Exception):
    pass
