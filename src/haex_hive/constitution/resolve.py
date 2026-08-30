"""D11 two-step contribution resolution: PublisherManifest -> PublisherAtomEntry -> AtomManifest.

Every atom-id in every `atoms[].includes[]` MUST resolve; an atom that
resolves but does not declare `contributes.constitution` is filtered out
silently (it is a non-contribution, not an error).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from haex_hive.git import revparse as git_revparse
from haex_hive.git import show as git_show
from haex_hive.migrate.transform import clone_dir
from haex_hive.model.atom_manifest import AtomManifest
from haex_hive.model.consumer_manifest import ConsumerManifest
from haex_hive.model.install_lock import ConstitutionSource
from haex_hive.model.publisher_manifest import PublisherManifest
from haex_hive.model.source_url import CanonicalSourceUrl
from haex_hive.util.errors import (
    AtomIdCollisionError,
    ContributionFileNotFoundError,
    MissingAtomManifestError,
    MissingPublisherManifestError,
    PublisherCloneUnavailableError,
)


@dataclass(frozen=True)
class ResolvedConstitutionContribution:
    source: ConstitutionSource
    body: bytes


def resolve_constitution_contributions(
    manifest: ConsumerManifest, state_root: Path
) -> list[ResolvedConstitutionContribution]:
    contributions: list[ResolvedConstitutionContribution] = []
    seen: dict[str, tuple[str, str]] = {}

    for atom_entry in manifest.atoms:
        source = CanonicalSourceUrl.validate(atom_entry.source)
        revision = atom_entry.revision
        repo_dir = clone_dir(state_root, source)
        if not repo_dir.is_dir():
            raise PublisherCloneUnavailableError(
                message=f"no publisher clone found for {source!r}",
                context={"source": source},
            )
        git_revparse.full_sha(repo_dir, revision)

        publisher_bytes = git_show.show_bytes(
            repo_dir,
            revision,
            "manifest.json",
            not_found_error=MissingPublisherManifestError,
        )
        try:
            publisher = PublisherManifest.from_json(publisher_bytes)
        except (ValueError, KeyError) as exc:
            raise MissingPublisherManifestError(
                message=f"publisher manifest at {source!r}@{revision[:12]} is invalid: {exc}",
                context={"source": source, "sha_short": revision[:12]},
            ) from exc

        for atom_id in atom_entry.includes:
            key = (source, revision)
            if atom_id in seen and seen[atom_id] != key:
                raise AtomIdCollisionError(
                    message=(
                        f"atom-id {atom_id!r} resolves to two different (source, revision) pairs"
                    ),
                    context={"atom_id": atom_id},
                )
            seen[atom_id] = key

            publisher_entry = publisher.atoms.get(atom_id)
            if publisher_entry is None:
                raise MissingAtomManifestError(
                    message=f"publisher {publisher.publisher!r} does not declare atom {atom_id!r}",
                    context={"atom_id": atom_id, "publisher": publisher.publisher},
                )

            atom_bytes = git_show.show_bytes(
                repo_dir,
                revision,
                f"{publisher_entry.path}/manifest.json",
                not_found_error=MissingAtomManifestError,
            )
            try:
                atom_manifest = AtomManifest.from_json(atom_bytes)
            except (ValueError, KeyError) as exc:
                raise MissingAtomManifestError(
                    message=f"atom manifest for {atom_id!r} is invalid: {exc}",
                    context={"atom_id": atom_id},
                ) from exc

            if atom_manifest.id != atom_id:
                raise MissingAtomManifestError(
                    message=(
                        f"atom manifest id {atom_manifest.id!r} does not match "
                        f"publisher key {atom_id!r}"
                    ),
                    context={"atom_id": atom_id, "manifest_id": atom_manifest.id},
                )
            if atom_manifest.version != publisher_entry.version:
                raise MissingAtomManifestError(
                    message=(
                        f"atom {atom_id!r} version {atom_manifest.version!r} does not match "
                        f"publisher-declared version {publisher_entry.version!r}"
                    ),
                    context={"atom_id": atom_id},
                )

            if atom_manifest.contributes is None or atom_manifest.contributes.constitution is None:
                continue

            contribution_path = f"{publisher_entry.path}/{atom_manifest.contributes.constitution}"
            body = git_show.show_bytes(
                repo_dir,
                revision,
                contribution_path,
                not_found_error=ContributionFileNotFoundError,
            )
            contributions.append(
                ResolvedConstitutionContribution(
                    source=ConstitutionSource(id=atom_id, revision=revision, source=source),
                    body=body,
                )
            )

    return contributions
