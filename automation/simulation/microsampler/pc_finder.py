from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional


@dataclass
class UUTPCAddresses:
    roi_start: int = -1
    roi_end: int = -1
    calling_address: int = -1
    return_address: int = -1
    start_address: int = -1


disassembly_regex = re.compile(r"\s*(?P<pc>[0-9a-f]+):\s+(?P<encoding>[0-9a-f]+)\s+(?P<opcode>[a-z]+)\s+(?P<operands>[0-9a-z,_.+-]+)(\s+<(?P<func>[a-z0-9_]+)>)?")
jump_address_regex = re.compile(r"ra,(?P<address>[0-9a-f]+)")
func_def_regex = re.compile(r"(?P<address>[0-9a-f]+)(\s+<(?P<func>[a-z0-9_]+)>)?:")


def find_pcs(obj_file: Path, roi_func: str, uut_func: str, warmup: bool = False) -> Optional[UUTPCAddresses]:
    with open(obj_file, 'r') as f:
        marker_reached = True
        funcdef_reached = False

        if warmup:
            marker_reached = False

        result = UUTPCAddresses()
        for line in f.readlines():
            if (match := re.search(disassembly_regex, line)):
                if match.group("encoding") == "00008013":
                    marker_reached = True
                    continue
                if marker_reached:
                    if match.group("opcode") == "jal":
                        pc = match.group("pc")
                        func = match.group("func")
                        if func == roi_func:
                            result.roi_start = int(pc, 16)
                            result.roi_end = int(pc, 16) + 4
                        elif funcdef_reached and func == uut_func:
                            result.calling_address = int(pc, 16)
                            addr = re.search(jump_address_regex, match.group("operands")).group("address")
                            result.start_address = int(addr, 16)
                            result.return_address = result.calling_address + 4
                            break
            elif (match := re.search(func_def_regex, line)):
                fname = match.group("func")
                if fname == roi_func:
                    funcdef_reached = True

        return result if all([
            result.roi_start > -1,
            result.roi_end > -1,
            result.calling_address > -1,
            result.start_address > -1,
            result.return_address > -1,
        ]) else None
