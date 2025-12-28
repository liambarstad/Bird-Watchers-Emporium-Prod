from typing import List, TypedDict


class CoTState(TypedDict):
    question: str
    step: int
    reasoning_steps: List[str]
    answer: str
