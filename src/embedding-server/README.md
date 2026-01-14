## Embedding Server

Serves multimodal embeddings (text + image) over HTTP for the model:

- `nomic-ai/nomic-embed-multimodal-3b`

### Endpoints

- `GET /health`
- `GET /info`
- `POST /embed/text`
  - Body: `{ "texts": ["..."], "normalize": true }`
- `POST /embed/image`
  - Multipart: `file=@image.jpg` (field name: `file`)
  - OR JSON: `{ "image_url": "https://...", "normalize": true }`

### Notes

- The server auto-selects `cuda` if available; otherwise it runs on CPU.
- For Neo4j ingestion/search, you typically store embeddings on nodes (e.g. `Fact.embedding`, `Image.embedding`) and query via Neo4j vector indexes.


