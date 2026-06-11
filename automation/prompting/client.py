import logging
from pathlib import Path
from typing import Dict, Optional, Type
import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from config import BaseConfig

logger = logging.getLogger(__file__)


def _create_context_compaction_middleware(ctx: BaseConfig, model: ChatOpenAI):
    config = ctx.llm.context_compaction
    if not config.enabled:
        return []

    return [
        SummarizationMiddleware(
            model=model,
            trigger=("tokens", config.trigger_tokens),
            keep=("messages", config.keep_messages),
            trim_tokens_to_summarize=config.trim_tokens_to_summarize,
        )
    ]


class Agent:
    def __init__(
            self, ctx: BaseConfig, model: str,
            name: str, output_format: Type[BaseModel],
            system_prompt: str,
            templates: Dict[str, Path],
            dry_run: bool = False
    ):
        self.ctx = ctx
        self.model = model
        self.name = name
        self.system_prompt = system_prompt
        self.output_format = output_format
        self.thread_id = str(uuid.uuid4())
        self.dry_run = dry_run
        self.templates = templates
        if ctx['llm']['api_key'] != '':
            self.model = ChatOpenAI(
                model=model,
                api_key=ctx['llm']['api_key'],
            )
        else:
            self.model = ChatOpenAI(
                model=model,
            )
        self.agent = create_agent(
            model=self.model,
            system_prompt=system_prompt,
            middleware=_create_context_compaction_middleware(ctx, self.model),
            response_format=ToolStrategy(self.output_format),
            checkpointer=InMemorySaver(),
        )

    def get_agent_prompt(self, name: str) -> str:
        with open(self.templates[name], 'r') as template:
            return template.read()

    def prompt_model(self, ctx: BaseConfig, prompt: str) -> Optional[BaseModel]:
        logger.info(f"prompting {self.name} agent with {prompt}")
        if self.dry_run:
            return None
        response = self.agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            config={
                "configurable": {
                    "thread_id": self.thread_id,
                }
            }
        )
        return response["structured_response"]
