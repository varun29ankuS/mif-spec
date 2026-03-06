"""MIF v2.0 data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EntityReference:
    name: str
    entity_type: str = "unknown"
    confidence: float = 1.0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name}
        d["entity_type"] = self.entity_type
        d["confidence"] = self.confidence
        return d

    @classmethod
    def from_dict(cls, data: dict) -> EntityReference:
        return cls(
            name=data["name"],
            entity_type=data.get("entity_type", "unknown"),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class Embedding:
    model: str
    dimensions: int
    vector: list[float]
    normalized: bool = True

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "vector": self.vector,
            "normalized": self.normalized,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Embedding:
        return cls(
            model=data["model"],
            dimensions=data["dimensions"],
            vector=data["vector"],
            normalized=data.get("normalized", True),
        )


@dataclass
class Source:
    source_type: str = ""
    session_id: str | None = None
    agent_name: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {}
        if self.source_type:
            d["source_type"] = self.source_type
        if self.session_id:
            d["session_id"] = self.session_id
        if self.agent_name:
            d["agent_name"] = self.agent_name
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Source:
        return cls(
            source_type=data.get("source_type", ""),
            session_id=data.get("session_id"),
            agent_name=data.get("agent_name") or data.get("agent"),
        )


@dataclass
class Memory:
    id: str
    content: str
    created_at: str
    memory_type: str = "observation"
    updated_at: str | None = None
    tags: list[str] = field(default_factory=list)
    entities: list[EntityReference] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embeddings: Embedding | None = None
    source: Source | None = None
    parent_id: str | None = None
    related_memory_ids: list[str] = field(default_factory=list)
    agent_id: str | None = None
    external_id: str | None = None
    version: int = 1
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
        }
        if self.memory_type and self.memory_type != "observation":
            d["memory_type"] = self.memory_type
        if self.updated_at:
            d["updated_at"] = self.updated_at
        if self.tags:
            d["tags"] = self.tags
        if self.entities:
            d["entities"] = [e.to_dict() for e in self.entities]
        if self.metadata:
            d["metadata"] = self.metadata
        if self.embeddings:
            d["embeddings"] = self.embeddings.to_dict()
        if self.source:
            d["source"] = self.source.to_dict()
        if self.parent_id is not None:
            d["parent_id"] = self.parent_id
        if self.related_memory_ids:
            d["related_memory_ids"] = self.related_memory_ids
        if self.agent_id is not None:
            d["agent_id"] = self.agent_id
        if self.external_id is not None:
            d["external_id"] = self.external_id
        if self.version != 1:
            d["version"] = self.version
        # Preserve any unknown fields from the source
        for k, v in self._extra.items():
            if k not in d:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        known = {
            "id", "content", "created_at", "memory_type", "updated_at",
            "tags", "entities", "metadata", "embeddings", "source",
            "parent_id", "related_memory_ids", "agent_id", "external_id", "version",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            memory_type=data.get("memory_type", "observation"),
            updated_at=data.get("updated_at"),
            tags=data.get("tags", []),
            entities=[EntityReference.from_dict(e) for e in data.get("entities", [])],
            metadata=data.get("metadata", {}),
            embeddings=Embedding.from_dict(data["embeddings"]) if data.get("embeddings") else None,
            source=Source.from_dict(data["source"]) if data.get("source") else None,
            parent_id=data.get("parent_id"),
            related_memory_ids=data.get("related_memory_ids", []),
            agent_id=data.get("agent_id"),
            external_id=data.get("external_id"),
            version=data.get("version", 1),
            _extra=extra,
        )


@dataclass
class GraphEntity:
    id: str
    name: str
    types: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None
    created_at: str | None = None
    last_seen_at: str | None = None
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.types:
            d["types"] = self.types
        if self.attributes:
            d["attributes"] = self.attributes
        if self.summary:
            d["summary"] = self.summary
        if self.created_at:
            d["created_at"] = self.created_at
        if self.last_seen_at:
            d["last_seen_at"] = self.last_seen_at
        for k, v in self._extra.items():
            if k not in d:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GraphEntity:
        known = {"id", "name", "types", "attributes", "summary", "created_at", "last_seen_at"}
        return cls(
            id=data["id"],
            name=data["name"],
            types=data.get("types", []),
            attributes=data.get("attributes", {}),
            summary=data.get("summary"),
            created_at=data.get("created_at"),
            last_seen_at=data.get("last_seen_at"),
            _extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class GraphRelationship:
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    context: str | None = None
    confidence: float | None = None
    created_at: str | None = None
    invalidated_at: str | None = None
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relation_type": self.relation_type,
        }
        if self.context:
            d["context"] = self.context
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.created_at:
            d["created_at"] = self.created_at
        if self.invalidated_at is not None:
            d["invalidated_at"] = self.invalidated_at
        for k, v in self._extra.items():
            if k not in d:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GraphRelationship:
        known = {
            "id", "source_entity_id", "target_entity_id", "relation_type",
            "context", "confidence", "created_at", "invalidated_at",
        }
        return cls(
            id=data["id"],
            source_entity_id=data["source_entity_id"],
            target_entity_id=data["target_entity_id"],
            relation_type=data["relation_type"],
            context=data.get("context"),
            confidence=data.get("confidence"),
            created_at=data.get("created_at"),
            invalidated_at=data.get("invalidated_at"),
            _extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class KnowledgeGraph:
    entities: list[GraphEntity] = field(default_factory=list)
    relationships: list[GraphRelationship] = field(default_factory=list)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
        }
        for k, v in self._extra.items():
            if k not in d:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeGraph:
        known = {"entities", "relationships"}
        return cls(
            entities=[GraphEntity.from_dict(e) for e in data.get("entities", [])],
            relationships=[GraphRelationship.from_dict(r) for r in data.get("relationships", [])],
            _extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class MifDocument:
    mif_version: str = "2.0"
    memories: list[Memory] = field(default_factory=list)
    generator: dict[str, str] | None = None
    export_meta: dict[str, Any] | None = None
    knowledge_graph: KnowledgeGraph | None = None
    vendor_extensions: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "mif_version": self.mif_version,
            "memories": [m.to_dict() for m in self.memories],
        }
        if self.generator:
            d["generator"] = self.generator
        if self.export_meta:
            d["export_meta"] = self.export_meta
        if self.knowledge_graph:
            d["knowledge_graph"] = self.knowledge_graph.to_dict()
        if self.vendor_extensions:
            d["vendor_extensions"] = self.vendor_extensions
        # Preserve unknown top-level fields
        for k, v in self._extra.items():
            if k not in d:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MifDocument:
        known = {
            "mif_version", "memories", "generator", "export_meta",
            "knowledge_graph", "vendor_extensions",
        }
        kg_data = data.get("knowledge_graph")
        return cls(
            mif_version=data.get("mif_version", "2.0"),
            memories=[Memory.from_dict(m) for m in data.get("memories", [])],
            generator=data.get("generator"),
            export_meta=data.get("export_meta"),
            knowledge_graph=KnowledgeGraph.from_dict(kg_data) if kg_data else None,
            vendor_extensions=data.get("vendor_extensions", {}),
            _extra={k: v for k, v in data.items() if k not in known},
        )
