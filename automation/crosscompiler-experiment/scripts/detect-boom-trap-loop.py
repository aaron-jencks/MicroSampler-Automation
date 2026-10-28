#!/usr/bin/env python3
"""Watch a BOOM verbose trace and report a conservative architectural trap loop.

The detector follows a growing stderr trace.  A loop is reported only after all
of the following repeat four times for an architecturally valid exception:

* instruction-access-fault cause 1 and the same bad virtual address;
* the same positive simulated-cycle and retired-instruction deltas; and
* the same non-trivial sequence of retired PCs for three consecutive periods.

This deliberately does not flag a hot PC, an invalid Xcpt entry, an early WFI,
or a short ordinary software loop.  Exit 10 means a loop was detected; exit 0
means the producer exited without satisfying the detector; other exits are
detector failures.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
import os
from pathlib import Path
import re
import time


CYCLE_RE = re.compile(
    r"---\s+Cycle=\s*([0-9]+)\s+---\s+Retired Instrs=\s*([0-9]+)"
)
FETCH_RE = re.compile(
    r"^\s*([0-9]+);\s+O3PipeView:fetch:\s*([0-9]+):0x([0-9a-fA-F]+):"
)
RETIRE_RE = re.compile(
    r"^\s*([0-9]+);\s+O3PipeView:retire:\s*([0-9]+)"
)
XCPT_RE = re.compile(
    r"Xcpt:\s*V:([A-Za-z-])\s+Cause:0x([0-9a-fA-F]+).*"
    r"BadVAddr:0x([0-9a-fA-F]+)"
)

REQUIRED_EVENTS = 4
REQUIRED_INTERVALS = REQUIRED_EVENTS - 1
MIN_RESOLVED_PCS = 16
MAX_RETIRED_HISTORY = 16384
MAX_FETCH_HISTORY = 262144


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--producer-pid", type=int, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=float, default=0.1)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")

    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    fetch_pc: dict[int, str] = {}
    fetch_order = deque()
    retired = deque(maxlen=MAX_RETIRED_HISTORY)
    retired_index = 0
    events = defaultdict(lambda: deque(maxlen=REQUIRED_EVENTS))
    cycle = None
    retired_total = None
    last_event_identity = None
    offset = 0

    while True:
        made_progress = False
        try:
            with args.log.open("r", encoding="utf-8", errors="replace") as trace:
                trace.seek(offset)
                while True:
                    line = trace.readline()
                    if not line:
                        break
                    made_progress = True
                    offset = trace.tell()

                    if match := CYCLE_RE.search(line):
                        cycle = int(match.group(1))
                        retired_total = int(match.group(2))
                        continue

                    if match := FETCH_RE.search(line):
                        sequence = int(match.group(1))
                        fetch_pc[sequence] = "0x" + match.group(3).lower()
                        fetch_order.append(sequence)
                        if len(fetch_order) > MAX_FETCH_HISTORY:
                            fetch_pc.pop(fetch_order.popleft(), None)
                        continue

                    if match := RETIRE_RE.search(line):
                        sequence = int(match.group(1))
                        retired_index += 1
                        retired.append((retired_index, fetch_pc.pop(sequence, None)))
                        continue

                    match = XCPT_RE.search(line)
                    if not match or match.group(1).upper() != "E" or cycle is None:
                        continue

                    cause = int(match.group(2), 16)
                    bad_address = "0x" + match.group(3).lower().lstrip("0")
                    if bad_address == "0x":
                        bad_address = "0x0"
                    # The historical PK failure is an instruction access fault.
                    # Other causes are retained in the trace but do not trigger
                    # this detector because legitimate programs may trap often.
                    if cause != 1:
                        continue

                    identity = (cycle, retired_total, cause, bad_address)
                    if identity == last_event_identity:
                        continue
                    last_event_identity = identity
                    key = (cause, bad_address)
                    prior = events[key][-1] if events[key] else None
                    start_index = prior["retired_index"] if prior else retired_index
                    interval_pcs = [
                        pc for index, pc in retired
                        if index > start_index and pc is not None
                    ]
                    event = {
                        "cycle": cycle,
                        "retired_total": retired_total,
                        "retired_index": retired_index,
                        "interval_pcs": interval_pcs,
                    }
                    events[key].append(event)
                    recent = list(events[key])
                    if len(recent) != REQUIRED_EVENTS:
                        continue

                    cycle_deltas = [
                        recent[index]["cycle"] - recent[index - 1]["cycle"]
                        for index in range(1, len(recent))
                    ]
                    retired_deltas = [
                        recent[index]["retired_total"] - recent[index - 1]["retired_total"]
                        for index in range(1, len(recent))
                    ]
                    pc_intervals = [event["interval_pcs"] for event in recent[1:]]
                    periodic = (
                        len(set(cycle_deltas)) == 1
                        and cycle_deltas[0] > 0
                        and len(set(retired_deltas)) == 1
                        and retired_deltas[0] > 0
                    )
                    pc_periodic = (
                        len(pc_intervals) == REQUIRED_INTERVALS
                        and len(pc_intervals[0]) >= MIN_RESOLVED_PCS
                        and all(interval == pc_intervals[0] for interval in pc_intervals[1:])
                    )
                    if not (periodic and pc_periodic):
                        continue

                    counts: dict[str, int] = defaultdict(int)
                    for pc in pc_intervals[0]:
                        counts[pc] += 1
                    evidence = {
                        "classification": "TRAP_LOOP_DETECTED",
                        "signature": {
                            "valid_exception": True,
                            "cause": cause,
                            "cause_name": "instruction_access_fault",
                            "bad_address": bad_address,
                            "event_count": REQUIRED_EVENTS,
                            "cycle_period": cycle_deltas[0],
                            "retired_instruction_period": retired_deltas[0],
                            "resolved_pc_count_per_period": len(pc_intervals[0]),
                            "retired_pc_sequence": pc_intervals[0],
                            "retired_pc_histogram": dict(
                                sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                            ),
                        },
                        "events": [
                            {
                                "cycle": item["cycle"],
                                "retired_total": item["retired_total"],
                            }
                            for item in recent
                        ],
                        "trace": str(args.log),
                        "trace_offset_bytes": offset,
                        "detector": {
                            "required_events": REQUIRED_EVENTS,
                            "required_equal_periods": REQUIRED_INTERVALS,
                            "minimum_resolved_pcs": MIN_RESOLVED_PCS,
                        },
                    }
                    atomic_json(args.evidence, evidence)
                    return 10
        except FileNotFoundError:
            pass

        if not pid_alive(args.producer_pid):
            # One extra iteration drains bytes written immediately before exit.
            if made_progress:
                continue
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
