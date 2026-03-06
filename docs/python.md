---
layout: default
title: Python
nav_order: 4
---

# Python Package

`mif-tools` — Python library and CLI for MIF.

---

## Installation

```bash
pip install mif-tools

# With schema validation support
pip install mif-tools[validate]

# With MCP server support
pip install mif-tools[mcp]
```

## API Reference

### `load(data, *, format=None) -> MifDocument`

Parse a string into a MifDocument. Auto-detects format unless specified.

```python
from mif import load

doc = load(open("memories.json").read())
doc = load(data, format="mem0")
```

### `dump(doc, *, format="shodh") -> str`

Serialize a MifDocument to a string.

```python
from mif import dump

json_str = dump(doc)                    # MIF v2 JSON
md_str = dump(doc, format="markdown")   # YAML frontmatter markdown
```

### `convert(data, *, from_format=None, to_format="shodh") -> str`

Convert between formats in one call.

```python
from mif import convert

result = convert(data, from_format="mem0", to_format="markdown")
```

### `validate(data) -> tuple[bool, list[str]]`

Validate a MIF JSON string against the schema.

```python
from mif import validate

is_valid, errors = validate(json_string)
```

### `validate_deep(data) -> tuple[bool, list[str]]`

Semantic validation (UUID format, referential integrity, timestamp ordering, embedding dimensions).

```python
from mif import validate_deep

is_valid, warnings = validate_deep(json_string)
```

### `deduplicate(doc) -> tuple[MifDocument, int]`

Deduplicate memories by SHA-256 content hash.

```python
from mif import deduplicate

deduped_doc, removed_count = deduplicate(doc)
```

## Models

```python
from mif.models import Memory, MifDocument

memory = Memory(
    id="550e8400-e29b-41d4-a716-446655440000",
    content="User prefers dark mode",
    created_at="2026-01-15T10:30:00Z",
    memory_type="observation",
    tags=["preferences"],
)

doc = MifDocument(memories=[memory])
```

## CLI

```bash
# Convert between formats
mif convert export.json --from mem0 --to shodh -o output.mif.json

# Auto-detect source format
mif convert memories.json --to markdown

# Validate MIF documents
mif validate file1.json file2.json

# Inspect a memory file
mif inspect memories.json

# List available formats
mif formats

# Start MCP server (requires mif-tools[mcp])
mif mcp
```
