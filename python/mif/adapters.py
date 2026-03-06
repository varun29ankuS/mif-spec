"""Format adapters: convert between external memory formats and MIF v2."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from mif.models import MifDocument, Memory, Source


class MifAdapter(ABC):
    """Base class for format adapters."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""

    @abstractmethod
    def format_id(self) -> str:
        """Unique format identifier."""

    @abstractmethod
    def detect(self, data: str) -> bool:
        """Return True if this adapter can handle the data."""

    @abstractmethod
    def to_mif(self, data: str) -> MifDocument:
        """Convert external format string to MifDocument."""

    @abstractmethod
    def from_mif(self, doc: MifDocument) -> str:
        """Convert MifDocument to external format string."""


def _parse_datetime(s: str | None) -> str:
    """Parse a datetime string, return ISO format or current time."""
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).isoformat()


def _ensure_uuid(s: str | None) -> str:
    """Parse UUID string or generate a new one."""
    if s:
        try:
            return str(uuid.UUID(s))
        except ValueError:
            pass
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Shodh adapter (MIF v2 native + v1 backward compat)
# ---------------------------------------------------------------------------

class ShodhAdapter(MifAdapter):
    def name(self) -> str:
        return "Shodh Memory (MIF v2/v1)"

    def format_id(self) -> str:
        return "shodh"

    def detect(self, data: str) -> bool:
        trimmed = data.lstrip()
        if not trimmed.startswith("{"):
            return False
        return '"mif_version"' in trimmed or '"shodh-memory"' in trimmed

    def to_mif(self, data: str) -> MifDocument:
        parsed = json.loads(data)
        version = parsed.get("mif_version", "")

        if version.startswith("2"):
            return MifDocument.from_dict(parsed)

        if version.startswith("1"):
            return self._convert_v1(parsed)

        # Try as v2 anyway
        return MifDocument.from_dict(parsed)

    def _convert_v1(self, v1: dict) -> MifDocument:
        memories = []
        for m in v1.get("memories", []):
            content = m.get("content", "")
            if not content:
                continue
            raw_id = m.get("id", "")
            mem_id = _strip_prefix_uuid(raw_id, "mem_")
            memory_type = (
                m.get("type") or m.get("memory_type") or "observation"
            ).lower()
            memories.append(Memory(
                id=mem_id,
                content=content,
                memory_type=memory_type,
                created_at=_parse_datetime(m.get("created_at")),
                tags=m.get("tags", []),
            ))
        return MifDocument(
            memories=memories,
            generator={"name": "shodh-memory-v1-import", "version": v1.get("mif_version", "1.0")},
        )

    def from_mif(self, doc: MifDocument) -> str:
        return json.dumps(doc.to_dict(), indent=2, ensure_ascii=False)


def _strip_prefix_uuid(s: str, prefix: str) -> str:
    stripped = s.removeprefix(prefix)
    return _ensure_uuid(stripped)


# ---------------------------------------------------------------------------
# mem0 adapter
# ---------------------------------------------------------------------------

