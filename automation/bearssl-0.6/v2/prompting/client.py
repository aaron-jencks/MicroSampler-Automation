import json
import logging
import re
from typing import Dict, List, Optional, Callable

from openai import OpenAI

from actions import LLMAction, LLMActionResponse


logger = logging.getLogger(__name__)


TemplateFeature = Callable[[Dict, str, str], str]


class OpenAIClient:
    def __init__(self, client: OpenAI, template_name: str):
        self.client = client
        self.tools: Dict[str, LLMAction] = {}
        self.template_tools: Dict[str, TemplateFeature] = {}
        self.conversation: Optional[str] = None
        self.template: str = template_name

    def create_template_tool(self, tag_name: str, handler: TemplateFeature):
        self.template_tools[tag_name] = handler

    def create_action(self, action: LLMAction):
        self.tools[action.name] = action

    def set_template_name(self, template_name: str):
        self.template = template_name

    def _create_conversation(self):
        conv = self.client.conversations.create()
        self.conversation = conv.id

    def clear_conversation(self):
        self.conversation = None

    def _load_model_template(self, ctx: Dict) -> str:
        with open(ctx["llm"]["templates"][self.template], 'r') as f:
            template = f.read()

        def replace_tags(m: re.Match) -> str:
            tag_name = m.group('tag')
            if tag_name not in self.template_tools:
                raise RuntimeError(f"Unrecognized tag name: {tag_name}")
            argument = m.group('argument')
            return self.template_tools[tag_name](ctx, tag_name, argument)

        processed_template = re.sub(
            r'\[\[(?P<tag>[^\]]+):(?P<argument>[^\]]+)]]',
            replace_tags,
            template,
            flags=re.MULTILINE | re.UNICODE
        )

        return processed_template

    def prompt_model(self, ctx: Dict, msg: str) -> List[LLMActionResponse]:
        if self.conversation is None:
            self._create_conversation()

        logger.info('prompting model...')
        logger.info(f'conversation: {self.conversation}')
        logger.info(f'template: {self.template}')

        response = self.client.responses.create(
            model=ctx["llm"]["model"],
            conversation=self.conversation,
            instructions=self._load_model_template(ctx),
            tools=[
                t.gene-rate_openai_argument() for t in self.tools.values()
            ],
            input=msg,
        )

        responses = []

        for item in response.output:
            if item.type == 'function_call':
                if item.name not in self.tools:
                    raise RuntimeError(f"Unrecognized function name: {item.name}")
                args_dict = json.loads(item.arguments)
                tool = self.tools[item.name]
                args = tool.schema.model_validate(args_dict)
                responses.append(tool.execute(ctx, args))
            else:
                logger.info(f'model response: {item.content}')

        return responses
