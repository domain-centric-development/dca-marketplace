#!/usr/bin/env python3
"""Factory CLI — what shows and coordinates. Its usage: `dca_factory/delivery/adapter/incoming/cli/cli_command.py`."""
import os, sys
sys.pycache_prefix = sys.pycache_prefix or os.path.join(os.path.expanduser("~"), ".cache", "dca-factory")  # bytecode, never in the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dca_factory import utf8_streams  # noqa: E402
from dca_factory.delivery.adapter.incoming.cli.cli_command import main  # noqa: E402

if __name__ == "__main__":
    utf8_streams()
    sys.exit(main(sys.argv[1:]))
