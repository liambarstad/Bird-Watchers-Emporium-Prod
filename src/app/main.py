import json
from typing import AsyncGenerator
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog
from langchain_core.messages import HumanMessage, AIMessage

from state import BWEState
from config import get_settings
from agents.bwe_agent import build_bwe_agent
from logging_config import configure_logging

settings = get_settings()

configure_logging(settings)
logger = structlog.get_logger(__name__)

app = FastAPI(title=settings.app_name)


@app.get('/health')
def health_check() -> dict:
    return {'status': 'ok', 'env': settings.app_env}


class Message(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    question: str
    conversation: list[Message]


@app.post('/query')
async def query_agent(
    request: QueryRequest,
    bwe_agent = Depends(build_bwe_agent)
) -> StreamingResponse:


    initial_state = BWEState(messages=[
        HumanMessage(content=message.content)
        if message.role == 'user'
        else AIMessage(content=message.content)
        for message in request.conversation
    ])

    async def _graph_event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in bwe_agent.astream_events(initial_state, version='v1'):

                data = event.get('data', {})
                run_id = event.get('run_id')
                name = event.get('name')

                match event.get('event'):

                    case 'on_chain_start':
                        if name == 'LangGraph':
                            logger.info('Request started', 
                                run_id=run_id,
                                starting_state=data.get('initial_state'),
                                event_payload=event
                            )
                            yield json.dumps({'status_message': 'Querying agent...'}) + '\n'

                    case 'on_chat_model_stream':
                        content = data['chunk'].content
                        if content:
                            logger.info('Streaming step', 
                                run_id=data.get('run_id'), 
                                step=content,
                                event_payload=event
                            )
                            yield json.dumps({'content': content}) + '\n'

                    case 'on_tool_start':
                        if name:
                            tool_input = data.get('input', {})
                            msg = tool_input.get('step_description') or f'Running tool: {name}...'
                            
                            logger.info('Tool start', run_id=run_id, tool=name)
                            yield json.dumps({'status_message': msg}) + '\n'

                    case 'on_tool_end':
                        output = data.get('output')
                        # Sometimes output is a dict, sometimes it might be just the value or a tool message
                        # We specifically want to look for our structured output from the neo4j tools
                        if isinstance(output, dict) and 'results_count' in output:
                            count = output['results_count']
                            yield json.dumps({'status_message': f'Found {count} results.'}) + '\n'
                        elif output:
                             # Fallback logging to debug what output we actually get
                             logger.info('Tool end output', output=str(output)[:200])

                    case 'on_chain_end':
                        # In v1, on_graph_end might not fire reliably for the top-level graph if it's nested
                        # Check if this is the top-level chain ending
                        if name == 'LangGraph':
                             yield json.dumps({'complete': True}) + '\n'

                    case 'on_error':
                        logger.error('Request error', 
                            run_id=data.get('run_id'),
                            error=data.get('error'),
                            event_payload=event
                        )
                        yield json.dumps({'error': True, 'status_message': 'Error during agent execution.'}) + '\n'

        
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error('Unexpected error', error=error_msg)
            yield json.dumps({'error': True, 'status_message': f'Unexpected error.'}) + '\n'

    
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
