import logging
import json
from typing import AsyncGenerator
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import get_settings
from state import CoTState
from graphs.cot_graph import get_graph

logger = logging.getLogger(__name__)

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s :: %(message)s",
)

app = FastAPI(title=settings.app_name)


@app.get('/health')
def health_check() -> dict:
    return {'status': 'ok', 'env': settings.app_env}


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    reasoning_steps: list[str]
    step_count: int


@app.post("/query", response_model=QueryResponse)
async def query_agent(payload: QueryRequest) -> QueryResponse:
    graph = get_graph()

    initial_state: CoTState = {
        "question": payload.question,
        "step": 0,
        "reasoning_steps": [],
        "answer": "",
    }

    async def _graph_event_generator() -> AsyncGenerator[str, None]:
        async for event in graph.astream_events(initial_state, version='v2'):
            if event['event'] == 'on_chain_end':
                if event['data']['name'] == 'agent':
                    yield json.dumps({
                        'name': 'agent',
                        'reasoning': event['data']['reasoning_steps'][-1],
                        'message': f'Agent reasoning step {event['data']['step']} completed'
                    })
                elif event['data']['name'] == 'finalize':
                    yield json.dumps({
                        'name': 'finalize',
                        'answer': event['data']['answer'],
                        'message': f'Final answer generated successfully'
                    })
    
    return StreamingResponse(
        _graph_event_generator(),
        media_type='application/x-ndjson',
    )


def main() -> None:
    logger.info(f"Starting {settings.app_name} server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port
    )


if __name__ == "__main__":
    main()
