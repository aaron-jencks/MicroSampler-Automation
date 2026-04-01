import json
import logging
import re
from typing import Any, Dict, List, Optional, Callable

from openai import OpenAI

from actions import LLMAction, LLMActionResponse


logger = logging.getLogger(__name__)


TemplateFeature = Callable[[Dict, Any, str, List[str]], str]


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

    def generate_preprocessed_template(self, ctx: Dict, content: str) -> str:
        def replace_tags(m: re.Match) -> str:
            tag_name = m.group('tag')
            if tag_name not in self.template_tools:
                raise RuntimeError(f"Unrecognized tag name: {tag_name}")
            arguments = m.group('arguments')
            return self.template_tools[tag_name](ctx, self, tag_name, arguments[1:].split(':'))

        processed_content = re.sub(
            r'\[\[(?P<tag>[^\]:]+)(?P<arguments>(:[^\]:]+)*)]]',
            replace_tags,
            content,
            flags=re.MULTILINE | re.UNICODE
        )

        return processed_content

    def load_model_template(self, ctx: Dict) -> str:
        with open(ctx["llm"]["templates"][self.template], 'r') as f:
            template = f.read()

        return self.generate_preprocessed_template(ctx, template)

    def prompt_model(self, ctx: Dict, msg: str) -> List[LLMActionResponse]:
        if self.conversation is None:
            self._create_conversation()

        logger.info('prompting model...')
        logger.info(f'conversation: {self.conversation}')
        logger.info(f'template: {self.template}')
        logger.info(f'msg: {msg}')

        response = self.client.responses.create(
            model=ctx["llm"]["model"],
            conversation=self.conversation,
            instructions=self.load_model_template(ctx),
            tools=[
                t.generate_openai_argument() for t in self.tools.values()
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
                responses.append((item, tool.execute(ctx, args)))
            else:
                logger.info(f'model response: {item.content}')

        return responses
