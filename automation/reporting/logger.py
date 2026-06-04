import logging
import shutil
from typing import Dict, List

from reporting.events import ReportEvent
from reporting.sections import ReportSection
from reporting.utils import get_report_directory


logger = logging.getLogger(__name__)


class ReportLog:
    def __init__(self):
        self.simulation_count = 0
        self.events: List[ReportEvent] = []
        self.sections: List[ReportSection] = []

    def add_section(self, section: ReportSection):
        self.sections.append(section)

    def log(self, d: ReportEvent):
        self.events.append(d)

    def generate_report(self, ctx: Dict):
        logger.info(f'generating report to {ctx["final_report"]["file"]}')

        prefix = get_report_directory(ctx)
        if ctx["final_report"]["clear_report_area"] and prefix.exists():
            shutil.rmtree(prefix)
            prefix.mkdir(parents=True, exist_ok=True)
        plots_prefix = prefix / ctx["final_report"]["plots_prefix"]
        plots_prefix.mkdir(parents=True, exist_ok=True)

        builder = f"<h1>{ctx['final_report']['run_name']} Final Report</h1>\n\n"

        self.sections.sort(key=lambda s: s.index)

        builder += "\n\n".join([s.generate_section(ctx) for s in self.sections])

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

        fpath = get_report_directory(ctx) / ctx["final_report"]["file"]
        with open(fpath, 'w+') as fp:
            fp.write(full_html)
