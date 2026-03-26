import argparse
import pathlib
import timeit

from openai import OpenAI

from v2 import v2

def get_timing_information(key: str, iters: int, loops: int = 1000) -> float:
    return timeit.timeit(
        lambda: v2(key, iters=iters),
        number=loops,
    )


def 


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('key', type=str, help='the key to use')
    ap.add_argument('--iters', type=int, default=100, help='the number of iterations')
    ap.add_argument(
        '--key-path', type=pathlib.Path, 
        default=pathlib.Path('../../../scripts/keys'),
        help='the location of the key files'
    )
    args = ap.parse_args()

    with open(args.key_path / f'{args.key}.key', 'r') as fp:
        key_value = fp.read()

    
