from typing import Any, Iterable, Sequence

import markdown
import pandas as pd


class MarkdownTableBuilder:
    TABLE_STYLE = "border-collapse: collapse; width: 100%;"
    HEADER_STYLE = "border: 1px solid #999; padding: 0.35rem 0.5rem; text-align: left; background: #f2f2f2;"
    CELL_STYLE = "border: 1px solid #999; padding: 0.35rem 0.5rem; text-align: left;"

    def _format_value(self, value: Any) -> str:
        if pd.isna(value):
            return "N/A"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    def to_markdown(self, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = "| " + " | ".join("---" for _ in headers) + " |"
        body_rows = [
            "| " + " | ".join(self._format_value(value) for value in row) + " |"
            for row in rows
        ]
        return "\n".join([header_row, separator_row, *body_rows])

    def to_html(self, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
        html = markdown.markdown(
            self.to_markdown(headers, rows),
            extensions=["tables"],
        )
        html = html.replace("<table>", f'<table style="{self.TABLE_STYLE}">')
        html = html.replace("<th>", f'<th style="{self.HEADER_STYLE}">')
        html = html.replace("<td>", f'<td style="{self.CELL_STYLE}">')
        return html
