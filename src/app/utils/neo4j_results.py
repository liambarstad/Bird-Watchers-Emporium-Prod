from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SimilarityScore(BaseModel):
    type: Literal["lexical", "semantic", "visual"]
    score: float


class FactResult(BaseModel):
    title: str
    text: str
    similarity: SimilarityScore


class ImageResult(BaseModel):
    url: str
    similarity: SimilarityScore


class ContinentResult(BaseModel):
    name: str


class CountryResult(BaseModel):
    name: str


class RegionResult(BaseModel):
    name: str


class BirdResult(BaseModel):
    name: str
    order: str
    family: str
    genus: str
    species: str

    facts: list[FactResult] = Field(default_factory=list)
    images: list[ImageResult] = Field(default_factory=list)
    continents: list[ContinentResult] = Field(default_factory=list)
    countries: list[CountryResult] = Field(default_factory=list)
    regions: list[RegionResult] = Field(default_factory=list)


class ResultIds(BaseModel):
    bird_ids: list[int] = Field(default_factory=list)
    fact_ids: list[int] = Field(default_factory=list)
    image_ids: list[int] = Field(default_factory=list)


class Neo4jQueryStep(BaseModel):
    description: str
    result_ids: ResultIds
    result_sample: list[BirdResult] = Field(default_factory=list)

    parent_step: Optional[int] = None


class Neo4jResults(BaseModel):
    steps: list[Neo4jQueryStep] = Field(default_factory=list)

    def step_descriptions(self) -> list[str]:
        return [
            f'{ind+1}. "{step.description}", num results: {len(step.result_ids.bird_ids)}'
            for ind, step in enumerate(self.steps)
        ]

    def num_results(self) -> int:
        return len(self.steps[-1].result_ids.bird_ids)

    def sample(self) -> list[BirdResult]:
        return self.steps[-1].result_sample