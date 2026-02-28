from typing import Callable
from langchain_core.tools import tool


def create_bird_search_tool() -> Callable:
    @tool
    def lookup_bird_info(query: str) -> str:
        '''
        Consult the bird information database, which contains facts, images, and locations about birds.
        The "query" argument should be a full, natural language question with as much detail as possible.
        '''
        return 'bird_search_tool'
    return lookup_bird_info


def create_bwe_tools() -> list[Callable]:
    return [
        create_bird_search_tool()
    ]