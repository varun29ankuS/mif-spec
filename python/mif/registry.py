"""Adapter registry and top-level API."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mif.adapters import (
    MifAdapter,
    ShodhAdapter,
    Mem0Adapter,
    CrewAIAdapter,
    LangChainAdapter,
    GenericJsonAdapter,
    MarkdownAdapter,
)
from mif.models import MifDocument


class AdapterRegistry:
    """Registry of format adapters with auto-detection.

    Detection order (most specific first):
    1. Shodh (MIF v2/v1) — has mif_version or shodh-memory marker
    2. mem0 — JSON array with "memory" field
    3. Generic JSON — JSON array with "content" field
    4. Markdown — starts with "---"
    """

    def __init__(self) -> None:
        self.adapters: list[MifAdapter] = [
            ShodhAdapter(),
            Mem0Adapter(),
            CrewAIAdapter(),
            LangChainAdapter(),
            GenericJsonAdapter(),
            MarkdownAdapter(),
        ]

    def auto_detect(self, data: str) -> MifAdapter | None:
        """Find the first adapter that detects the format."""
        for adapter in self.adapters:
            if adapter.detect(data):
                return adapter
        return None

    def get(self, format_id: str) -> MifAdapter | None:
        """Get adapter by format ID."""
        for adapter in self.adapters:
            if adapter.format_id() == format_id:
                return adapter
        return None

    def list_formats(self) -> list[dict[str, str]]:
        """List all available adapters."""
        return [{"name": a.name(), "format_id": a.format_id()} for a in self.adapters]


# Module-level registry
_registry = AdapterRegistry()


def load(data: str, *, format: str | None = None) -> MifDocument:
    """Load a MIF document from a string.

    Auto-detects format unless `format` is specified.

    Args:
        data: Input string (JSON, markdown, etc.)
        format: Optional format ID ("shodh", "mem0", "generic", "markdown")

    Returns:
        MifDocument with parsed memories.

    Raises:
        ValueError: If format cannot be detected or is unknown.
    """
    if format:
        adapter = _registry.get(format)
        if not adapter:
            available = ", ".join(a.format_id() for a in _registry.adapters)
            raise ValueError(f"Unknown format: '{format}'. Available: {available}")
        return adapter.to_mif(data)

    adapter = _registry.auto_detect(data)
    if not adapter:
        raise ValueError(
            "Could not auto-detect format. "
            "Supported: shodh (MIF JSON), mem0, generic JSON array, markdown."
        )
    return adapter.to_mif(data)


def dump(doc: MifDocument, *, format: str = "shodh") -> str:
    """Serialize a MifDocument to a string.

    Args:
        doc: The MIF document to serialize.
        format: Output format ID (default: "shodh" for MIF v2 JSON).

    Returns:
        Serialized string in the requested format.
    """
    adapter = _registry.get(format)
    if not adapter:
        available = ", ".join(a.format_id() for a in _registry.adapters)
        raise ValueError(f"Unknown format: '{format}'. Available: {available}")
    return adapter.from_mif(doc)


def convert(data: str, *, from_format: str | None = None, to_format: str = "shodh") -> str:
    """Convert between formats in one call.

    Args:
        data: Input data string.
        from_format: Source format (auto-detected if None).
        to_format: Target format (default: MIF v2 JSON).

    Returns:
        Converted string in the target format.
    """
    doc = load(data, format=from_format)
    return dump(doc, format=to_format)


def validate(data: str) -> tuple[bool, list[str]]:
    """Validate a MIF JSON document against the schema.

    Args:
        data: JSON string to validate.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    # Try bundled schema first (works when pip-installed), then dev layout
    schema_path = Path(__file__).parent / "schema" / "mif-v2.schema.json"
    if not schema_path.exists():
        schema_path = Path(__file__).parent.parent.parent / "schema" / "mif-v2.schema.json"
    if not schema_path.exists():
        return False, ["Schema file not found. Install jsonschema and ensure schema is available."]

    try:
        import jsonschema
    except ImportError:
        return False, ["jsonschema not installed. Run: pip install jsonschema"]

    try:
        document = json.loads(data)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    with open(schema_path) as f:
        schema = json.load(f)

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(document))

    if not errors:
        return True, []

    messages = []
    for err in errors:
        path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
        messages.append(f"[{path}] {err.message}")
    return False, messages


# ---------------------------------------------------------------------------
# ISO 8601 pattern — accepts the subset used by MIF (RFC-3339 / UTC offset)
# Examples: 2024-01-15T10:30:00Z  2024-01-15T10:30:00.123456Z
#           2024-01-15T10:30:00+05:30
# ---------------------------------------------------------------------------
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"           # date
    r"[T ]"                          # separator
    r"\d{2}:\d{2}:\d{2}"            # time
    r"(\.\d+)?"                      # optional fractional seconds
    r"(Z|[+-]\d{2}:\d{2})$",        # UTC marker or offset
    re.ASCII,
)


