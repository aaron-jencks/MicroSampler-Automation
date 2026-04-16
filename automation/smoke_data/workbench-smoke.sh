#!/usr/bin/env bash
set -euo pipefail

printf 'workbench smoke script\n'
printf '%s\n' "$*" > script-output.txt
printf 'script invoked with %s args\n' "$#" >&2
