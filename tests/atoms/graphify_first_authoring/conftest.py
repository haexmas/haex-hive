"""Test package conftest for the graphify-first-authoring atom.

The atom's scripts (``install.py``, ``_refresh.py``, ``_snapshot.py``,
``_tracked_branches.py``) live under ``.specify/molecules/graphify-first-authoring/``
and are intentionally not packaged into the ``haex_hive`` distribution — they
are per-repo tooling installed into ``.git/hooks/``. Expose them on ``sys.path``
so tests can ``import`` them as plain modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOLECULE_DIR = _REPO_ROOT / ".specify" / "molecules" / "graphify-first-authoring"
_HOOKS_DIR = _MOLECULE_DIR / "hooks"

for path in (_MOLECULE_DIR, _HOOKS_DIR):
    sys_path_entry = str(path)
    if sys_path_entry not in sys.path:
        sys.path.insert(0, sys_path_entry)
