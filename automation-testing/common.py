from typing import List, Dict

from pydantic import BaseModel


class TokenUsage(BaseModel):
    input_count: List[int] = []
    output_count: List[int] = []


class StatisticalAnalysisResults(BaseModel):
    iteration_scores: List[List[float]]
    success_iterations: List[int]
    success_token_usage: Dict[str, TokenUsage]
    failure_token_usage: Dict[str, TokenUsage]


class CollatedData(BaseModel):
    candidate_iterations: int
    results: Dict[str, StatisticalAnalysisResults]
