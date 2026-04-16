from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Type

from pydantic import BaseModel


@dataclass
class LLMActionError:
    name: str
    description: str


@dataclass
class LLMConclusion:
    constant_time: bool
    reasoning: str


@dataclass
class LLMActionResponse:
    response_message: Optional[str]
    error: Optional[LLMActionError]
    conclusion: Optional[LLMConclusion]


default_action_response = LLMActionResponse(None, None, None)


LLMActionCallback = Callable[[Dict, Type[BaseModel]], LLMActionResponse]


class LLMAction(ABC):
    def __init__(self, name: str, description: str, schema: Type[BaseModel]):
        self.name = name
        self.description = description
        self.schema = schema

    def format_documentation(self) -> str:
        return f"{self.name}: {self.description}"

    def generate_openai_argument(self) -> Dict:
        return {
            'type': 'function',
            'name': self.name,
            'description': self.description,
            'parameters': self.schema.model_json_schema(),
            'strict': True
        }

    @abstractmethod
    def format_report_line(self, ctx: Dict, kwargs: Type[BaseModel]) -> Optional[str]:
        pass

    @abstractmethod
    def execute(self, ctx: Dict, kwargs: Type[BaseModel]) -> LLMActionResponse:
        pass
