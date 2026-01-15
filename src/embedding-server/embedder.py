import torch
from colpali_engine.models import BiQwen2_5, BiQwen2_5_Processor


class Embedder:
    def __init__(self, model_path: str, model_device: str):
        self.model = BiQwen2_5.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map=None,
            attn_implementation=None,
            #attn_implementation='sdpa',
        ).eval()\
            .to(model_device)

        self.processor = BiQwen2_5_Processor.from_pretrained(model_path, user_fast=False)

    def embed_text(self, queries: list[str]) -> list[list[float]]:
        with torch.no_grad():
            batch_queries = self.processor.process_queries(queries).to(self.model.device)
            return self.model(**batch_queries).tolist()