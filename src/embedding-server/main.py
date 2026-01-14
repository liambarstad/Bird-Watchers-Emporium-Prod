import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from config import get_settings
from embedder import Embedder

settings = get_settings()

app = FastAPI(title=settings.api_name, version=settings.api_version)

embedder = Embedder(
    model_path=settings.model_path,
    model_device=settings.model_device,
)


@app.get('/health')
def health_check() -> dict:
    return {'status': 'ok', 'env': settings.app_env}


class EmbedTextRequest(BaseModel):
    texts: list[str]


@app.post('/embed/text')
def embed_text(request: EmbedTextRequest) -> dict:



def main() -> None:
    uvicorn.run(
        app, 
        host=settings.api_host, 
        port=settings.api_port, 
        log_level='info'
    )


if __name__ == '__main__':
    main()
