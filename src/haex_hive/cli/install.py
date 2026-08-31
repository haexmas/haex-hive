"""`haex install` handler.

Stub for Spec 008 Phase 1 setup (T003). Later phases replace the body with the
full transaction pipeline described in
[specs/008-install-transaction/plan.md](../../../specs/008-install-transaction/plan.md).
"""

from __future__ import annotations

import argparse
import sys

from haex_hive.util import exit_codes


def run(args: argparse.Namespace) -> int:
    """Refuse until the Spec 008 install pipeline is implemented."""
    del args
    sys.stderr.write("haex install: not-yet-implemented (Spec 008 Phase 1 stub)\n")
    return exit_codes.SYSTEM_REFUSE
