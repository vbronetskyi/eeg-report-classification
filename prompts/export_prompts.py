#!/usr/bin/env python3
"""Regenerate prompts/v*.txt from src/core/prompt.py — the single source of truth."""
import os, importlib
from pathlib import Path
OUT = Path(__file__).resolve().parent
for v in ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"]:
    os.environ["PROMPT_VARIANT"] = v
    import core.prompt as p; importlib.reload(p)
    txt = f"#### SYSTEM ####\n\n{p.SYSTEM}\n\n#### USER PROMPT ({v}) ####\n\n"
    txt += p.build_prompt("<EEG report text is appended here>")
    (OUT / f"{v}.txt").write_text(txt); print("wrote", f"prompts/{v}.txt")
