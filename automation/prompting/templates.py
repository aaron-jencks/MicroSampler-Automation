import logging
import re
from typing import Any, Dict, List, Callable, Optional

from config import BaseConfig

logger = logging.getLogger(__file__)


TemplateFeature = Callable[[BaseConfig, Any, str, List[str], Optional[Dict[str, Any]]], str]


class TemplateController:
    def __init__(self):
        self.template_tools: Dict[str, TemplateFeature] = {}

    def create_template_tool(self, tag_name: str, handler: TemplateFeature):
        logger.info(f"creating template tool: {tag_name}")
        self.template_tools[tag_name] = handler

    def process_template(self, ctx: BaseConfig, content: str, kwargs: Optional[Dict[str, Any]] = None) -> str:
        def replace_tags(m: re.Match) -> str:
            tag_name = m.group('tag')
            if tag_name not in self.template_tools:
                raise RuntimeError(f"Unrecognized tag name: {tag_name}")
            arguments = m.group('arguments')
            return self.template_tools[tag_name](
                ctx, self,
                tag_name, arguments[1:].split(':') if len(arguments) > 1 else [], kwargs
            )

        processed_content = re.sub(
            r'\[\[(?P<tag>[^\]:]+)(?P<arguments>(:[^\]:]+)*)]]',
            replace_tags,
            content,
            flags=re.MULTILINE | re.UNICODE
        )

        return processed_content
