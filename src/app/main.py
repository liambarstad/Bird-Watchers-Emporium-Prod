import json
from typing import AsyncGenerator
import asyncio
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


def return_step_message(message: str, event: dict) -> str:
    data = event.get('data', {})
    run_id = event.get('run_id')
    name = event.get('name')

    logger.info('-- Return step message --', data=data, run_id=run_id, name=name, message=message)
    yield json.dumps({'status_message': message}) + '\n'


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
            async for event in bwe_agent.astream_events(initial_state, version='v2'):
                match event.get('event'):

                    case 'on_chain_start':
                        return_step_message('Querying agent...', event)

                    case 'on_tool_start':
                        tool_step_description = (event.get('data', {})\
                            .get('input', {})\
                            .get('step_description') \
                            or 'Running tool') + '...'

                        return_step_message(tool_step_description, event)

                    case 'on_tool_end':
                        return_step_message('Output from tool received', event)

                    case 'on_chain_end':
                        output = event.get('data', {}).get('output')
                        if isinstance(output, dict):
                            final_answer = output.get('final_answer')
                            yield json.dumps({'complete': True, 'final_answer': final_answer}) + '\n'

                    case 'on_error':
                        data = event.get('data', {})
                        logger.error('Request error', 
                            run_id=data.get('run_id'),
                            error=data.get('error')
                        )
                        yield json.dumps({'error': True, 'status_message': 'Error during agent execution.'}) + '\n'

        
        except Exception as e:
            if settings.debug:
                raise e
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error('Unexpected error', error=error_msg)
            yield json.dumps({'error': True, 'status_message': f'Unexpected error.'}) + '\n'

    
    return StreamingResponse(
        _graph_event_generator(),
        media_type='application/x-ndjson',
    )


def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Task exception: {str(msg)}")


def main() -> None:
    logger.info(f"Starting {settings.app_name} server on {settings.api_host}:{settings.api_port}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if not settings.debug:
        loop.set_exception_handler(handle_exception)

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        loop="asyncio" 
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


if __name__ == "__main__":
    main()
