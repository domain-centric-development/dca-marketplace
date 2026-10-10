#!/usr/bin/env python3
"""Factory CLI — what shows and coordinates a run. The code is `dca_factory/cli.py` beside this file; its docstring is the usage."""
import os, sys
sys.dont_write_bytecode = True                              # a project carries no __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dca_factory import utf8_streams  # noqa: E402
from dca_factory.cli import main  # noqa: E402

if __name__ == "__main__":
    utf8_streams()
    sys.exit(main(sys.argv[1:]))
