#!/usr/bin/env python3
"""Export the three-way field prompts (triphasic, slowing, background) as standalone .txt files,
the same way export_prompts.py does for the abnormality variants. Single source of truth is the
labeler modules in src/cpu/; this just writes a readable copy next to prompts/v*.txt.

Run:  python prompts/export_field_prompts.py     ->  prompts/<field>.txt
"""
from __future__ import annotations

from pathlib import Path

from cpu.slowing import SYSTEM as SLOW_SYS, FOCAL, GENERALIZED
from cpu.background import SYSTEM as BG_SYS, DISCONTINUOUS, BURST_SUPPRESSION, SUPPRESSED
from cpu.triphasic import SYSTEM as TRI_SYS, SHORT, LONG

OUT = Path(__file__).resolve().parent
FILES = {
    "triphasic_short.txt": (TRI_SYS, SHORT),
    "triphasic_long.txt": (TRI_SYS, LONG),
    "slowing_focal.txt": (SLOW_SYS, FOCAL),
    "slowing_generalized.txt": (SLOW_SYS, GENERALIZED),
    "background_discontinuous.txt": (BG_SYS, DISCONTINUOUS),
    "background_burst_suppression.txt": (BG_SYS, BURST_SUPPRESSION),
    "background_suppressed.txt": (BG_SYS, SUPPRESSED),
}


def main():
    for name, (system, prompt) in FILES.items():
        text = f"[SYSTEM]\n{system}\n\n[PROMPT]\n{prompt}\n"
        (OUT / name).write_text(text)
        print(f"wrote prompts/{name}")


if __name__ == "__main__":
    main()
