#!/usr/bin/env python3
"""§11 entrypoint: ``python main.py "build a rate limiter"`` (implies ``run``)."""

import sys

from xr_ai_co.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] not in ("run", "resume", "pause", "status", "-h", "--help"):
        argv = ["run", *argv]
    main(argv)