class Mem0Adapter(MifAdapter):
    def name(self) -> str:
        return "mem0"

    def format_id(self) -> str:
        return "mem0"

    def detect(self, data: str) -> bool:
        trimmed = data.lstrip()
        if not trimmed.startswith("["):
            return False
        return '"memory"' in trimmed and '"mif_version"' not in trimmed

    def to_mif(self, data: str) -> MifDocument:
        items = json.loads(data)
        if not isinstance(items, list):
            raise ValueError("mem0 format requires a JSON array")

        memories = []
        user_id = ""

        for item in items:
            memory_text = item.get("memory", "")
            if not memory_text:
                continue

            mem_id = _ensure_uuid(item.get("id"))

            if not user_id and item.get("user_id"):
                user_id = item["user_id"]

            # Extract metadata
            metadata: dict[str, Any] = {}
            if isinstance(item.get("metadata"), dict):
                for k, v in item["metadata"].items():
                    metadata[k] = v  # preserve original type

            # Map category to memory type
            category = metadata.get("category", "")
            type_map = {
                "preference": "observation",
                "preferences": "observation",
                "decision": "decision",
                "learning": "learning",
                "fact": "learning",
                "error": "error",
                "mistake": "error",
                "task": "task",
                "todo": "task",
            }
            memory_type = type_map.get(category, "observation")

            # Extract tags from metadata (handles both string and list)
            tags = []
            if "tags" in metadata:
                raw_tags = metadata["tags"]
                if isinstance(raw_tags, list):
                    tags = [str(t).strip() for t in raw_tags if str(t).strip()]
                elif isinstance(raw_tags, str):
                    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

            memories.append(Memory(
                id=mem_id,
                content=memory_text,
                memory_type=memory_type,
                created_at=_parse_datetime(item.get("created_at")),
                tags=tags,
                metadata=metadata,
                source=Source(source_type="mem0"),
                agent_id=item.get("agent_id"),
                external_id=item.get("id"),
            ))

        doc = MifDocument(
            memories=memories,
            generator={"name": "mem0-import", "version": "1.0"},
        )
        if user_id:
            doc.export_meta = {"user_id": user_id}
        return doc

    def from_mif(self, doc: MifDocument) -> str:
        user_id = ""
        if doc.export_meta and isinstance(doc.export_meta, dict):
            user_id = doc.export_meta.get("user_id", "")

        items = []
        for m in doc.memories:
            obj: dict[str, Any] = {
                "id": m.id,
                "memory": m.content,
                "created_at": m.created_at,
                "updated_at": m.updated_at or m.created_at,
            }
            if user_id:
                obj["user_id"] = user_id
            if m.metadata:
                obj["metadata"] = m.metadata
            items.append(obj)
        return json.dumps(items, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Generic JSON adapter
# ---------------------------------------------------------------------------

class GenericJsonAdapter(MifAdapter):
    def name(self) -> str:
        return "Generic JSON"

    def format_id(self) -> str:
        return "generic"

    def detect(self, data: str) -> bool:
        trimmed = data.lstrip()
        return trimmed.startswith("[") and '"content"' in trimmed

    def to_mif(self, data: str) -> MifDocument:
        items = json.loads(data)
        if not isinstance(items, list):
            raise ValueError("Generic JSON format requires a JSON array")

        memories = []
        for item in items:
            content = item.get("content", "")
            if not content:
                continue

            mem_id = _ensure_uuid(item.get("id"))

            created_at = _parse_datetime(
                item.get("timestamp") or item.get("created_at") or item.get("date")
            )

            memory_type = (
                item.get("type") or item.get("memory_type") or "observation"
            ).lower()

            tags = []
            if isinstance(item.get("tags"), list):
                tags = [str(t) for t in item["tags"]]

            metadata: dict[str, Any] = {}
            if isinstance(item.get("metadata"), dict):
                for k, v in item["metadata"].items():
                    metadata[k] = v  # preserve original type

            memories.append(Memory(
                id=mem_id,
                content=content,
                memory_type=memory_type,
                created_at=created_at,
                tags=tags,
                metadata=metadata,
                source=Source(source_type="generic_json"),
                external_id=item.get("id"),
            ))

        return MifDocument(
            memories=memories,
            generator={"name": "generic-json-import", "version": "1.0"},
        )

    def from_mif(self, doc: MifDocument) -> str:
        items = []
        for m in doc.memories:
            obj: dict[str, Any] = {
                "id": m.id,
                "content": m.content,
                "type": m.memory_type,
                "timestamp": m.created_at,
            }
            if m.tags:
                obj["tags"] = m.tags
            if m.metadata:
                obj["metadata"] = m.metadata
            items.append(obj)
        return json.dumps(items, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Markdown adapter (YAML frontmatter)
# ---------------------------------------------------------------------------

def _escape_md_separators(text: str) -> str:
    """Escape lines that are exactly ``---`` so they don't break frontmatter parsing."""
    lines = text.split("\n")
    out = []
    for line in lines:
        if line.strip() == "---":
            out.append(line.replace("---", "\\---"))
        else:
            out.append(line)
    return "\n".join(out)


def _unescape_md_separators(text: str) -> str:
    """Reverse the escaping applied by :func:`_escape_md_separators`."""
    return text.replace("\\---", "---")


class MarkdownAdapter(MifAdapter):
    def name(self) -> str:
        return "Markdown (YAML frontmatter)"

    def format_id(self) -> str:
        return "markdown"

    def detect(self, data: str) -> bool:
        return data.lstrip().startswith("---")

    def to_mif(self, data: str) -> MifDocument:
        blocks = _split_frontmatter_blocks(data)
        memories = []

        for frontmatter, body in blocks:
            content = _unescape_md_separators(body.strip())
            if not content:
                continue

            fm = _parse_frontmatter(frontmatter)

            mem_id = _ensure_uuid(fm.get("id"))
            memory_type = fm.get("type", "observation")
            created_at = _parse_datetime(fm.get("created_at") or fm.get("date"))

            # Parse tags: supports [a, b] and a, b
            tags = []
            if "tags" in fm:
                cleaned = fm["tags"].strip().lstrip("[").rstrip("]")
                tags = [
                    t.strip().strip("'\"")
                    for t in cleaned.split(",")
                    if t.strip().strip("'\"")
                ]

            # Remaining frontmatter → metadata
            reserved = {"type", "tags", "created_at", "date", "id"}
            metadata = {k: v for k, v in fm.items() if k not in reserved}

            memories.append(Memory(
                id=mem_id,
                content=content,
                memory_type=memory_type,
                created_at=created_at,
                tags=tags,
                metadata=metadata,
                source=Source(source_type="markdown"),
            ))

        return MifDocument(
            memories=memories,
            generator={"name": "markdown-import", "version": "1.0"},
        )

    def from_mif(self, doc: MifDocument) -> str:
        parts = []
        for m in doc.memories:
            block = "---\n"
            block += f"id: {m.id}\n"
            block += f"type: {m.memory_type}\n"
            block += f"created_at: {m.created_at}\n"
            if m.tags:
                quoted_tags = [f'"{t}"' if "," in t else t for t in m.tags]
                block += f"tags: [{', '.join(quoted_tags)}]\n"
            block += "---\n"
            block += _escape_md_separators(m.content) + "\n"
            parts.append(block)
        return "\n".join(parts)


def _split_frontmatter_blocks(text: str) -> list[tuple[str, str]]:
    """Split markdown into (frontmatter, body) pairs."""
    blocks = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return blocks

    i = 0
    while i < len(lines):
        if lines[i].strip() != "---":
            i += 1
            continue
        i += 1  # skip opening ---

        # Collect frontmatter
        fm_lines = []
        while i < len(lines) and lines[i].strip() != "---":
            fm_lines.append(lines[i])
            i += 1
        if i < len(lines):
            i += 1  # skip closing ---

        # Collect body
        body_lines = []
        while i < len(lines) and lines[i].strip() != "---":
            body_lines.append(lines[i])
            i += 1

        fm = "\n".join(fm_lines)
        body = "\n".join(body_lines)
        if fm or body:
            blocks.append((fm, body))

    return blocks


def _parse_frontmatter(fm: str) -> dict[str, str]:
    """Parse simple YAML frontmatter into key-value pairs."""
    result: dict[str, str] = {}
    for line in fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pos = line.find(":")
        if pos > 0:
            key = line[:pos].strip()
            value = line[pos + 1:].strip()
            if key:
                result[key] = value
    return result


# ---------------------------------------------------------------------------
# CrewAI adapter (LTMSQLiteStorage JSON export)
# ---------------------------------------------------------------------------

class CrewAIAdapter(MifAdapter):
    """Convert CrewAI long-term memory exports to/from MIF.

    CrewAI's LTMSQLiteStorage stores rows with:
      task_description, metadata (JSON string), datetime (Unix timestamp string), score
    """

    def name(self) -> str:
        return "CrewAI"

    def format_id(self) -> str:
        return "crewai"

    def detect(self, data: str) -> bool:
        trimmed = data.lstrip()
        if not trimmed.startswith("["):
            return False
        return '"task_description"' in trimmed

    def to_mif(self, data: str) -> MifDocument:
        items = json.loads(data)
        if not isinstance(items, list):
            raise ValueError("CrewAI format requires a JSON array")

        memories = []
        for item in items:
            content = item.get("task_description", "")
            if not content:
                continue

            # Parse metadata (may be JSON string or dict)
            raw_meta = item.get("metadata", {})
            if isinstance(raw_meta, str):
                try:
                    metadata = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    metadata = {"raw": raw_meta}
            elif isinstance(raw_meta, dict):
                metadata = dict(raw_meta)
            else:
                metadata = {}

            # Parse datetime (Unix timestamp string or ISO)
            raw_dt = item.get("datetime")
            if raw_dt:
                try:
                    ts = float(raw_dt)
                    created_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                except (ValueError, TypeError, OSError):
                    created_at = _parse_datetime(str(raw_dt))
            else:
                created_at = _parse_datetime(None)

            # Preserve score in metadata
            score = item.get("score")
            if score is not None:
                metadata["score"] = score

            memories.append(Memory(
                id=_ensure_uuid(None),
                content=content,
                memory_type="observation",
                created_at=created_at,
                metadata=metadata,
                source=Source(source_type="crewai"),
            ))

        return MifDocument(
            memories=memories,
            generator={"name": "crewai-import", "version": "1.0"},
        )

    def from_mif(self, doc: MifDocument) -> str:
        items = []
        for m in doc.memories:
            meta = dict(m.metadata) if m.metadata else {}
            score = meta.pop("score", None)

            obj: dict[str, Any] = {
                "task_description": m.content,
                "metadata": json.dumps(meta, ensure_ascii=False) if meta else "{}",
                "datetime": str(datetime.fromisoformat(
                    m.created_at.replace("Z", "+00:00")
                ).timestamp()),
            }
            if score is not None:
                obj["score"] = score

            items.append(obj)
        return json.dumps(items, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LangChain / LangMem adapter
# ---------------------------------------------------------------------------

class LangChainAdapter(MifAdapter):
    """Convert LangChain/LangMem memory Item exports to/from MIF.

    LangMem's Item format:
      namespace (list[str]), key, value ({kind, content}),
      created_at, updated_at, score
    """

    def name(self) -> str:
        return "LangChain"

    def format_id(self) -> str:
        return "langchain"

    def detect(self, data: str) -> bool:
        trimmed = data.lstrip()
        if not trimmed.startswith("["):
            return False
        return '"namespace"' in trimmed and '"value"' in trimmed

    def to_mif(self, data: str) -> MifDocument:
        items = json.loads(data)
        if not isinstance(items, list):
            raise ValueError("LangChain format requires a JSON array")

        memories = []
        for item in items:
            value = item.get("value", {})
            if isinstance(value, str):
                content = value
            elif isinstance(value, dict):
                content = value.get("content", "")
            else:
                continue

            if not content:
                continue

            # Map kind → memory_type
            kind = ""
            if isinstance(value, dict):
                kind = value.get("kind", "")
            memory_type = kind.lower() if kind else "observation"
            # Normalise known types
            type_map = {
                "memory": "observation",
                "fact": "learning",
                "preference": "observation",
                "note": "observation",
            }
            memory_type = type_map.get(memory_type, memory_type) or "observation"

            # Namespace → tags
            namespace = item.get("namespace", [])
            tags = [str(ns) for ns in namespace] if isinstance(namespace, list) else []

            # Metadata
            metadata: dict[str, Any] = {}
            score = item.get("score")
            if score is not None:
                metadata["score"] = score

            created_at = _parse_datetime(item.get("created_at"))
            updated_at_raw = item.get("updated_at")
            updated_at = _parse_datetime(updated_at_raw) if updated_at_raw else None

            memories.append(Memory(
                id=_ensure_uuid(None),
                content=content,
                memory_type=memory_type,
                created_at=created_at,
                updated_at=updated_at,
                tags=tags,
                metadata=metadata if metadata else None,
                source=Source(source_type="langchain"),
                external_id=item.get("key"),
            ))

        return MifDocument(
            memories=memories,
            generator={"name": "langchain-import", "version": "1.0"},
        )

    def from_mif(self, doc: MifDocument) -> str:
        items = []
        for m in doc.memories:
            meta = dict(m.metadata) if m.metadata else {}
            score = meta.pop("score", None)

            kind = (m.memory_type or "observation").capitalize()

            obj: dict[str, Any] = {
                "namespace": m.tags if m.tags else ["memories"],
                "key": m.external_id or m.id,
                "value": {
                    "kind": kind,
                    "content": m.content,
                },
                "created_at": m.created_at,
            }
            if m.updated_at:
                obj["updated_at"] = m.updated_at
            if score is not None:
                obj["score"] = score

            items.append(obj)
        return json.dumps(items, indent=2, ensure_ascii=False)
