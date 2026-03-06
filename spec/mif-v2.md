# Memory Interchange Format (MIF) v2.0

- **Version**: 2.0
- **Status**: Draft
- **Created**: 2026-03-03
- **Author(s)**: Varun Sharma (@varun29ankuS)

**Note:** v2.0 is the first public release. The "v2" numbering reflects internal iterations during development. There is no public v1 specification.

## Abstract

MIF is a vendor-neutral JSON schema for exchanging AI agent memories between systems. It defines a minimal, extensible envelope for memories and optional knowledge graph data, enabling portability across providers.

## Motivation

Memory is becoming standard infrastructure for AI agents. Multiple implementations exist — some store memories as plain text with timestamps, others as JSON objects with metadata, others as markdown with YAML frontmatter. Each captures useful information, but none can interoperate.

This creates practical problems:

- Teams evaluating memory providers cannot trial System B without abandoning context built in System A
- Users switching AI clients lose months of accumulated context
- Memory servers cannot compose — a retrieval-focused server cannot import from a storage-focused server

Other domains solved this with interchange formats: vCard for contacts, iCalendar for events, OPML for feeds. MIF applies the same approach to AI agent memories.

## 1. Document Structure

A MIF document is a JSON object:

```json
{
  "mif_version": "2.0",
  "generator": { "name": "example-memory", "version": "1.0.0" },
  "export_meta": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-03-03T10:00:00Z",
    "user_id": "user-1",
    "checksum": "sha256:abc123...",
    "privacy": {
      "pii_detected": false,
      "redacted_fields": []
    }
  },
  "memories": [],
  "knowledge_graph": null,
  "vendor_extensions": {}
}
```

**Required fields:** `mif_version`, `memories`

**Optional fields:** Everything else.

A minimal conforming document:

```json
{"mif_version": "2.0", "memories": []}
```

## 2. Memory Object

