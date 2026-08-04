"""Human-readable vs. structured JSON output, matching ``src/output.ts``.

Note: unlike :mod:`computeledger.canonical`, this module's JSON output is
never hashed or signed — it exists purely for human/agent consumption — so
it uses Python's regular ``json.dumps`` pretty-printing rather than the
byte-exact canonical serializer.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def print_result(data: Any, human_text: str, json_output: bool) -> None:
    if json_output:
        sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(human_text + "\n")


def print_error(message: str, json_output: bool) -> None:
    if json_output:
        sys.stderr.write(json.dumps({"error": message}, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stderr.write(f"Error: {message}\n")
