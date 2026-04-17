import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

import openai
from openai import OpenAI

from prompting.actions import LLMAction, LLMActionResponse
from reporting.logger import ReportLog


logger = logging.getLogger(__name__)


TemplateFeature = Callable[[Dict, Any, str, List[str]], str]


class OpenAIClient:
    def __init__(self, client: OpenAI, template_name: str, reporter: ReportLog):
        self.client = client
        self.tools: Dict[str, LLMAction] = {}
        self.template_tools: Dict[str, TemplateFeature] = {}
        self.conversation: Optional[str] = None
        self.template: str = template_name
        self.dry_run : bool = False
        self.reporter = reporter

    def create_template_tool(self, tag_name: str, handler: TemplateFeature):
        logger.info(f"creating template tool: {tag_name}")
        self.template_tools[tag_name] = handler

    def create_action(self, action: LLMAction):
        logger.info(f"creating action: {action.name}")
        self.tools[action.name] = action

    def set_template_name(self, template_name: str):
        logger.info(f"setting template name: {template_name}")
        self.template = template_name

    def _create_conversation(self):
        logger.info('creating conversation...')
        if self.dry_run:
            logger.info("dry run requested, skipping conversation creation")
            return
        conv = self.client.conversations.create()
        self.conversation = conv.id

    def clear_conversation(self):
        logger.info('clearing conversation...')
        self.conversation = None

    def generate_preprocessed_template(self, ctx: Dict, content: str) -> str:
        def replace_tags(m: re.Match) -> str:
            tag_name = m.group('tag')
            if tag_name not in self.template_tools:
                raise RuntimeError(f"Unrecognized tag name: {tag_name}")
            arguments = m.group('arguments')
            return self.template_tools[tag_name](ctx, self, tag_name, arguments[1:].split(':') if len(arguments) > 1 else [])

        processed_content = re.sub(
            r'\[\[(?P<tag>[^\]:]+)(?P<arguments>(:[^\]:]+)*)]]',
            replace_tags,
            content,
            flags=re.MULTILINE | re.UNICODE
        )

        return processed_content

    def load_model_template(self, ctx: Dict) -> str:
        fp = Path(ctx["general_prefix"]) / ctx["llm"]["templates"]["prefix"] / ctx["llm"]["templates"][self.template]
        with open(fp, 'r') as f:
            template = f.read()

        return self.generate_preprocessed_template(ctx, template)

    def prompt_model(self, ctx: Dict, msg: Union[str, List[Dict]]) -> List[LLMActionResponse]:
        if self.conversation is None:
            self._create_conversation()

        logger.info('prompting model...')
        logger.info(f'conversation: {self.conversation}')
        logger.info(f'template: {self.template}')
        # if isinstance(msg, str):
        #     logger.info(f'msg: {msg}')
        # else:
        #     logger.info('msg is a tool response')
        logger.info(f'msg: {msg}')

        if self.dry_run:
            logger.info("dry run requested, skipping actual prompting")
            return []

        while True:
            try:
                response = self.client.responses.create(
                    model=ctx["llm"]["model"],
                    conversation=self.conversation,
                    instructions=self.load_model_template(ctx),
                    tools=[
                        t.generate_openai_argument() for t in self.tools.values()
                    ],
                    input=msg,
                )
                break
            except openai.RateLimitError as e:
                sleep_time = float(re.match(r"Please try again in (?P<time>\d+(\.\d+)?)", e.message).group('time')) + 1
                logger.info(f"rate limit exceeded waiting for {sleep_time} seconds")
                time.sleep(sleep_time)

        responses = []

        for item in response.output:
            if item.type == 'function_call':
                if item.name not in self.tools:
                    raise RuntimeError(f"Unrecognized function name: {item.name}")
                args_dict = json.loads(item.arguments)
                tool = self.tools[item.name]
                args = tool.schema.model_validate(args_dict)
                responses.append((item, tool.execute(ctx, args)))
            elif item.type == 'message':
                for content in item.content:
                    logger.info(f'model text output: {content.text}')
                    line = content.text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
                    self.reporter.log_transcript(f'model thought: {line}')
            else:
                logger.info(f'uncategorized model response: {item.content}')

        return responses
