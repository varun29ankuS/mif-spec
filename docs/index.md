---
layout: default
title: Home
nav_order: 1
---

# Memory Interchange Format (MIF)

A vendor-neutral JSON schema for portable AI agent memories.
{: .fs-6 .fw-300 }

---

## The Problem

AI memory is becoming standard infrastructure — but every system stores it differently. Switching providers means losing months of accumulated context. Memory servers can't compose. There's no vCard for AI memories.

## The Solution

MIF defines a minimal, extensible JSON envelope for memories and optional knowledge graph data. Export from any system, import into any other.

```json
{
  "mif_version": "2.0",
  "memories": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "content": "User prefers dark mode across all applications",
      "memory_type": "observation",
      "created_at": "2026-01-15T10:30:00Z",
      "tags": ["preferences", "ui"]
    }
  ]
}
```

## Quick Start

### Python

```bash
pip install mif-tools
```

```python
from mif import load, dump, convert

# Auto-detect format and convert to MIF
doc = load(open("memories.json").read())

# Convert between formats
result = convert(data, from_format="mem0", to_format="shodh")
```

### npm

```bash
npm install @varunshodh/mif-tools
```

```typescript
import { load, dump, convert } from "@varunshodh/mif-tools";

const doc = load(fs.readFileSync("memories.json", "utf-8"));
const result = convert(data, { fromFormat: "mem0", toFormat: "shodh" });
```

### CLI

```bash
mif convert export.json --from mem0 --to shodh -o memories.mif.json
mif validate memories.mif.json
mif inspect memories.json
mif formats
```

## Supported Formats

| Format | ID | Description |
|---|---|---|
| MIF / Shodh | `shodh` | Native MIF v2 JSON (+ v1 backward compat) |
| mem0 | `mem0` | mem0 JSON array format |
| CrewAI | `crewai` | CrewAI LTMSQLiteStorage export |
| LangChain | `langchain` | LangChain/LangMem Item format |
| Generic JSON | `generic` | Any JSON array with `content` field |
| Markdown | `markdown` | YAML frontmatter + body |

## Links

- [Full Specification](spec) - MIF v2.0 spec
- [Adapter Reference](adapters) - All format adapters
- [Python Package](python) - Python guide
- [npm Package](npm) - npm/TypeScript guide
- [MCP Server](mcp) - Model Context Protocol server
- [GitHub Repository](https://github.com/varun29ankuS/mif-spec)
