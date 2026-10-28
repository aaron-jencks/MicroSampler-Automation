#!/usr/bin/env python3
"""Behavioral tests for the live BOOM trap-loop detector."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DETECTOR = Path(__file__).parents[1] / "scripts" / "detect-boom-trap-loop.py"
NONEXISTENT_PID = 2_147_483_647


def trace(validity: str = "E", change_one_pc: bool = False) -> str:
    lines: list[str] = []
    sequence = 0
    for event_number in range(4):
        if event_number:
            for pc_number in range(16):
                sequence += 1
                pc = 0x80000100 + pc_number * 4
                if change_one_pc and event_number == 2 and pc_number == 7:
                    pc += 4
                lines.append(
                    f"{sequence}; O3PipeView:fetch: {event_number * 100}:"
                    f"0x{pc:x}:0: {event_number * 100}:DASM(00000013)"
                )
                lines.append(
                    f"{sequence}; O3PipeView:retire: {event_number * 100 + 1}:store: 0"
                )
        lines.append(
            f"--- Cycle={100 + event_number * 379:20d} --- "
            f"Retired Instrs={event_number * 103:20d}"
        )
        lines.append(
            f"Xcpt: V:{validity} Cause:0x1 RobIdx: 0 BadVAddr:0x000000c000001f2c"
        )
    return "\n".join(lines) + "\n"


class DetectorTest(unittest.TestCase):
    def run_detector(self, content: str) -> tuple[subprocess.CompletedProcess[str], Path, tempfile.TemporaryDirectory]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        log = root / "boom.stderr"
        evidence = root / "evidence.json"
        log.write_text(content)
        completed = subprocess.run(
            [
                sys.executable,
                str(DETECTOR),
                "--log",
                str(log),
                "--producer-pid",
                str(NONEXISTENT_PID),
                "--evidence",
                str(evidence),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        return completed, evidence, temporary

    def test_detects_historical_shape(self) -> None:
        completed, evidence, temporary = self.run_detector(trace())
        self.addCleanup(temporary.cleanup)
        self.assertEqual(completed.returncode, 10, completed.stderr)
        result = json.loads(evidence.read_text())
        self.assertEqual(result["classification"], "TRAP_LOOP_DETECTED")
        self.assertEqual(result["signature"]["cycle_period"], 379)
        self.assertEqual(result["signature"]["retired_instruction_period"], 103)
        self.assertEqual(result["signature"]["bad_address"], "0xc000001f2c")

    def test_ignores_invalid_exception_entries(self) -> None:
        completed, evidence, temporary = self.run_detector(trace(validity="-"))
        self.addCleanup(temporary.cleanup)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(evidence.exists())

    def test_requires_identical_committed_pc_periods(self) -> None:
        completed, evidence, temporary = self.run_detector(trace(change_one_pc=True))
        self.addCleanup(temporary.cleanup)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(evidence.exists())


if __name__ == "__main__":
    unittest.main()
