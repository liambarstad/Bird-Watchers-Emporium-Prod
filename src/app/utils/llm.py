import logging
import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class LlamaServerError(Exception):
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        logger.error(f'LLAMA SERVER ERROR: {message}\n(original error: {original_error})')
        self.message = message
        self.original_error = original_error


def call_llama_server(
    messages: list[dict[str, str]],
    temperature: float = 0.7, 
    max_tokens: int = 4096
) -> str:

    settings = get_settings()
    llama_url = f'http://{settings.llama_host}:{settings.llama_port}/v1/chat/completions'

    payload = {
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(llama_url, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']

            request_info = {
                'model': result['model'],
                'finish_reason': result['choices'][0]['finish_reason'],
                'usage': result['usage'],
                'timings': result['timings'],
            }
            logger.info(f'LLAMA SERVER REQUEST INFO: {request_info}')

            return content.strip()
    except httpx.RequestError as e:
        raise LlamaServerError(f'Failed to communicate with llama-server: {str(e)}', original_error=e)
    except httpx.HTTPStatusError as e:
        raise LlamaServerError(f'llama-server returned error status {e.response.status_code}: {str(e)}', original_error=e)
    except (KeyError, IndexError) as e:
        raise LlamaServerError(f'Unexpected response format from llama-server: {str(e)}', original_error=e)
    except Exception as e:
        raise LlamaServerError(f'Unexpected error calling llama-server: {str(e)}', original_error=e)