Each entry in the `memories` array:

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "content": "User prefers dark mode across all applications",
  "memory_type": "decision",
  "created_at": "2026-01-15T10:30:00Z",
  "tags": ["preferences", "ui"],
  "entities": [
    { "name": "dark mode", "entity_type": "concept", "confidence": 1.0 }
  ],
  "metadata": {},
  "embeddings": {
    "model": "minilm-l6-v2",
    "dimensions": 384,
    "vector": [0.012, -0.034],
    "normalized": true
  },
  "source": {
    "source_type": "user",
    "session_id": "session-42",
    "agent_name": "claude-code"
  },
  "parent_id": null,
  "related_memory_ids": [],
  "agent_id": null,
  "external_id": null,
  "version": 1
}
```

**Required:** `id` (UUID v4), `content` (string), `created_at` (ISO 8601)

**Optional:** Everything else.

### 2.1 Memory Types

Lowercase snake_case strings. Common types seen across implementations:

| Type           | Description                                   |
| -------------- | --------------------------------------------- |
| `observation`  | Factual observation about user or environment |
| `decision`     | A decision made by or for the user            |
| `learning`     | Something learned during interaction          |
| `error`        | An error and its context                      |
| `context`      | Session or project context                    |
| `conversation` | Conversation excerpt or summary               |

This list is **non-exhaustive**. Implementations will define their own types (e.g., `task`, `discovery`, `pattern`, `code_edit`). Implementations MUST accept unknown types without error and MUST preserve them on round-trip.

### 2.2 Entity References

```json
{ "name": "RocksDB", "entity_type": "technology", "confidence": 0.95 }
```

Common entity types: `person`, `organization`, `location`, `technology`, `concept`, `event`, `product`, `unknown`.

This list is **non-exhaustive**. Implementations MUST accept unknown entity types and MUST preserve them on round-trip.

### 2.3 Embeddings

Optional. When present, `model` identifies the embedding model used.

- Importers using the **same model** MAY reuse the vector directly.
- Importers using a **different model** SHOULD discard the vector and regenerate from `content`.
- Importers **without embedding capability** SHOULD ignore this field entirely.
- The `dimensions` field declares the model's output dimensionality. In examples, vectors are truncated for readability. Production vectors MUST have exactly `dimensions` elements.

## 3. Knowledge Graph (Optional)

For systems that maintain entity relationships:

```json
{
  "entities": [
    {
      "id": "...",
      "name": "Rust",
      "types": ["technology"],
      "attributes": { "category": "programming_language" },
      "summary": "Systems programming language",
      "created_at": "2026-01-01T00:00:00Z",
      "last_seen_at": "2026-03-01T00:00:00Z"
    }
  ],
  "relationships": [
    {
      "id": "...",
      "source_entity_id": "...",
      "target_entity_id": "...",
      "relation_type": "works_with",
      "context": "User builds projects in Rust",
      "confidence": 0.9,
      "created_at": "2026-01-15T00:00:00Z",
      "invalidated_at": null
    }
  ]
}
```

Systems without graph support SHOULD omit this field entirely (not set to null). Systems that encounter unknown fields MUST preserve them on round-trip. Implementations MAY add additional arrays (e.g., `episodes`) — consumers MUST ignore fields they do not understand.

## 4. Vendor Extensions

System-specific metadata lives in `vendor_extensions`, keyed by system name:

```json
"vendor_extensions": {
  "shodh-memory": {
    "memory_metadata": {
      "<uuid>": { "importance": 0.85, "access_count": 12, "activation": 0.73 }
    }
  },
  "mem0": {
    "organization_id": "org-123"
  }
}
```

Implementations MUST preserve vendor extensions from other systems on round-trip, even if unrecognized. This enables lossless export -> import -> re-export without losing system-specific data.

## 5. Privacy

The `export_meta.privacy` field communicates PII handling:

```json
{ "pii_detected": true, "redacted_fields": ["email", "phone"] }
```

When PII redaction is requested, implementations SHOULD replace detected PII with `[REDACTED:type]` markers and record types in `redacted_fields`.

Common categories: `email`, `phone`, `ssn`, `api_key`, `credit_card`. Implementations MAY define additional categories.

## 6. Import Behavior

- **UUID preservation:** Imported memories SHOULD retain original IDs when possible.
- **Deduplication:** Implementations SHOULD deduplicate by content hash (SHA-256 of `content`), not UUID collision.
- **Partial failure:** Individual memory import failures MUST NOT abort the batch. Errors SHOULD be collected and returned.
- **Unknown fields:** Importers MUST ignore unknown top-level or nested fields (forward compatibility).

Import result:

```json
{
  "memories_imported": 150,
  "entities_imported": 45,
  "edges_imported": 78,
  "duplicates_skipped": 3,
  "errors": []
}
```

## 7. MCP Tool Conventions

Memory servers implementing MIF SHOULD expose:

| Tool              | Purpose                                |
| ----------------- | -------------------------------------- |
| `export_memories` | Export user memories as MIF JSON       |
| `import_memories` | Import MIF JSON into the memory system |

These are conventions, not protocol requirements.

## 8. JSON Schema

A formal JSON Schema for validation is provided as a companion file: [`mif-v2.schema.json`](../schema/mif-v2.schema.json).

Implementations SHOULD validate incoming MIF documents against this schema before import.

## Security Considerations

- Export/import endpoints MUST require authentication.
- Exports MUST be scoped to the authenticated user — no cross-user access.
- PII redaction SHOULD be surfaced prominently in UIs.
- MIF documents SHOULD NOT be transmitted over unencrypted connections.
- Vendor extensions from untrusted sources SHOULD be treated as untrusted input.

## Rationale

**Why memories + graph only?** Keeping the initial scope minimal maximizes adoption. Task management, reminders, and projects are separate concerns.

**Why JSON?** Universally supported, human-readable, native to MCP communication.

**Why UUIDs?** Enables lossless round-trip. Export from A -> import to B -> export from B preserves IDs, preventing duplicate accumulation.

**Why vendor extensions?** Different memory systems track different metadata. Extensions preserve this without requiring all implementers to understand every system's internals.

**Why content-hash dedup?** UUIDs may collide when importing from systems that generate new IDs on export. Content hash catches true semantic duplicates regardless of ID scheme.

## Extensibility

MIF is designed to be vendor-agnostic. The schema uses `additionalProperties: true` at every level. This means:

- Implementations MAY add fields at any level (top-level, memory, graph entity, relationship, source)
- Consumers MUST ignore fields they do not understand
- Consumers MUST preserve unknown fields on round-trip when possible
- System-specific metadata SHOULD go in `vendor_extensions`, but additional top-level or nested fields are valid

The type lists (memory types, entity types, PII categories) are non-exhaustive examples. Each memory system will have its own vocabulary. MIF does not mandate a closed set — it provides common labels for interoperability where they overlap.

## Backward Compatibility

Purely additive. No changes to existing protocols or systems. Providers can adopt MIF alongside existing APIs.

## Reference Implementation

A reference implementation exists in [shodh-memory](https://github.com/varun29ankuS/shodh-memory) (~3,000 lines across schema, export, import, format adapters, and HTTP handlers). Format adapters exist for mem0 JSON arrays, YAML-frontmatter markdown, and generic JSON. Deployed in production since February 2026.
