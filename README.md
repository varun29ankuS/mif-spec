# Memory Interchange Format (MIF)

**Your AI agent has 6 months of memories in System A. You want to try System B. Without MIF, you lose everything. With MIF:**

```bash
pip install mif-tools
mif convert mem0_export.json --to shodh -o memories.mif.json
```

Done. Your memories are portable.

## What is MIF?

A vendor-neutral JSON envelope for AI agent memories. Like vCard for contacts or iCalendar for events — a minimal schema so memories move between providers without data loss.

**3 required fields.** That's it.

```json
{
  "mif_version": "2.0",
  "memories": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "content": "User prefers dark mode across all applications",
      "created_at": "2026-01-15T10:30:00Z"
    }
  ]
}
```

Everything else — memory types, tags, entities, embeddings, knowledge graph, vendor extensions — is optional. Add what you have, ignore what you don't.

## Install

```bash
# Python
pip install mif-tools              # core (zero dependencies)
pip install mif-tools[validate]    # with JSON Schema validation

# Node.js / TypeScript
npm install @varunshodh/mif-tools
```

## Convert Between Formats

```bash
# mem0 → MIF
mif convert mem0_export.json --from mem0 -o memories.mif.json

# MIF → Markdown (Obsidian/Letta style)
mif convert memories.mif.json --to markdown -o memories.md

# Auto-detect source format
mif convert any_memory_file.json -o output.mif.json

# Inspect any memory file
mif inspect memories.json

# Validate MIF document
mif validate memories.mif.json
```

## Python API

```python
from mif import load, dump, convert, MifDocument, Memory

# Load from any format (auto-detects mem0, markdown, generic JSON, MIF)
doc = load(open("mem0_export.json").read())
print(f"{len(doc.memories)} memories loaded")

# Convert between formats in one line
markdown = convert(data, from_format="mem0", to_format="markdown")

# Create memories from scratch
doc = MifDocument(memories=[
    Memory(
        id="123e4567-e89b-12d3-a456-426614174000",
        content="User prefers dark mode",
        created_at="2026-01-15T10:30:00Z",
        memory_type="observation",
        tags=["preferences", "ui"],
    )
])
print(dump(doc))  # MIF v2 JSON

# Deep validation (UUIDs, references, timestamps, embedding dimensions)
from mif import validate_deep
ok, warnings = validate_deep(open("export.mif.json").read())
```

## Add MIF to Your MCP Server (10 lines)

```python
from mif import load, dump

# Export handler
def export_memories(user_id: str) -> str:
    memories = my_storage.get_all(user_id)
    return dump(memories)

# Import handler — auto-detects mem0, markdown, generic JSON, MIF
def import_memories(data: str) -> dict:
    doc = load(data)
    for mem in doc.memories:
        my_storage.save(mem.id, mem.content, mem.created_at)
    return {"memories_imported": len(doc.memories)}
```

## Supported Formats

| Format | ID | Auto-detect | Description |
|--------|----|-------------|-------------|
| **MIF v2** | `shodh` | `"mif_version"` in JSON | Native format, lossless round-trip |
| **mem0** | `mem0` | JSON array with `"memory"` field | mem0 memory exports |
| **Generic JSON** | `generic` | JSON array with `"content"` field | Any JSON memory array |
| **Markdown** | `markdown` | Starts with `---` | YAML frontmatter (Letta/Obsidian style) |

## Full Spec

MIF supports optional fields for rich memory data:

- **Memory types** — `observation`, `decision`, `learning`, `error`, `context`, `conversation`, and custom types
- **Entity references** — named entities with type and confidence
- **Embeddings** — model name, dimensions, vector (reuse or regenerate)
- **Knowledge graph** — entities and relationships with confidence scores
- **Vendor extensions** — system-specific metadata preserved on round-trip
- **Privacy** — PII detection and redaction markers

Full specification: [`spec/mif-v2.md`](./spec/mif-v2.md) | JSON Schema: [`schema/mif-v2.schema.json`](./schema/mif-v2.schema.json)

## Adapters & Implementations

| System | Status | Type |
|--------|--------|------|
| [shodh-memory](https://github.com/varun29ankuS/shodh-memory) | Production | Built-in HTTP API (`/api/export/mif`, `/api/import/mif`) |
| [mif-tools](https://pypi.org/project/mif-tools/) | Production | Python package with CLI |
| mem0 | Adapter ready | Python + [Rust](https://github.com/varun29ankuS/shodh-memory/blob/main/src/mif/adapters/mem0.rs) |
| Markdown (YAML frontmatter) | Adapter ready | Python + [Rust](https://github.com/varun29ankuS/shodh-memory/blob/main/src/mif/adapters/markdown.rs) |
| Generic JSON | Adapter ready | Python + [Rust](https://github.com/varun29ankuS/shodh-memory/blob/main/src/mif/adapters/generic.rs) |
| CrewAI | Planned | — |
| LangChain | Planned | — |

## Design Principles

1. **Minimal** — 3 required fields. Everything else is optional.
2. **Extensible** — Unknown fields and vendor extensions MUST be preserved on round-trip.
3. **Vendor-neutral** — The schema doesn't favor any implementation.
4. **Forward-compatible** — Importers MUST ignore unknown fields.

## Contributing

We welcome adapter implementations for any memory system. See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Related

- [MCP SEP #2342](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2342) — Original proposal to the Model Context Protocol
- [tower-mcp #531](https://github.com/joshrotenberg/tower-mcp/issues/531) — Tracking issue in tower-mcp
- [shodh-memory](https://github.com/varun29ankuS/shodh-memory) — Reference implementation (Rust)
- [mif-tools on PyPI](https://pypi.org/project/mif-tools/) — Python package

## License

Apache 2.0
