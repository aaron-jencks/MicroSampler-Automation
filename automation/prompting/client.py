import logging
from typing import Dict
import uuid

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel


logger = logging.getLogger(__file__)


class Agent:
    def __init__(self, ctx: Dict, name: str, output_format: BaseModel, system_prompt: str):
        self.ctx = ctx
        self.name = name
        self.system_prompt = system_prompt
        self.output_format = output_format
        self.thread_id = str(uuid.uuid4())
        if ctx['llm']['api_key'] != '':
            self.model = ChatOpenAI(
                model=ctx['llm']['model'],
                api_key=ctx['llm']['api_key'],
            )
        else:
            self.model = ChatOpenAI(
                model=ctx['llm']['model'],
            )
        self.agent = create_agent(
            model=self.model,
            system_prompt=system_prompt,
            response_format=ToolStrategy(self.output_format),
            checkpointer=InMemorySaver(),
        )

    def prompt_model(self, ctx: Dict, prompt: str) -> BaseModel:
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
