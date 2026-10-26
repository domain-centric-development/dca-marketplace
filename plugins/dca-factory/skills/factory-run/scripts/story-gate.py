#!/usr/bin/env python3
"""Story gate — what decides a stage. Its usage: `dca_factory/delivery/adapter/incoming/gate/gate_command.py`."""
import os, sys
sys.pycache_prefix = sys.pycache_prefix or os.path.join(os.path.expanduser("~"), ".cache", "dca-factory")  # bytecode, never in the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dca_factory import utf8_streams  # noqa: E402
from dca_factory.delivery.adapter.incoming.gate.gate_command import main  # noqa: E402

if __name__ == "__main__":
    utf8_streams()
    sys.exit(main(sys.argv[1:]))