def _is_valid_uuid(value: str) -> bool:
    """Return True if *value* is a canonical UUID (any version)."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _parse_iso8601(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp; return None if unparseable."""
    if not isinstance(value, str):
        return None
    if not _ISO8601_RE.match(value):
        return None
    # Normalise 'Z' → '+00:00' for fromisoformat (Python < 3.11 compat)
    normalised = value.rstrip("Z")
    if normalised != value:
        normalised += "+00:00"
    # Replace space separator with T
    normalised = normalised.replace(" ", "T")
    try:
        return datetime.fromisoformat(normalised)
    except ValueError:
        return None


def validate_deep(data: str) -> tuple[bool, list[str]]:
    """Perform deep semantic validation of a MIF JSON document.

    Checks performed (in addition to structural JSON parsing):

    1. All memory ``id`` values are valid UUIDs.
    2. All memory ``id`` values are unique within the document.
    3. Every entry in ``related_memory_ids`` references a memory that
       exists in the same document.
    4. Every ``parent_id`` references a memory that exists in the document.
    5. Every ``created_at`` timestamp is valid ISO 8601.
    6. ``updated_at`` is chronologically after ``created_at`` when both
       are present.
    7. Knowledge-graph entity IDs are unique.
    8. Knowledge-graph relationship ``source_entity_id`` and
       ``target_entity_id`` reference entities that exist in the graph.
    9. For every memory embedding, ``len(vector)`` equals ``dimensions``
       when both are present.

    Args:
        data: JSON string representing a MIF v2 document.

    Returns:
        ``(True, [])`` when all checks pass, or
        ``(False, [human-readable warning, ...])`` listing every violation
        found.  All violations are collected before returning so callers
        receive a complete picture in a single call.
    """
    try:
        document = json.loads(data)
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON: {exc}"]

    if not isinstance(document, dict):
        return False, ["Document root must be a JSON object."]

    warnings: list[str] = []

    memories: list[dict[str, Any]] = document.get("memories", [])
    if not isinstance(memories, list):
        # Structural issue — nothing meaningful to validate further.
        return False, ["'memories' field must be a JSON array."]

    # ------------------------------------------------------------------
    # Build the set of known memory IDs (used for cross-reference checks)
    # ------------------------------------------------------------------
    seen_memory_ids: dict[str, int] = {}  # id → first index where seen

    for idx, mem in enumerate(memories):
        if not isinstance(mem, dict):
            warnings.append(f"memories[{idx}]: entry is not a JSON object, skipping.")
            continue

        mem_id = mem.get("id")

        # Check 1 — valid UUID
        if mem_id is None:
            warnings.append(f"memories[{idx}]: missing 'id' field.")
        elif not isinstance(mem_id, str) or not _is_valid_uuid(mem_id):
            warnings.append(
                f"memories[{idx}]: 'id' value {mem_id!r} is not a valid UUID."
            )
        else:
            # Check 2 — unique
            if mem_id in seen_memory_ids:
                warnings.append(
                    f"memories[{idx}]: duplicate 'id' {mem_id!r} "
                    f"(first seen at index {seen_memory_ids[mem_id]})."
                )
            else:
                seen_memory_ids[mem_id] = idx

    known_ids: set[str] = set(seen_memory_ids.keys())

    # ------------------------------------------------------------------
    # Per-memory semantic checks
    # ------------------------------------------------------------------
    for idx, mem in enumerate(memories):
        if not isinstance(mem, dict):
            continue  # already warned above

        mem_label = f"memories[{idx}] (id={mem.get('id', '<missing>')!r})"

        # Check 3 — related_memory_ids referential integrity
        related: list = mem.get("related_memory_ids", [])
        if isinstance(related, list):
            for ref in related:
                if not isinstance(ref, str):
                    warnings.append(
                        f"{mem_label}: related_memory_ids entry {ref!r} is not a string."
                    )
                elif ref not in known_ids:
                    warnings.append(
                        f"{mem_label}: related_memory_ids references unknown "
                        f"memory id {ref!r}."
                    )

        # Check 4 — parent_id referential integrity
        parent_id = mem.get("parent_id")
        if parent_id is not None:
            if not isinstance(parent_id, str):
                warnings.append(
                    f"{mem_label}: 'parent_id' must be a string, got {type(parent_id).__name__}."
                )
            elif parent_id not in known_ids:
                warnings.append(
                    f"{mem_label}: 'parent_id' references unknown memory id {parent_id!r}."
                )

        # Check 5 — created_at is valid ISO 8601
        created_raw: Any = mem.get("created_at")
        created_dt: datetime | None = None
        if created_raw is not None:
            created_dt = _parse_iso8601(created_raw)
            if created_dt is None:
                warnings.append(
                    f"{mem_label}: 'created_at' value {created_raw!r} is not "
                    f"valid ISO 8601 (expected format: YYYY-MM-DDTHH:MM:SSZ)."
                )

        # Check 6 — updated_at > created_at
        updated_raw: Any = mem.get("updated_at")
        if updated_raw is not None:
            updated_dt = _parse_iso8601(updated_raw)
            if updated_dt is None:
                warnings.append(
                    f"{mem_label}: 'updated_at' value {updated_raw!r} is not "
                    f"valid ISO 8601."
                )
            elif created_dt is not None and updated_dt < created_dt:
                warnings.append(
                    f"{mem_label}: 'updated_at' ({updated_raw}) is before "
                    f"'created_at' ({created_raw})."
                )

        # Check 9 — embedding vector length matches dimensions
        embeddings: Any = mem.get("embeddings")
        if isinstance(embeddings, dict):
            dims: Any = embeddings.get("dimensions")
            vector: Any = embeddings.get("vector")
            if dims is not None and vector is not None:
                if isinstance(vector, list) and isinstance(dims, int):
                    if len(vector) != dims:
                        warnings.append(
                            f"{mem_label}: embedding 'vector' has {len(vector)} "
                            f"elements but 'dimensions' is {dims}."
                        )

    # ------------------------------------------------------------------
    # Knowledge graph checks (7 and 8)
    # ------------------------------------------------------------------
    kg: Any = document.get("knowledge_graph")
    if isinstance(kg, dict):
        entities: list = kg.get("entities", [])
        relationships: list = kg.get("relationships", [])

        # Check 7 — entity IDs are unique
        seen_entity_ids: dict[str, int] = {}
        for eidx, entity in enumerate(entities):
            if not isinstance(entity, dict):
                warnings.append(
                    f"knowledge_graph.entities[{eidx}]: entry is not a JSON object."
                )
                continue
            eid: Any = entity.get("id")
            if eid is None:
                warnings.append(
                    f"knowledge_graph.entities[{eidx}]: missing 'id' field."
                )
            elif not isinstance(eid, str):
                warnings.append(
                    f"knowledge_graph.entities[{eidx}]: 'id' must be a string, "
                    f"got {type(eid).__name__}."
                )
            elif eid in seen_entity_ids:
                warnings.append(
                    f"knowledge_graph.entities[{eidx}]: duplicate entity id "
                    f"{eid!r} (first seen at index {seen_entity_ids[eid]})."
                )
            else:
                seen_entity_ids[eid] = eidx

        known_entity_ids: set[str] = set(seen_entity_ids.keys())

        # Check 8 — relationship source/target reference existing entities
        for ridx, rel in enumerate(relationships):
            if not isinstance(rel, dict):
                warnings.append(
                    f"knowledge_graph.relationships[{ridx}]: entry is not a JSON object."
                )
                continue
            rel_label = (
                f"knowledge_graph.relationships[{ridx}] "
                f"(id={rel.get('id', '<missing>')!r})"
            )
            src: Any = rel.get("source_entity_id")
            tgt: Any = rel.get("target_entity_id")

            if src is None:
                warnings.append(f"{rel_label}: missing 'source_entity_id'.")
            elif not isinstance(src, str):
                warnings.append(
                    f"{rel_label}: 'source_entity_id' must be a string."
                )
            elif src not in known_entity_ids:
                warnings.append(
                    f"{rel_label}: 'source_entity_id' {src!r} references an "
                    f"entity that does not exist in knowledge_graph.entities."
                )

            if tgt is None:
                warnings.append(f"{rel_label}: missing 'target_entity_id'.")
            elif not isinstance(tgt, str):
                warnings.append(
                    f"{rel_label}: 'target_entity_id' must be a string."
                )
            elif tgt not in known_entity_ids:
                warnings.append(
                    f"{rel_label}: 'target_entity_id' {tgt!r} references an "
                    f"entity that does not exist in knowledge_graph.entities."
                )

    if warnings:
        return False, warnings
    return True, []


def deduplicate(doc: MifDocument) -> tuple[MifDocument, int]:
    """Deduplicate memories by SHA-256 content hash.

    Per the MIF spec (section 6), implementations SHOULD deduplicate by
    content hash rather than UUID collision.

    Args:
        doc: The MIF document to deduplicate.

    Returns:
        Tuple of (deduplicated document, number of duplicates removed).
    """
    seen_hashes: set[str] = set()
    unique_memories: list = []

    for mem in doc.memories:
        content_hash = hashlib.sha256(mem.content.encode("utf-8")).hexdigest()
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_memories.append(mem)

    removed = len(doc.memories) - len(unique_memories)
    deduped = MifDocument(
        mif_version=doc.mif_version,
        memories=unique_memories,
        generator=doc.generator,
        export_meta=doc.export_meta,
        knowledge_graph=doc.knowledge_graph,
        vendor_extensions=doc.vendor_extensions,
        _extra=doc._extra,
    )
    return deduped, removed
