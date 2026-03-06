---
layout: default
title: Adapters
nav_order: 3
---

# Format Adapters

MIF tools include adapters for converting between popular AI memory formats and MIF v2.

---

## Shodh / MIF Native (`shodh`)

The native MIF v2 format. Also handles backward-compatible import of MIF v1 documents.

**Detection:** JSON object with `"mif_version"` or `"shodh-memory"` key.

```json
{
  "mif_version": "2.0",
  "memories": [
    { "id": "...", "content": "...", "created_at": "..." }
  ]
}
```

---

## mem0 (`mem0`)

Converts [mem0](https://mem0.ai) JSON array exports.

**Detection:** JSON array where items have a `"memory"` field.

```json
[
  {
    "id": "...",
    "memory": "User prefers TypeScript",
    "user_id": "user-42",
    "created_at": "2025-06-15T12:00:00Z",
    "metadata": { "category": "preference" }
  }
]
```

**Field mapping:**

| mem0 | MIF |
|---|---|
| `memory` | `content` |
| `id` | `external_id` + `id` (preserved if valid UUID) |
| `metadata.category` | `memory_type` (via mapping table) |
| `metadata.tags` | `tags` (comma-separated string or array) |
| `user_id` | `export_meta.user_id` |

---

## CrewAI (`crewai`)

Converts [CrewAI](https://crewai.com) long-term memory exports from LTMSQLiteStorage.

**Detection:** JSON array where items have a `"task_description"` field.

```json
[
  {
    "task_description": "User prefers dark mode for all IDEs",
    "metadata": "{\"category\": \"preference\"}",
    "datetime": "1718452800.0",
    "score": 0.95
  }
]
```

**Field mapping:**

| CrewAI | MIF |
|---|---|
| `task_description` | `content` |
| `metadata` (JSON string) | `metadata` (parsed to object) |
| `datetime` (Unix timestamp) | `created_at` (ISO 8601) |
| `score` | `metadata.score` |

---

## LangChain / LangMem (`langchain`)

Converts [LangChain](https://langchain.com) and [LangMem](https://langchain-ai.github.io/langmem/) Item objects.

**Detection:** JSON array where items have `"namespace"` and `"value"` fields.

```json
[
  {
    "namespace": ["memories", "user-prefs"],
    "key": "pref-dark-mode",
    "value": { "kind": "Memory", "content": "User prefers dark mode" },
    "created_at": "2025-06-15T12:00:00Z",
    "score": 0.9
  }
]
```

**Field mapping:**

| LangChain | MIF |
|---|---|
| `value.content` | `content` |
| `value.kind` | `memory_type` (lowercased, mapped) |
| `namespace` | `tags` (flattened) |
| `key` | `external_id` |
| `created_at` | `created_at` |
| `updated_at` | `updated_at` |
| `score` | `metadata.score` |

---

## Generic JSON (`generic`)

Fallback adapter for any JSON array with a `content` field.

**Detection:** JSON array where items have a `"content"` field.

```json
[
  {
    "content": "Remember to check logs daily",
    "type": "task",
    "timestamp": "2025-06-15T12:00:00Z",
    "tags": ["ops"]
  }
]
```

Accepts `timestamp`, `created_at`, or `date` for the creation time. Accepts `type` or `memory_type` for the memory type.

---

## Markdown (`markdown`)

YAML frontmatter + body format. Each memory is a `---` delimited block.

**Detection:** Input starts with `---`.

```markdown
---
type: observation
created_at: 2025-06-15T12:00:00Z
tags: [python, testing]
---
User prefers pytest over unittest.
```

---

## Writing Custom Adapters

### Python

```python
from mif.adapters import MifAdapter
from mif.models import MifDocument

class MyAdapter(MifAdapter):
    def name(self) -> str:
        return "My Format"

    def format_id(self) -> str:
        return "myformat"

    def detect(self, data: str) -> bool:
        return '"my_marker"' in data

    def to_mif(self, data: str) -> MifDocument:
        # Parse data and return MifDocument
        ...

    def from_mif(self, doc: MifDocument) -> str:
        # Serialize MifDocument to your format
        ...
```

### TypeScript

```typescript
import { MifAdapter, MifDocument } from "@varunshodh/mif-tools";

class MyAdapter implements MifAdapter {
  name() { return "My Format"; }
  formatId() { return "myformat"; }
  detect(data: string) { return data.includes('"my_marker"'); }
  toMif(data: string): MifDocument { /* ... */ }
  fromMif(doc: MifDocument): string { /* ... */ }
}
```

Register your adapter:

```python
from mif.registry import AdapterRegistry
registry = AdapterRegistry()
registry.adapters.insert(0, MyAdapter())  # highest priority
```

```typescript
import { AdapterRegistry } from "@varunshodh/mif-tools";
const registry = new AdapterRegistry();
registry.register(new MyAdapter()); // prepended for highest priority
```
