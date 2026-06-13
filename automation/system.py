from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Dict, List

from config import BaseConfig


@dataclass
class CacheInfo:
    name: str
    level: str
    type: str
    size: str
    coherency_line_size: str
    ways_of_associativity: str
    number_of_sets: str
    shared_cpu_list: str


def get_cache_information(ctx: BaseConfig) -> List[CacheInfo]:
    # TODO make this cross-platform
    result = []

    cache_root = Path("/sys/devices/system/cpu/cpu0/cache")

    for index in sorted(cache_root.glob("index*")):
        kwargs = {
            "name": index.name,
        }
        for field in ["level", "type", "size", "coherency_line_size",
                      "ways_of_associativity", "number_of_sets",
                      "shared_cpu_list"]:
            value = (index / field).read_text().strip()
            kwargs[field] = value
        result.append(CacheInfo(**kwargs))

    return result


def read_cpuinfo(ctx: BaseConfig) -> Dict:
    # TODO make this cross-platform
    cpu_text_data = Path("/proc/cpuinfo").read_text().splitlines(keepends=False)
    result = {}
    for line in cpu_text_data:
        arr = re.split(r"\t*:\s*", line)
        k = arr[0]
        if len(arr) < 2:
            v = None
        else:
            v = arr[1]
        result[k] = v
    return result
