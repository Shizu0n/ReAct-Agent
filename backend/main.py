from time import perf_counter

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import build_graph


class ScriptedLLM:
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    def invoke(self, messages):
        return AIMessage(content=next(self._responses))


EXAMPLES = [
    (
        "Give a direct answer: what is ReAct in one sentence?",
        [
            "Thought: This can be answered directly.\n"
            "Final Answer: ReAct combines reasoning traces with tool actions so an agent can think, act, observe, and answer."
        ],
    ),
    (
        "Calculate 12 * 8 + 5.",
        [
            "Thought: Need exact arithmetic.\nAction: calculator\nAction Input: 12 * 8 + 5",
            "Thought: The calculator returned the value.\nFinal Answer: 101",
        ],
    ),
    (
        "Use Python to compute 6!, then divide it by 9.",
        [
            "Thought: Need factorial first.\nAction: python_executor\nAction Input: print(math.factorial(6))",
            "Thought: Need divide the observed factorial by 9.\nAction: calculator\nAction Input: 720 / 9",
            "Thought: The final computed value is available.\nFinal Answer: 80.0",
        ],
    ),
]


def run_example(index: int, query: str, responses: list[str]) -> None:
    print(f"\n=== Example {index}: {query} ===")
    graph = build_graph(llm=ScriptedLLM(responses))
    started_at = perf_counter()
    printed_steps = 0
    final_answer = None

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }

    for state in graph.stream(initial_state, stream_mode="values"):
        steps = state.get("intermediate_steps", [])
        while printed_steps < len(steps):
            step = steps[printed_steps]
            observation = step["observation"].replace("\n", " ")
            print(
                f"[Step {printed_steps + 1}] Thought: {step['thought']} | "
                f"Action: {step['action']} | Observation: {observation}"
            )
            printed_steps += 1
        final_answer = state.get("final_answer") or final_answer

    elapsed = perf_counter() - started_at
    print(f"Final answer: {final_answer}")
    print(f"Total time: {elapsed:.2f}s")


def main() -> None:
    for index, (query, responses) in enumerate(EXAMPLES, start=1):
        run_example(index, query, responses)


if __name__ == "__main__":
    main()
