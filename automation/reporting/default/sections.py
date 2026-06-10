from collections import defaultdict
from typing import Dict, Iterable, List, Optional

import pandas as pd

from agents.responses import Hypothesis, Implementation, Summarization
from agents.defs import LoopState
from reporting.default.events import AnalysisEvent, ConclusionEvent, ImplementationErrorEvent, SimulationErrorEvent
from reporting.events import ReportEvent
from reporting.sections import ReportSection
from reporting.tables import MarkdownTableBuilder
from stats import StatisticalAnalysisResults


def dataframe_to_html_table(df: pd.DataFrame) -> str:
    return MarkdownTableBuilder().to_html(df.columns.tolist(), df.itertuples(index=False))


def _code_block(language: str, body: str) -> str:
    return f"```{language}\n{body}\n```"


def _format_run_configuration(hypothesis: Hypothesis) -> str:
    cfg = hypothesis.run_configuration
    return (
        f"- Global iterations: `{cfg.global_iterations}`\n"
        f"- Inner iterations: `{cfg.inner_iterations}`\n"
        f"- Run name: `{cfg.run_name}`\n"
        f"- Random seed: `{cfg.random_seed}`"
    )


def _format_hypothesis(hypothesis: Hypothesis) -> str:
    bugs = "\n".join(f"- {bug}" for bug in hypothesis.previous_implementation_bugs)
    if len(bugs) == 0:
        bugs = "None"
    return (
        f"**Hypothesis**\n\n{hypothesis.hypothesis}\n\n"
        f"**Previous Implementation Bugs**\n\n{bugs}\n\n"
        f"**Run Configuration**\n\n{_format_run_configuration(hypothesis)}"
    )


def _format_implementation(implementation: Implementation) -> str:
    changes = implementation.changes or []
    changes_md = "\n".join(f"- {change}" for change in changes) if len(changes) > 0 else "None"
    return (
        f"**Changes**\n\n{changes_md}\n\n"
        f"<details>\n<summary>Generated attack.c</summary>\n\n"
        f"{_code_block('c', implementation.attack_code)}\n\n"
        f"</details>"
    )


def _format_summary(summary: Summarization) -> str:
    bugs = "\n".join(f"- {bug}" for bug in summary.bugs)
    if len(bugs) == 0:
        bugs = "None"
    return (
        f"**Description**\n\n{summary.description}\n\n"
        f"**Suggestion**\n\n{summary.suggestion}\n\n"
        f"**Failure Reason**\n\n{summary.failure_reason}\n\n"
        f"**Bugs**\n\n{bugs}"
    )


def _format_stats(stats: StatisticalAnalysisResults, compact: bool = False) -> str:
    lines = [
        f"- Global score: `{stats.global_score:.6f}`",
        f"- Iteration score: `{stats.iteration_score:.6f}`",
    ]
    if compact:
        lines.extend([
            "",
            "<details>",
            "<summary>Stats Tables</summary>",
            "",
        ])
    lines.extend([
        "**Global Distribution**",
        "",
        dataframe_to_html_table(stats.global_distribution),
        "",
        "**Global Welch T-Test**",
        "",
        dataframe_to_html_table(stats.global_welch_ttest_data),
        "",
        "**Iteration Welch T-Tests**",
        "",
        dataframe_to_html_table(stats.iteration_welch_ttest_data),
    ])
    if compact:
        lines.extend(["", "</details>"])
    return "\n".join(lines)


def _latest_payload_before_or_at(
        events: Iterable[ReportEvent],
        iteration: int,
        payload_type: type,
) -> Optional[object]:
    result = None
    for event in events:
        if event.iteration <= iteration and isinstance(event.payload, payload_type):
            result = event.payload
    return result


class TimelineSection(ReportSection):
    def __init__(self, index: int = 0):
        super().__init__(index, "Timeline")

    def body(self, ctx: Dict, events: List[ReportEvent]) -> str:
        if len(events) == 0:
            return "No report events were recorded."

        by_iteration = defaultdict(list)
        for event in events:
            by_iteration[event.iteration].append(event)

        sections = []
        for iteration in sorted(by_iteration.keys()):
            sections.append(f"## Iteration {iteration}")
            for event in by_iteration[iteration]:
                sections.append(self._format_event(event))
        return "\n\n".join(sections)

    def _format_event(self, event: ReportEvent) -> str:
        timestamp = event.timestamp.isoformat()
        header = f"### {event.state.name.title()} - {event.kind} ({timestamp})"
        payload = event.payload

        if isinstance(payload, Hypothesis):
            return f"{header}\n\n{_format_hypothesis(payload)}"
        if isinstance(payload, Implementation):
            return f"{header}\n\n{_format_implementation(payload)}"
        if isinstance(payload, StatisticalAnalysisResults):
            return f"{header}\n\n{_format_stats(payload, compact=True)}"
        if isinstance(payload, Summarization):
            return f"{header}\n\n{_format_summary(payload)}"
        if isinstance(event, ImplementationErrorEvent):
            return f"{header}\n\nImplementation did not build or failed code validation.\n\n{_code_block('', str(payload))}"
        if isinstance(event, SimulationErrorEvent):
            return f"{header}\n\nSimulation failed before analysis.\n\n{_code_block('', str(payload))}"
        if event.state == LoopState.SIMULATION and event.kind == "deployment":
            return f"{header}\n\nSimulation completed and produced output for analysis."
        if event.state == LoopState.CONCLUSION:
            return f"{header}\n\nStopping threshold reached."
        return f"{header}\n\n{str(payload)}"


class FinalVerificationSection(ReportSection):
    def __init__(self, index: int = 1):
        super().__init__(index, "Final Verification")

    def body(self, ctx: Dict, events: List[ReportEvent]) -> str:
        stats_event = self._find_final_stats_event(events)
        if stats_event is None or not isinstance(stats_event.payload, StatisticalAnalysisResults):
            return "No final statistics are available."

        iteration = stats_event.iteration
        stats = stats_event.payload
        hypothesis = _latest_payload_before_or_at(events, iteration, Hypothesis)
        implementation = _latest_payload_before_or_at(events, iteration, Implementation)

        sections = [
            f"Final statistics are from iteration `{iteration}`.",
            "",
            "## Final Scores",
            "",
            f"- Global score: `{stats.global_score:.6f}`",
            f"- Iteration score: `{stats.iteration_score:.6f}`",
            "",
        ]

        if isinstance(hypothesis, Hypothesis):
            sections.extend(["## Final Hypothesis", "", _format_hypothesis(hypothesis), ""])
        if isinstance(implementation, Implementation):
            sections.extend(["## Final Implementation", "", _format_implementation(implementation), ""])

        sections.extend([
            "## Final Statistics",
            "",
            _format_stats(stats, compact=True),
        ])
        return "\n".join(sections)

    def _find_final_stats_event(self, events: List[ReportEvent]) -> Optional[ReportEvent]:
        for event in reversed(events):
            if isinstance(event, ConclusionEvent):
                return event
        for event in reversed(events):
            if isinstance(event, AnalysisEvent):
                return event
        return None


def create_default_report_sections() -> List[ReportSection]:
    return [
        TimelineSection(0),
        FinalVerificationSection(1),
    ]
