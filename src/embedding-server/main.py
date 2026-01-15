import logging

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import get_settings
from embedder import Embedder

settings = get_settings()

app = FastAPI(title=settings.api_name, version=settings.api_version)

embedder = Embedder(
    model_path=settings.model_path,
    model_device=settings.model_device,
)

logger = logging.getLogger(__name__)


@app.get('/health')
def health_check() -> dict:
    return {'status': 'ok', 'env': settings.app_env}


class EmbedTextRequest(BaseModel):
    texts: list[str]


@app.post('/embed/text')
def embed_text(request: EmbedTextRequest) -> dict:
    if not request.texts:
        raise HTTPException(status_code=400, detail='`texts` must be a non-empty list')

    try:
        embeddings = embedder.embed_text(request.texts)
    except Exception as exc:  # pragma: no cover
        logger.exception('Failed to generate embeddings')
        raise HTTPException(status_code=500, detail='Failed to generate embeddings') from exc

    return {
        'embeddings': embeddings,
        'count': len(embeddings),
        'model': settings.model_path,
        'device_type': embedder.model.device.type,
    }


def main() -> None:
    logger.info(f"Starting {settings.api_name} server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level='info',
    )


if __name__ == '__main__':
    main()
