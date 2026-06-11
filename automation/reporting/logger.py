from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
from typing import List, Tuple

from config import BaseConfig
from reporting.events import ReportEvent
from reporting.sections import ReportSection
from reporting.utils import get_report_directory


logger = logging.getLogger(__name__)


def generate_timestamped_report_file_name(ctx: BaseConfig) -> Tuple[Path, Path]:
    dname = get_report_directory(ctx)
    fname = dname / ctx["final_report"]["file"]
    dstring = datetime.now(tz=timezone.utc).strftime("%m_%d_%Y_%H_%M_%S")
    return dname, fname.with_stem(f"{fname.stem}_{dstring}")


class ReportLog:
    def __init__(self):
        self.simulation_count = 0
        self.events: List[ReportEvent] = []
        self.sections: List[ReportSection] = []

    def add_section(self, section: ReportSection):
        self.sections.append(section)

    def log(self, d: ReportEvent):
        self.events.append(d)

    def generate_report(self, ctx: BaseConfig):
        prefix, output_fname = generate_timestamped_report_file_name(ctx)
        logger.info(f'generating report to {output_fname.resolve()}')

        if ctx["final_report"]["clear_report_area"] and prefix.exists():
            shutil.rmtree(prefix)
            prefix.mkdir(parents=True, exist_ok=True)
        plots_prefix = prefix / ctx["final_report"]["plots_prefix"]
        plots_prefix.mkdir(parents=True, exist_ok=True)

        builder = f"<h1>{ctx['final_report']['run_name']} Final Report</h1>\n\n"

        self.sections.sort(key=lambda s: s.index)

        builder += "\n\n".join([s.generate_section(ctx, self.events) for s in self.sections])

        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Report</title>
        </head>
        <body>
        {builder}
        </body>
        </html>
        """

        with open(output_fname, 'w+') as fp:
            fp.write(full_html)

        logger.info(f"wrote report to {output_fname.resolve()}")
