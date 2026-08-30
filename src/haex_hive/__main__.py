"""`python -m haex_hive` entry point."""

from __future__ import annotations

import sys

from haex_hive.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
