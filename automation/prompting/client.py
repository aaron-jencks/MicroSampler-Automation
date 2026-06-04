import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type
import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel


logger = logging.getLogger(__file__)


def _get_context_compaction_config(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx.get("llm", {}).get("context_compaction", {})


def _create_context_compaction_middleware(ctx: Dict[str, Any], model: ChatOpenAI):
    config = _get_context_compaction_config(ctx)
    if not config.get("enabled", True):
        return []

    trigger_tokens = int(config.get("trigger_tokens", 80000))
    keep_messages = int(config.get("keep_messages", 12))
    trim_tokens_to_summarize = config.get("trim_tokens_to_summarize", 4000)
    if trim_tokens_to_summarize is not None:
        trim_tokens_to_summarize = int(trim_tokens_to_summarize)

    return [
        SummarizationMiddleware(
            model=model,
            trigger=("tokens", trigger_tokens),
            keep=("messages", keep_messages),
            trim_tokens_to_summarize=trim_tokens_to_summarize,
        )
    ]


class Agent:
    def __init__(
            self, ctx: Dict, model: str,
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

    def prompt_model(self, ctx: Dict, prompt: str) -> Optional[BaseModel]:
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
