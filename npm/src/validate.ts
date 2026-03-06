/** MIF v2 validation: schema-level and deep semantic checks. */

import * as fs from "fs";
import * as path from "path";

// ---------------------------------------------------------------------------
// UUID / ISO-8601 helpers
// ---------------------------------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUuid(s: unknown): boolean {
  return typeof s === "string" && UUID_RE.test(s);
}

const ISO8601_RE =
  /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

function parseIso8601(s: unknown): Date | null {
  if (typeof s !== "string") return null;
  if (!ISO8601_RE.test(s)) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

// ---------------------------------------------------------------------------
// Schema validation (structural)
// ---------------------------------------------------------------------------

/**
 * Validate a MIF JSON string against the bundled JSON Schema.
 *
 * This performs basic structural checks without requiring an external
 * JSON Schema library.  It validates required fields, types, and key
 * constraints from the MIF v2 schema.
 *
 * @returns `[true, []]` when valid, `[false, errors]` otherwise.
 */
export function validate(data: string): [boolean, string[]] {
  let document: any;
  try {
    document = JSON.parse(data);
  } catch (e: any) {
    return [false, [`Invalid JSON: ${e.message}`]];
  }

  if (typeof document !== "object" || document === null || Array.isArray(document)) {
    return [false, ["Document root must be a JSON object."]];
  }

  const errors: string[] = [];

  // mif_version
  if (!document.mif_version) {
    errors.push("Missing required field: 'mif_version'.");
  } else if (typeof document.mif_version !== "string") {
    errors.push("'mif_version' must be a string.");
  } else if (!/^2\./.test(document.mif_version)) {
    errors.push(`'mif_version' must start with '2.' (got '${document.mif_version}').`);
  }

  // memories
  if (!("memories" in document)) {
    errors.push("Missing required field: 'memories'.");
  } else if (!Array.isArray(document.memories)) {
    errors.push("'memories' must be an array.");
  } else {
    for (let i = 0; i < document.memories.length; i++) {
      const mem = document.memories[i];
      if (typeof mem !== "object" || mem === null || Array.isArray(mem)) {
        errors.push(`memories[${i}]: must be a JSON object.`);
        continue;
      }
      if (!mem.id) errors.push(`memories[${i}]: missing required field 'id'.`);
      if (!mem.content && mem.content !== "") errors.push(`memories[${i}]: missing required field 'content'.`);
      if (!mem.created_at) errors.push(`memories[${i}]: missing required field 'created_at'.`);
    }
  }

  // generator
  if (document.generator !== undefined && document.generator !== null) {
    if (typeof document.generator !== "object" || Array.isArray(document.generator)) {
      errors.push("'generator' must be an object.");
    } else {
      if (!document.generator.name) errors.push("generator: missing required field 'name'.");
      if (!document.generator.version) errors.push("generator: missing required field 'version'.");
    }
  }

  return errors.length === 0 ? [true, []] : [false, errors];
}

// ---------------------------------------------------------------------------
// Deep semantic validation (9 checks, mirrors Python validate_deep)
// ---------------------------------------------------------------------------

/**
 * Perform deep semantic validation of a MIF JSON document.
 *
 * Checks:
 *  1. All memory `id` values are valid UUIDs.
 *  2. All memory `id` values are unique.
 *  3. Every `related_memory_ids` entry references an existing memory.
 *  4. Every `parent_id` references an existing memory.
 *  5. Every `created_at` is valid ISO 8601.
 *  6. `updated_at` is chronologically after `created_at`.
 *  7. Knowledge-graph entity IDs are unique.
 *  8. Graph relationship source/target reference existing entities.
 *  9. Embedding vector length matches dimensions.
 *
 * @returns `[true, []]` when all checks pass, `[false, warnings]` otherwise.
 */
export function validateDeep(data: string): [boolean, string[]] {
  let document: any;
  try {
    document = JSON.parse(data);
  } catch (e: any) {
    return [false, [`Invalid JSON: ${e.message}`]];
  }

  if (typeof document !== "object" || document === null || Array.isArray(document)) {
    return [false, ["Document root must be a JSON object."]];
  }

  const warnings: string[] = [];
  const memories: any[] = document.memories;
  if (!Array.isArray(memories)) {
    return [false, ["'memories' field must be a JSON array."]];
  }

  // Build set of known memory IDs
  const seenMemoryIds = new Map<string, number>();

  for (let idx = 0; idx < memories.length; idx++) {
    const mem = memories[idx];
    if (typeof mem !== "object" || mem === null || Array.isArray(mem)) {
      warnings.push(`memories[${idx}]: entry is not a JSON object, skipping.`);
      continue;
    }

    const memId = mem.id;

    // Check 1 — valid UUID
    if (memId === undefined || memId === null) {
      warnings.push(`memories[${idx}]: missing 'id' field.`);
    } else if (!isValidUuid(memId)) {
      warnings.push(`memories[${idx}]: 'id' value '${memId}' is not a valid UUID.`);
    } else {
      // Check 2 — unique
      if (seenMemoryIds.has(memId)) {
        warnings.push(
          `memories[${idx}]: duplicate 'id' '${memId}' (first seen at index ${seenMemoryIds.get(memId)}).`
        );
      } else {
        seenMemoryIds.set(memId, idx);
      }
    }
  }

  const knownIds = new Set(seenMemoryIds.keys());

  // Per-memory semantic checks
  for (let idx = 0; idx < memories.length; idx++) {
    const mem = memories[idx];
    if (typeof mem !== "object" || mem === null || Array.isArray(mem)) continue;

    const memLabel = `memories[${idx}] (id='${mem.id ?? "<missing>"}')`;

    // Check 3 — related_memory_ids referential integrity
    const related = mem.related_memory_ids;
    if (Array.isArray(related)) {
      for (const ref of related) {
        if (typeof ref !== "string") {
          warnings.push(`${memLabel}: related_memory_ids entry '${ref}' is not a string.`);
        } else if (!knownIds.has(ref)) {
          warnings.push(`${memLabel}: related_memory_ids references unknown memory id '${ref}'.`);
        }
      }
    }

    // Check 4 — parent_id referential integrity
    const parentId = mem.parent_id;
    if (parentId !== undefined && parentId !== null) {
      if (typeof parentId !== "string") {
        warnings.push(`${memLabel}: 'parent_id' must be a string, got ${typeof parentId}.`);
      } else if (!knownIds.has(parentId)) {
        warnings.push(`${memLabel}: 'parent_id' references unknown memory id '${parentId}'.`);
      }
    }

    // Check 5 — created_at is valid ISO 8601
    const createdRaw = mem.created_at;
    let createdDt: Date | null = null;
    if (createdRaw !== undefined && createdRaw !== null) {
      createdDt = parseIso8601(createdRaw);
      if (createdDt === null) {
        warnings.push(
          `${memLabel}: 'created_at' value '${createdRaw}' is not valid ISO 8601 (expected format: YYYY-MM-DDTHH:MM:SSZ).`
        );
      }
    }

    // Check 6 — updated_at > created_at
    const updatedRaw = mem.updated_at;
    if (updatedRaw !== undefined && updatedRaw !== null) {
      const updatedDt = parseIso8601(updatedRaw);
      if (updatedDt === null) {
        warnings.push(`${memLabel}: 'updated_at' value '${updatedRaw}' is not valid ISO 8601.`);
      } else if (createdDt !== null && updatedDt < createdDt) {
        warnings.push(
          `${memLabel}: 'updated_at' (${updatedRaw}) is before 'created_at' (${createdRaw}).`
        );
      }
    }

    // Check 9 — embedding vector length matches dimensions
    const embeddings = mem.embeddings;
    if (embeddings && typeof embeddings === "object" && !Array.isArray(embeddings)) {
      const dims = embeddings.dimensions;
      const vector = embeddings.vector;
      if (dims !== undefined && vector !== undefined) {
        if (Array.isArray(vector) && typeof dims === "number") {
          if (vector.length !== dims) {
            warnings.push(
              `${memLabel}: embedding 'vector' has ${vector.length} elements but 'dimensions' is ${dims}.`
            );
          }
        }
      }
    }
  }

  // Knowledge graph checks (7 and 8)
  const kg = document.knowledge_graph;
  if (kg && typeof kg === "object" && !Array.isArray(kg)) {
    const entities: any[] = kg.entities || [];
    const relationships: any[] = kg.relationships || [];

    // Check 7 — entity IDs are unique
    const seenEntityIds = new Map<string, number>();
    for (let eidx = 0; eidx < entities.length; eidx++) {
      const entity = entities[eidx];
      if (typeof entity !== "object" || entity === null || Array.isArray(entity)) {
        warnings.push(`knowledge_graph.entities[${eidx}]: entry is not a JSON object.`);
        continue;
      }
      const eid = entity.id;
      if (eid === undefined || eid === null) {
        warnings.push(`knowledge_graph.entities[${eidx}]: missing 'id' field.`);
      } else if (typeof eid !== "string") {
        warnings.push(`knowledge_graph.entities[${eidx}]: 'id' must be a string, got ${typeof eid}.`);
      } else if (seenEntityIds.has(eid)) {
        warnings.push(
          `knowledge_graph.entities[${eidx}]: duplicate entity id '${eid}' (first seen at index ${seenEntityIds.get(eid)}).`
        );
      } else {
        seenEntityIds.set(eid, eidx);
      }
    }

    const knownEntityIds = new Set(seenEntityIds.keys());

    // Check 8 — relationship source/target reference existing entities
    for (let ridx = 0; ridx < relationships.length; ridx++) {
      const rel = relationships[ridx];
      if (typeof rel !== "object" || rel === null || Array.isArray(rel)) {
        warnings.push(`knowledge_graph.relationships[${ridx}]: entry is not a JSON object.`);
        continue;
      }
      const relLabel = `knowledge_graph.relationships[${ridx}] (id='${rel.id ?? "<missing>"}')`;

      const src = rel.source_entity_id;
      const tgt = rel.target_entity_id;

      if (src === undefined || src === null) {
        warnings.push(`${relLabel}: missing 'source_entity_id'.`);
      } else if (typeof src !== "string") {
        warnings.push(`${relLabel}: 'source_entity_id' must be a string.`);
      } else if (!knownEntityIds.has(src)) {
        warnings.push(
          `${relLabel}: 'source_entity_id' '${src}' references an entity that does not exist in knowledge_graph.entities.`
        );
      }

      if (tgt === undefined || tgt === null) {
        warnings.push(`${relLabel}: missing 'target_entity_id'.`);
      } else if (typeof tgt !== "string") {
        warnings.push(`${relLabel}: 'target_entity_id' must be a string.`);
      } else if (!knownEntityIds.has(tgt)) {
        warnings.push(
          `${relLabel}: 'target_entity_id' '${tgt}' references an entity that does not exist in knowledge_graph.entities.`
        );
      }
    }
  }

  return warnings.length === 0 ? [true, []] : [false, warnings];
}
