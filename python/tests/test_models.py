"""Unit tests for mif.models — all data classes and their serialization."""

import uuid
from datetime import datetime, timezone

import pytest

from mif.models import (
    EntityReference,
    Embedding,
    Source,
    Memory,
    GraphEntity,
    GraphRelationship,
    KnowledgeGraph,
    MifDocument,
)


# ── EntityReference ──────────────────────────────────────────────────────

class TestEntityReference:
    def test_defaults(self):
        er = EntityReference(name="Alice")
        assert er.entity_type == "unknown"
        assert er.confidence == 1.0

    def test_to_dict_includes_defaults(self):
        er = EntityReference(name="Alice")
        d = er.to_dict()
        assert d == {"name": "Alice", "entity_type": "unknown", "confidence": 1.0}
        assert "entity_type" in d
        assert "confidence" in d

    def test_to_dict_includes_non_defaults(self):
        er = EntityReference(name="Alice", entity_type="person", confidence=0.8)
        d = er.to_dict()
        assert d == {"name": "Alice", "entity_type": "person", "confidence": 0.8}

    def test_round_trip(self):
        original = EntityReference(name="Bob", entity_type="org", confidence=0.5)
        restored = EntityReference.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.entity_type == original.entity_type
        assert restored.confidence == original.confidence

    def test_from_dict_missing_optional(self):
        er = EntityReference.from_dict({"name": "X"})
        assert er.entity_type == "unknown"
        assert er.confidence == 1.0


# ── Embedding ────────────────────────────────────────────────────────────

class TestEmbedding:
    def test_creation(self):
        emb = Embedding(model="test", dimensions=2, vector=[0.1, 0.2])
        assert emb.normalized is True

    def test_to_dict_always_includes_all_fields(self):
        emb = Embedding(model="m", dimensions=3, vector=[1.0, 2.0, 3.0], normalized=False)
        d = emb.to_dict()
        assert set(d.keys()) == {"model", "dimensions", "vector", "normalized"}
        assert d["normalized"] is False

    def test_round_trip(self):
        original = Embedding(model="ada-002", dimensions=2, vector=[0.5, -0.5], normalized=False)
        restored = Embedding.from_dict(original.to_dict())
        assert restored.model == original.model
        assert restored.dimensions == original.dimensions
        assert restored.vector == original.vector
        assert restored.normalized == original.normalized

    def test_from_dict_default_normalized(self):
        emb = Embedding.from_dict({"model": "m", "dimensions": 1, "vector": [0.0]})
        assert emb.normalized is True

    def test_empty_vector(self):
        emb = Embedding(model="m", dimensions=0, vector=[])
        d = emb.to_dict()
        assert d["vector"] == []
        assert d["dimensions"] == 0


# ── Source ───────────────────────────────────────────────────────────────

class TestSource:
    def test_defaults(self):
        s = Source()
        assert s.source_type == ""
        assert s.session_id is None
        assert s.agent_name is None

    def test_to_dict_omits_empty(self):
        s = Source()
        assert s.to_dict() == {}

    def test_to_dict_includes_non_empty(self):
        s = Source(source_type="api", session_id="s1", agent_name="claude")
        d = s.to_dict()
        assert d == {"source_type": "api", "session_id": "s1", "agent_name": "claude"}

    def test_round_trip(self):
        original = Source(source_type="webhook", session_id="sess-99", agent_name="agent-x")
        restored = Source.from_dict(original.to_dict())
        assert restored.source_type == original.source_type
        assert restored.session_id == original.session_id
        assert restored.agent_name == original.agent_name

    def test_from_dict_agent_field_alias(self):
        """The 'agent' key should map to agent_name."""
        s = Source.from_dict({"agent": "my-agent"})
        assert s.agent_name == "my-agent"

    def test_from_dict_agent_name_takes_precedence(self):
        s = Source.from_dict({"agent_name": "preferred", "agent": "fallback"})
        assert s.agent_name == "preferred"


# ── Memory ───────────────────────────────────────────────────────────────

