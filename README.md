# haex-hive

## `haex` CLI

Install:

```bash
pip install haex-hive
```

Commands:

```bash
haex migrate                         # rewrite v1 .haex-hive.json into a v2 sidecar
haex constitution assemble           # produce .haex-hive/constitution.md + install.lock
haex constitution show               # print the effective constitution
```

See [specs/007-unified-manifest-v2/quickstart.md](specs/007-unified-manifest-v2/quickstart.md) for a full walkthrough of each command, including the multi-source LLM-merge flow and every refusal path.
