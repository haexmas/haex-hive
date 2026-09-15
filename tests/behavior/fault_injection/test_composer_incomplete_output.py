"""Composer silent-incompleteness fault-injection (Spec 023 T073, FR-012b, exit 32).

Unlike the other `fault_injection/` tests, this failure mode cannot be
triggered by stubbing `invoke_composer` alone (that layer only sees a single
canned response and has no fragment set to compare against). It is only
observable at the `orchestrate.run()` transaction boundary, where the
completeness check has the full input fragment set to diff the Composer's
citations against. Drives `orchestrate.run()` directly with project-local
fragments only (`resolved=()`), so no git repo or publisher fixture is
needed, matching the git-free spirit of the other fault-injection tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spaex.behavior import orchestrate as behavior_orchestrate
from spaex.behavior.composer.clarifications import (
    CLARIFICATIONS_FILENAME,
    CitedFragment,
    Clarification,
    ClarificationsStore,
    derive_key,
    save,
)
from spaex.behavior.composer.failure import ComposerInvalidOutputError
from spaex.behavior.composer.invoke import (
    ComposedShape,
    ComposerInput,
    InvokeOptions,
    InvokeOutcome,
    RuntimeDescriptor,
)
from spaex.behavior.fragment import PROJECT_SCOPE, BehaviorFragment
from spaex.paths import composed_constitution_path
from spaex.util import exit_codes


def _project_fragment(fid: str, body: str) -> BehaviorFragment:
    raw = (
        f"---\nid: {fid}\nkind: constitution_fragment\n"
        f"atom_source: consumer\n---\n{body}"
    ).encode()
    return BehaviorFragment.from_bytes(raw, molecule_id=PROJECT_SCOPE, path=f"_project/{fid}.md")


def _stub_invoke_composer_omitting(omit_scoped_id: str):
    """Return an `invoke_composer` replacement that cites every fragment
    except `omit_scoped_id`, echoing back the spaex-computed hashes so the
    header check in `emit_composed` would pass if reached."""

    def _stub(
        composer_input: ComposerInput,
        *,
        repo_root: Path,
        options: InvokeOptions | None = None,
    ) -> InvokeOutcome:
        bullets = [
            f"- Rule. _[from `{f.scoped_id}`]_\n"
            for f in composer_input.fragments
            if f.scoped_id != omit_scoped_id
        ]
        body = (
            f'<!-- spaex-composed:source_hash="{composer_input.expected_source_hash}" '
            f'build_input_hash="{composer_input.expected_build_input_hash}" version="1" -->\n'
            "# spaex Behavior Harness\n\n## MUST\n\n" + "".join(bullets)
        )
        return InvokeOutcome(
            result=ComposedShape(body=body),
            runtime=RuntimeDescriptor(kind="stub", identifier="test"),
            raw_output=body,
        )

    return _stub


def test_silently_incomplete_output_aborts_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".spaex").mkdir(parents=True)
    dropped = _project_fragment("rule-b", "**MUST** ship signed.\n")
    kept = _project_fragment("rule-a", "**MUST** run tests.\n")

    monkeypatch.setattr(
        behavior_orchestrate,
        "invoke_composer",
        _stub_invoke_composer_omitting(dropped.scoped_id),
    )

    with pytest.raises(ComposerInvalidOutputError) as exc:
        behavior_orchestrate.run(
            repo_root=repo_root,
            state_root=tmp_path / "state",
            resolved=(),
            project_local=(kept, dropped),
        )

    assert exc.value.exit_code == exit_codes.BEHAVIOR_COMPOSER_INVALID_OUTPUT
    assert dropped.scoped_id in str(exc.value)
    assert not composed_constitution_path(repo_root).exists()


def test_fragment_covered_by_valid_clarification_still_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".spaex").mkdir(parents=True)
    dropped = _project_fragment("rule-b", "**MUST** ship signed.\n")
    kept = _project_fragment("rule-a", "**MUST** run tests.\n")

    cited = (
        CitedFragment(
            molecule_id=PROJECT_SCOPE, fragment_id="rule-a", body_sha256=kept.body_hash
        ),
        CitedFragment(
            molecule_id=PROJECT_SCOPE, fragment_id="rule-b", body_sha256=dropped.body_hash
        ),
    )
    key = derive_key(cited)
    store = ClarificationsStore().with_entry(
        Clarification(
            key=key,
            question="alpha/rule-a and _project/rule-b contradict; which wins?",
            cited_fragments=cited,
            answer="keep rule-a only",
            asked_at="2026-09-15T00:00:00Z",
            answered_at="2026-09-15T00:00:00Z",
        )
    )
    save(repo_root / ".spaex" / CLARIFICATIONS_FILENAME, store)

    monkeypatch.setattr(
        behavior_orchestrate,
        "invoke_composer",
        _stub_invoke_composer_omitting(dropped.scoped_id),
    )

    outcome = behavior_orchestrate.run(
        repo_root=repo_root,
        state_root=tmp_path / "state",
        resolved=(),
        project_local=(kept, dropped),
    )

    assert outcome.published is True
    assert composed_constitution_path(repo_root).exists()