class TestMemory:
    def test_minimal_creation(self, fixed_uuid):
        m = Memory(id=fixed_uuid, content="hello", created_at="2025-01-01T00:00:00Z")
        assert m.memory_type == "observation"
        assert m.tags == []
        assert m.entities == []
        assert m.metadata == {}
        assert m.embeddings is None
        assert m.source is None
        assert m.parent_id is None
        assert m.related_memory_ids == []
        assert m.version == 1
        assert m._extra == {}

    def test_to_dict_minimal(self, sample_memory):
        d = sample_memory.to_dict()
        assert set(d.keys()) == {"id", "content", "created_at"}
        # memory_type "observation" is the default and should be omitted
        assert "memory_type" not in d

    def test_to_dict_full(self, full_memory):
        d = full_memory.to_dict()
        assert d["memory_type"] == "decision"
        assert d["updated_at"] is not None
        assert d["tags"] == ["deployment", "production"]
        assert len(d["entities"]) == 2
        assert d["metadata"]["environment"] == "prod"
        assert d["embeddings"]["model"] == "text-embedding-ada-002"
        assert d["source"]["source_type"] == "api"
        assert d["parent_id"] is not None
        assert len(d["related_memory_ids"]) == 1
        assert d["agent_id"] == "agent-42"
        assert d["external_id"] == "ext-99"
        assert d["version"] == 2
        assert d["x_custom"] == "hello"

    def test_extra_fields_preserved_on_round_trip(self, fixed_uuid):
        data = {
            "id": fixed_uuid,
            "content": "test",
            "created_at": "2025-01-01T00:00:00Z",
            "x_vendor_field": "vendor_value",
            "x_score": 42,
        }
        m = Memory.from_dict(data)
        assert m._extra == {"x_vendor_field": "vendor_value", "x_score": 42}
        d = m.to_dict()
        assert d["x_vendor_field"] == "vendor_value"
        assert d["x_score"] == 42

    def test_from_dict_generates_id_if_missing(self):
        m = Memory.from_dict({"content": "no id"})
        # Should be a valid UUID
        uuid.UUID(m.id)

    def test_from_dict_generates_created_at_if_missing(self):
        m = Memory.from_dict({"content": "no timestamp"})
        # Should be parseable as ISO 8601
        datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))

    def test_round_trip_with_embeddings(self):
        data = {
            "id": str(uuid.uuid4()),
            "content": "embed test",
            "created_at": "2025-01-01T00:00:00Z",
            "embeddings": {
                "model": "m",
                "dimensions": 2,
                "vector": [0.1, 0.2],
                "normalized": False,
            },
        }
        m = Memory.from_dict(data)
        assert m.embeddings is not None
        assert m.embeddings.vector == [0.1, 0.2]
        d = m.to_dict()
        assert d["embeddings"]["vector"] == [0.1, 0.2]

    def test_round_trip_with_source(self):
        data = {
            "id": str(uuid.uuid4()),
            "content": "source test",
            "created_at": "2025-01-01T00:00:00Z",
            "source": {"source_type": "api", "session_id": "s1"},
        }
        m = Memory.from_dict(data)
        assert m.source is not None
        assert m.source.source_type == "api"
        d = m.to_dict()
        assert d["source"]["source_type"] == "api"

    def test_version_1_omitted_from_dict(self, sample_memory):
        d = sample_memory.to_dict()
        assert "version" not in d

    def test_version_non_1_included(self, fixed_uuid):
        m = Memory(id=fixed_uuid, content="x", created_at="2025-01-01T00:00:00Z", version=3)
        d = m.to_dict()
        assert d["version"] == 3

    def test_empty_content(self, fixed_uuid):
        m = Memory(id=fixed_uuid, content="", created_at="2025-01-01T00:00:00Z")
        d = m.to_dict()
        assert d["content"] == ""

    def test_none_optional_fields(self):
        m = Memory.from_dict({"content": "x", "updated_at": None, "parent_id": None})
        assert m.updated_at is None
        assert m.parent_id is None
        d = m.to_dict()
        assert "updated_at" not in d
        assert "parent_id" not in d


# ── GraphEntity ──────────────────────────────────────────────────────────

class TestGraphEntity:
    def test_minimal(self):
        e = GraphEntity(id="e1", name="Alice")
        d = e.to_dict()
        assert d == {"id": "e1", "name": "Alice"}

    def test_full_round_trip(self):
        data = {
            "id": "e1",
            "name": "Alice",
            "types": ["person", "engineer"],
            "attributes": {"role": "SRE"},
            "summary": "Site reliability engineer",
            "created_at": "2025-01-01T00:00:00Z",
            "last_seen_at": "2025-06-01T00:00:00Z",
            "x_custom": "custom_val",
        }
        e = GraphEntity.from_dict(data)
        assert e._extra == {"x_custom": "custom_val"}
        d = e.to_dict()
        assert d["x_custom"] == "custom_val"
        assert d["types"] == ["person", "engineer"]
        assert d["summary"] == "Site reliability engineer"

    def test_empty_types_omitted(self):
        e = GraphEntity(id="e1", name="X", types=[])
        d = e.to_dict()
        assert "types" not in d

    def test_empty_attributes_omitted(self):
        e = GraphEntity(id="e1", name="X", attributes={})
        d = e.to_dict()
        assert "attributes" not in d


# ── GraphRelationship ────────────────────────────────────────────────────

