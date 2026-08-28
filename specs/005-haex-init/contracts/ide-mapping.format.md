# Contract: IDE Schema-Mapping Files

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Date**: 2026-08-27

## Purpose

Defines the exact shapes `haex-init` writes into the two supported IDE
families' project-local schema-mapping files, plus the detection and
merge rules that make writes safe on projects that already carry
unrelated settings.

## VSCode Family (`.vscode/settings.json`)

### Target file

- Path: `<project-root>/.vscode/settings.json`
- Serialization: JSON with `indent=2`, LF line endings, trailing LF.
- IDEs covered: VSCode, VSCode Insiders, Cursor, Windsurf.

### Canonical entry

The `json.schemas` array MUST contain an entry with exactly this
shape:

```json
{
  "fileMatch": [".haex-hive.json"],
  "url": "./.specify/schemas/haex-hive.schema.json"
}
```

### Merge rules (Decision 5)

- File missing → create with:

  ```json
  {
    "json.schemas": [
      {
        "fileMatch": [".haex-hive.json"],
        "url": "./.specify/schemas/haex-hive.schema.json"
      }
    ]
  }
  ```

- File exists → parse with `json.load`:
  - Missing `json.schemas` key → add as `[]` before insertion.
  - `json.schemas` is not an array → refuse (schema violation),
    print the type mismatch, exit 2.
  - An entry whose `fileMatch` contains `.haex-hive.json`:
    - Same `url` → no action.
    - Different `url` → offer diff-preview update.
  - No matching entry → append the canonical entry.

- Serialize the merged content with `json.dumps(indent=2,
  ensure_ascii=False, sort_keys=False)` + trailing LF.

### Failure modes

| Symptom | Handler |
|---------|---------|
| File contains a JSON5-style comment | Refuse, print "cannot parse .vscode/settings.json: JSON5 comments not supported; strip comments and re-run". |
| File is invalid JSON | Refuse, print the exact `json.JSONDecodeError` location. |
| File is a directory | Refuse, print "expected file, found directory". |

## JetBrains Family (`.idea/jsonSchemas.xml`)

### Target file

- Path: `<project-root>/.idea/jsonSchemas.xml`
- Serialization: XML, UTF-8, `<?xml version="1.0" encoding="UTF-8"?>`
  declaration, 2-space indent, LF line endings.
- IDEs covered: IntelliJ IDEA, PyCharm, GoLand, WebStorm, PhpStorm,
  RubyMine, CLion, DataGrip, Rider, Android Studio.

### Canonical entry

```xml
<entry key="haex-hive">
  <value>
    <SchemaInfo>
      <option name="name" value="haex-hive" />
      <option name="relativePathToSchema" value=".specify/schemas/haex-hive.schema.json" />
      <option name="schemaVersion" value="JSON Schema version 7" />
      <option name="patterns">
        <list>
          <Item>
            <option name="path" value=".haex-hive.json" />
          </Item>
        </list>
      </option>
    </SchemaInfo>
  </value>
</entry>
```

### Merge rules (Decision 6)

- File missing → create with (full document):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <project version="4">
    <component name="JsonSchemaMappingsProjectConfiguration">
      <state>
        <map>
          <entry key="haex-hive">
            …canonical entry above…
          </entry>
        </map>
      </state>
    </component>
  </project>
  ```

- File exists → parse with `xml.etree.ElementTree`:
  - Match the root and every subordinate element by **local name**
    (i.e. the element's tag after any `{namespace}` prefix `ET` may
    have stamped). Concretely: `tag.rsplit("}", 1)[-1] == "project"`,
    same for `component`, `state`, `map`, `entry`. This is how
    IntelliJ-style tools that stamp a namespace on the root still
    match. Unrecognised namespaces produce a warning (per Failure
    modes below) but the parse proceeds.
  - No `project` local-name root → refuse, print "unexpected XML
    root element in .idea/jsonSchemas.xml".
  - `project` root but no `JsonSchemaMappingsProjectConfiguration`
    component → add the component.
  - Component exists but no `entry key="haex-hive"` under
    `state/map` → add the entry.
  - `entry key="haex-hive"` exists:
    - `relativePathToSchema` value matches canonical → no action.
    - `relativePathToSchema` value differs → offer diff-preview update.
- Re-serialize with `ET.tostring(root, encoding="utf-8",
  xml_declaration=True)`. If `ET.indent` is available (Python 3.9+),
  use it with 2-space indent. Preserve any `xmlns` attributes present
  on the input root so a namespaced document round-trips with its
  original namespace intact. A regression fixture covering a
  namespaced `<project xmlns="…">` root MUST accompany the
  local-name matching change.

### Gitignore warning (FR-013)

Before writing, run `git check-ignore .idea/` in the project's git
working directory. If it exits 0 (i.e. `.idea/` is ignored):

- Print: `warning: .idea/ is gitignored; .idea/jsonSchemas.xml will
  not travel with the project.`
- Offer proceed / skip: `Proceed anyway? [y/N]:` (default N).

### Failure modes

| Symptom | Handler |
|---------|---------|
| File is invalid XML | Refuse, print `ET.ParseError`'s line/column. |
| File uses XML namespaces we do not recognize | Warn but proceed. |
| File is a directory | Refuse, print "expected file, found directory". |

## Detection Signal Map

| Detected tool | Mapping-file write target |
|---------------|--------------------------|
| `vscode` | `.vscode/settings.json` |
| `vscode-insiders` | `.vscode/settings.json` (same file — VSCode-family shares workspace settings) |
| `cursor` | `.vscode/settings.json` |
| `windsurf` | `.vscode/settings.json` |
| `jetbrains` (family) | `.idea/jsonSchemas.xml` |

If multiple VSCode-family tools are selected, exactly one merge into
`.vscode/settings.json` happens (idempotency by shape). The final
action-report lists the tools that share the mapping.

## Not part of this contract

- Neovim, Emacs, Sublime Text, Zed, Helix: documented as manual in
  `docs/haex-init.md`; `haex-init` does NOT write for these in
  Phase 1 (spec Non-Goal).
- IDE-specific "open project on first run" or workspace files
  (`.code-workspace`, `.idea/workspace.xml`): not touched.
- Any editor's user-global settings (`~/.vscode/settings.json`,
  `~/Library/Application Support/JetBrains/…`): not touched. Only
  project-local `.vscode/` and `.idea/` are in scope.
