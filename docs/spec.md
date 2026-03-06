---
layout: default
title: Specification
nav_order: 2
---

# MIF v2.0 Specification

- **Version**: 2.0
- **Status**: Draft
- **Created**: 2026-03-03
- **Author(s)**: Varun Sharma (@varun29ankuS)

**Note:** v2.0 is the first public release. The "v2" numbering reflects internal iterations during development.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Abstract

MIF is a vendor-neutral JSON schema for exchanging AI agent memories between systems. It defines a minimal, extensible envelope for memories and optional knowledge graph data, enabling portability across providers.

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
    "privacy": { "pii_detected": false, "redacted_fields": [] }
  },
  "memories": [],
  "knowledge_graph": null,
  "vendor_extensions": {}
}
```

**Required fields:** `mif_version`, `memories`

A minimal conforming document:

```json
{"mif_version": "2.0", "memories": []}
```

## 2. Memory Object

Each entry in the `memories` array:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string (UUID v4) | Yes | Unique identifier |
| `content` | string | Yes | Memory content text |
| `created_at` | string (ISO 8601) | Yes | Creation timestamp |
| `memory_type` | string | No | Type classification |
| `updated_at` | string (ISO 8601) | No | Last modification time |
| `tags` | string[] | No | Classification tags |
| `entities` | EntityReference[] | No | Referenced entities |
| `metadata` | object | No | Arbitrary metadata |
| `embeddings` | Embedding | No | Vector embedding |
| `source` | Source | No | Origin information |
| `parent_id` | string (UUID) \| null | No | Parent memory reference |
| `related_memory_ids` | string[] (UUIDs) | No | Related memories |
| `agent_id` | string \| null | No | Agent identifier |
| `external_id` | string \| null | No | External system ID |
| `version` | integer (>= 1) | No | Version number |

### 2.1 Memory Types

Lowercase snake_case strings. Common types:

| Type | Description |
|---|---|
| `observation` | Factual observation about user or environment |
| `decision` | A decision made by or for the user |
| `learning` | Something learned during interaction |
| `error` | An error and its context |
| `context` | Session or project context |
| `conversation` | Conversation excerpt or summary |

This list is **non-exhaustive**. Implementations MUST accept unknown types without error and MUST preserve them on round-trip.

### 2.2 Entity References

```json
{ "name": "RocksDB", "entity_type": "technology", "confidence": 0.95 }
```

Common entity types: `person`, `organization`, `location`, `technology`, `concept`, `event`, `product`, `unknown`.

### 2.3 Embeddings

Optional. When present:
- Importers using the **same model** MAY reuse the vector directly
- Importers using a **different model** SHOULD discard and regenerate from `content`
- `dimensions` must equal `len(vector)`

## 3. Knowledge Graph (Optional)

```json
{
  "entities": [
    {
      "id": "...",
      "name": "Rust",
      "types": ["technology"],
      "attributes": { "category": "programming_language" },
      "summary": "Systems programming language"
    }
  ],
  "relationships": [
    {
      "id": "...",
      "source_entity_id": "...",
      "target_entity_id": "...",
      "relation_type": "works_with",
      "confidence": 0.9
    }
  ]
}
```

## 4. Vendor Extensions

System-specific metadata lives in `vendor_extensions`, keyed by system name:

```json
"vendor_extensions": {
  "shodh-memory": { "memory_metadata": { "<uuid>": { "importance": 0.85 } } },
  "mem0": { "organization_id": "org-123" }
}
```

Implementations MUST preserve vendor extensions from other systems on round-trip.

## 5. Privacy

The `export_meta.privacy` field communicates PII handling:

```json
{ "pii_detected": true, "redacted_fields": ["email", "phone"] }
```

## 6. Import Behavior

- **UUID preservation:** Imported memories SHOULD retain original IDs
- **Deduplication:** By content hash (SHA-256 of `content`), not UUID collision
- **Partial failure:** Individual failures MUST NOT abort the batch
- **Unknown fields:** Importers MUST ignore unknown fields (forward compatibility)

## 7. MCP Tool Conventions

Memory servers implementing MIF SHOULD expose:

| Tool | Purpose |
|---|---|
| `export_memories` | Export user memories as MIF JSON |
| `import_memories` | Import MIF JSON into the memory system |

## 8. Versioning

- **Minor versions (2.x)** are additive only — new optional fields, no breaking changes
- A v2.0 consumer SHOULD accept any v2.x document
- **Major versions (3.0+)** MAY introduce breaking changes

## 9. JSON Schema

A formal JSON Schema for validation: [`mif-v2.schema.json`](https://github.com/varun29ankuS/mif-spec/blob/main/schema/mif-v2.schema.json)