class TestGraphRelationship:
    def test_minimal(self):
        r = GraphRelationship(
            id="r1", source_entity_id="e1", target_entity_id="e2", relation_type="knows"
        )
        d = r.to_dict()
        assert set(d.keys()) == {"id", "source_entity_id", "target_entity_id", "relation_type"}

    def test_full_round_trip(self):
        data = {
            "id": "r1",
            "source_entity_id": "e1",
            "target_entity_id": "e2",
            "relation_type": "manages",
            "context": "Project Alpha",
            "confidence": 0.85,
            "created_at": "2025-01-01T00:00:00Z",
            "invalidated_at": "2025-06-01T00:00:00Z",
            "x_weight": 1.5,
        }
        r = GraphRelationship.from_dict(data)
        assert r._extra == {"x_weight": 1.5}
        d = r.to_dict()
        assert d["invalidated_at"] == "2025-06-01T00:00:00Z"
        assert d["x_weight"] == 1.5

    def test_confidence_none_omitted(self):
        r = GraphRelationship(
            id="r1", source_entity_id="e1", target_entity_id="e2",
            relation_type="knows", confidence=None,
        )
        d = r.to_dict()
        assert "confidence" not in d

    def test_confidence_zero_included(self):
        r = GraphRelationship(
            id="r1", source_entity_id="e1", target_entity_id="e2",
            relation_type="knows", confidence=0.0,
        )
        # confidence is not None, it's 0.0, so it should be included
        d = r.to_dict()
        assert d["confidence"] == 0.0


# ── KnowledgeGraph ───────────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_empty(self):
        kg = KnowledgeGraph()
        d = kg.to_dict()
        assert d == {"entities": [], "relationships": []}

    def test_round_trip(self, sample_graph):
        d = sample_graph.to_dict()
        restored = KnowledgeGraph.from_dict(d)
        assert len(restored.entities) == 2
        assert len(restored.relationships) == 1
        assert restored.relationships[0].confidence == 0.9

    def test_extra_fields_preserved(self):
        data = {
            "entities": [],
            "relationships": [],
            "x_graph_version": "3.0",
        }
        kg = KnowledgeGraph.from_dict(data)
        assert kg._extra == {"x_graph_version": "3.0"}
        d = kg.to_dict()
        assert d["x_graph_version"] == "3.0"


# ── MifDocument ──────────────────────────────────────────────────────────

class TestMifDocument:
    def test_defaults(self):
        doc = MifDocument()
        assert doc.mif_version == "2.0"
        assert doc.memories == []
        assert doc.generator is None
        assert doc.export_meta is None
        assert doc.knowledge_graph is None
        assert doc.vendor_extensions == {}

    def test_to_dict_minimal(self):
        doc = MifDocument()
        d = doc.to_dict()
        assert d == {"mif_version": "2.0", "memories": []}
        assert "generator" not in d
        assert "export_meta" not in d
        assert "knowledge_graph" not in d
        assert "vendor_extensions" not in d

    def test_to_dict_full(self, sample_mif_doc):
        d = sample_mif_doc.to_dict()
        assert d["mif_version"] == "2.0"
        assert len(d["memories"]) == 1
        assert d["generator"]["name"] == "test"
        assert d["export_meta"]["user_id"] == "user-1"
        assert "knowledge_graph" in d
        assert d["vendor_extensions"]["x_test"]["key"] == "value"

    def test_round_trip(self, sample_mif_doc):
        d = sample_mif_doc.to_dict()
        restored = MifDocument.from_dict(d)
        assert restored.mif_version == "2.0"
        assert len(restored.memories) == 1
        assert restored.generator["name"] == "test"
        assert restored.export_meta["user_id"] == "user-1"
        assert restored.knowledge_graph is not None
        assert len(restored.knowledge_graph.entities) == 2
        assert restored.vendor_extensions["x_test"]["key"] == "value"

    def test_extra_fields_preserved(self):
        data = {
            "mif_version": "2.0",
            "memories": [],
            "x_experiment": "abc",
        }
        doc = MifDocument.from_dict(data)
        assert doc._extra == {"x_experiment": "abc"}
        d = doc.to_dict()
        assert d["x_experiment"] == "abc"

    def test_from_dict_missing_version_defaults(self):
        doc = MifDocument.from_dict({"memories": []})
        assert doc.mif_version == "2.0"

    def test_from_dict_empty_dict(self):
        doc = MifDocument.from_dict({})
        assert doc.mif_version == "2.0"
        assert doc.memories == []

    def test_with_all_optional_sections(self, full_memory, sample_graph):
        doc = MifDocument(
            memories=[full_memory],
            generator={"name": "gen", "version": "1.0"},
            export_meta={"exported_at": "2025-01-01", "user_id": "u1"},
            knowledge_graph=sample_graph,
            vendor_extensions={"x_a": 1, "x_b": {"nested": True}},
        )
        d = doc.to_dict()
        restored = MifDocument.from_dict(d)
        assert len(restored.memories) == 1
        assert restored.memories[0].memory_type == "decision"
        assert restored.generator == {"name": "gen", "version": "1.0"}
        assert restored.export_meta["user_id"] == "u1"
        assert restored.knowledge_graph is not None
        assert restored.vendor_extensions["x_b"]["nested"] is True
