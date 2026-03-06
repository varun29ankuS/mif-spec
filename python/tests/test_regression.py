"""Regression tests — round-trip integrity, edge cases, and data preservation."""

import json
import uuid

import pytest

from mif.registry import load, dump, convert
from mif.models import (
    Memory, MifDocument, KnowledgeGraph, GraphEntity, GraphRelationship,
    Embedding, Source, EntityReference,
)


ALL_FORMATS = ["shodh", "mem0", "generic", "markdown"]


# ── Round-trip memory count preservation ─────────────────────────────────

class TestRoundTripMemoryCount:
    """Converting through any format pair must preserve the number of memories."""

    @pytest.fixture
    def two_memory_doc(self):
        return MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()), content="First memory",
                created_at="2025-01-01T00:00:00+00:00",
            ),
            Memory(
                id=str(uuid.uuid4()), content="Second memory",
                created_at="2025-01-02T00:00:00+00:00",
            ),
        ])

    @pytest.mark.parametrize("fmt", ALL_FORMATS)
    def test_round_trip_count(self, two_memory_doc, fmt):
        """dump to format then load back should preserve memory count."""
        serialized = dump(two_memory_doc, format=fmt)
        restored = load(serialized, format=fmt)
        assert len(restored.memories) == len(two_memory_doc.memories)


# ── mem0 category mapping ────────────────────────────────────────────────

class TestMem0CategoryMapping:
    def test_unmapped_category_preserved_in_metadata(self):
        """Categories that don't map to a known type should still be in metadata."""
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "metadata": {"category": "custom_category_xyz"},
        }])
        doc = load(data, format="mem0")
        assert doc.memories[0].metadata["category"] == "custom_category_xyz"

    def test_unmapped_category_defaults_to_observation(self):
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "metadata": {"category": "something_new"},
        }])
        doc = load(data, format="mem0")
        assert doc.memories[0].memory_type == "observation"


# ── Markdown frontmatter special characters ──────────────────────────────

class TestMarkdownSpecialCharacters:
    def test_colon_in_value(self):
        md = (
            "---\n"
            "type: observation\n"
            "note: time is 10:30:00\n"
            "---\n"
            "Content with colons: here and here: there.\n"
        )
        doc = load(md, format="markdown")
        assert len(doc.memories) == 1
        assert doc.memories[0].metadata["note"] == "time is 10:30:00"
        assert "colons" in doc.memories[0].content

    def test_brackets_in_value(self):
        md = (
            "---\n"
            "type: observation\n"
            "source: [internal, external]\n"
            "---\n"
            "Content here.\n"
        )
        doc = load(md, format="markdown")
        assert len(doc.memories) == 1
        # The "source" key is in reserved set? No, only type/tags/created_at/date/id are reserved
        assert "source" in doc.memories[0].metadata


# ── Empty memories array ─────────────────────────────────────────────────

class TestEmptyMemories:
    def test_shodh_empty(self):
        data = json.dumps({"mif_version": "2.0", "memories": []})
        doc = load(data, format="shodh")
        assert doc.memories == []

    def test_mem0_empty(self):
        doc = load("[]", format="mem0")
        assert doc.memories == []

    def test_generic_empty(self):
        doc = load("[]", format="generic")
        assert doc.memories == []

    def test_markdown_empty(self):
        doc = load("---\n---\n", format="markdown")
        assert doc.memories == []


# ── Unicode content preservation ─────────────────────────────────────────

class TestUnicodePreservation:
    UNICODE_CONTENT = (
        "User prefers dark mode. "
        "Japanese: \u6771\u4eac\u306f\u7d20\u6674\u3089\u3057\u3044\u90fd\u5e02\u3067\u3059\u3002 "
        "Arabic: \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a "
        "Emoji: \U0001f9e0\U0001f4a1\U0001f680 "
        "Math: \u222b\u222e\u2211\u220f"
    )

    @pytest.mark.parametrize("fmt", ALL_FORMATS)
    def test_unicode_round_trip(self, fmt):
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()),
                content=self.UNICODE_CONTENT,
                created_at="2025-01-01T00:00:00+00:00",
            ),
        ])
        serialized = dump(doc, format=fmt)
        restored = load(serialized, format=fmt)
        assert restored.memories[0].content == self.UNICODE_CONTENT


# ── Very large content ───────────────────────────────────────────────────

class TestLargeContent:
    def test_10kb_content_preserved(self):
        large_content = "A" * 10240  # 10KB
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()),
                content=large_content,
                created_at="2025-01-01T00:00:00+00:00",
            ),
        ])
        for fmt in ALL_FORMATS:
            serialized = dump(doc, format=fmt)
            restored = load(serialized, format=fmt)
            assert len(restored.memories[0].content) == 10240, (
                f"Content length changed through {fmt} adapter"
            )

    def test_50kb_content_preserved_shodh(self):
        large_content = "Line of text.\n" * 3500  # ~50KB
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()),
                content=large_content.strip(),
                created_at="2025-01-01T00:00:00+00:00",
            ),
        ])
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.memories[0].content == large_content.strip()


# ── Timestamps with timezone offsets ─────────────────────────────────────

class TestTimezonePreservation:
    @pytest.mark.parametrize("ts", [
        "2025-01-15T10:30:00Z",
        "2025-01-15T10:30:00+00:00",
        "2025-01-15T10:30:00+05:30",
        "2025-01-15T10:30:00-08:00",
        "2025-01-15T10:30:00.123456Z",
    ])
    def test_timestamp_survives_shodh_round_trip(self, ts):
        """Shodh is the native format, timestamps should survive exactly."""
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()),
                content="Test",
                created_at=ts,
            ),
        ])
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.memories[0].created_at == ts


# ── Full optional fields round-trip ──────────────────────────────────────

class TestFullMemoryRoundTrip:
    def test_all_fields_survive_shodh_round_trip(self, full_memory):
        doc = MifDocument(memories=[full_memory])
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        m = restored.memories[0]

        assert m.id == full_memory.id
        assert m.content == full_memory.content
        assert m.memory_type == full_memory.memory_type
        assert m.created_at == full_memory.created_at
        assert m.updated_at == full_memory.updated_at
        assert m.tags == full_memory.tags
        assert len(m.entities) == len(full_memory.entities)
        assert m.entities[0].name == full_memory.entities[0].name
        assert m.entities[0].entity_type == full_memory.entities[0].entity_type
        assert m.entities[0].confidence == full_memory.entities[0].confidence
        assert m.metadata == full_memory.metadata
        assert m.embeddings is not None
        assert m.embeddings.model == full_memory.embeddings.model
        assert m.embeddings.vector == full_memory.embeddings.vector
        assert m.source is not None
        assert m.source.source_type == full_memory.source.source_type
        assert m.source.session_id == full_memory.source.session_id
        assert m.source.agent_name == full_memory.source.agent_name
        assert m.parent_id == full_memory.parent_id
        assert m.related_memory_ids == full_memory.related_memory_ids
        assert m.agent_id == full_memory.agent_id
        assert m.external_id == full_memory.external_id
        assert m.version == full_memory.version


# ── knowledge_graph survives shodh round-trip ────────────────────────────

class TestKnowledgeGraphRoundTrip:
    def test_graph_preserved(self, sample_graph):
        doc = MifDocument(
            memories=[
                Memory(
                    id=str(uuid.uuid4()), content="Test",
                    created_at="2025-01-01T00:00:00+00:00",
                ),
            ],
            knowledge_graph=sample_graph,
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")

        assert restored.knowledge_graph is not None
        kg = restored.knowledge_graph
        assert len(kg.entities) == 2
        assert len(kg.relationships) == 1
        assert kg.entities[0].name == "Alice"
        assert kg.entities[1].name == "Bob"
        assert kg.relationships[0].relation_type == "knows"
        assert kg.relationships[0].confidence == 0.9

    def test_graph_with_all_fields(self):
        e1 = GraphEntity(
            id="e1", name="Alice", types=["person"],
            attributes={"role": "engineer"},
            summary="An engineer",
            created_at="2025-01-01T00:00:00Z",
            last_seen_at="2025-06-01T00:00:00Z",
        )
        r1 = GraphRelationship(
            id="r1", source_entity_id="e1", target_entity_id="e1",
            relation_type="self-ref", context="testing",
            confidence=0.75, created_at="2025-01-01T00:00:00Z",
        )
        kg = KnowledgeGraph(entities=[e1], relationships=[r1])
        doc = MifDocument(
            memories=[Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z")],
            knowledge_graph=kg,
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")

        re1 = restored.knowledge_graph.entities[0]
        assert re1.types == ["person"]
        assert re1.attributes["role"] == "engineer"
        assert re1.summary == "An engineer"
        assert re1.created_at == "2025-01-01T00:00:00Z"
        assert re1.last_seen_at == "2025-06-01T00:00:00Z"

        rr1 = restored.knowledge_graph.relationships[0]
        assert rr1.context == "testing"
        assert rr1.confidence == 0.75


# ── vendor_extensions preserved ──────────────────────────────────────────

class TestVendorExtensionsRoundTrip:
    def test_extensions_preserved(self):
        doc = MifDocument(
            memories=[Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z")],
            vendor_extensions={
                "x_custom_tool": {"version": "1.0", "enabled": True},
                "x_analytics": {"events": 42},
            },
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.vendor_extensions["x_custom_tool"]["version"] == "1.0"
        assert restored.vendor_extensions["x_custom_tool"]["enabled"] is True
        assert restored.vendor_extensions["x_analytics"]["events"] == 42


# ── export_meta preserved ────────────────────────────────────────────────

class TestExportMetaRoundTrip:
    def test_export_meta_preserved(self):
        doc = MifDocument(
            memories=[Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z")],
            export_meta={
                "user_id": "user-42",
                "exported_at": "2025-06-15T12:00:00Z",
                "total_memories": 100,
            },
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.export_meta["user_id"] == "user-42"
        assert restored.export_meta["exported_at"] == "2025-06-15T12:00:00Z"
        assert restored.export_meta["total_memories"] == 100


# ── Extra fields on models preserved through shodh ───────────────────────

class TestExtraFieldsPreservation:
    def test_memory_extra_fields(self):
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()), content="x",
                created_at="2025-01-01T00:00:00Z",
                _extra={"x_importance": 0.95, "x_origin": "manual"},
            ),
        ])
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.memories[0]._extra["x_importance"] == 0.95
        assert restored.memories[0]._extra["x_origin"] == "manual"

    def test_document_extra_fields(self):
        doc = MifDocument(
            memories=[],
            _extra={"x_schema_version": "2.1-draft"},
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored._extra["x_schema_version"] == "2.1-draft"

    def test_graph_entity_extra_fields(self):
        kg = KnowledgeGraph(
            entities=[GraphEntity(id="e1", name="X", _extra={"x_weight": 1.5})],
            relationships=[],
        )
        doc = MifDocument(
            memories=[Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z")],
            knowledge_graph=kg,
        )
        serialized = dump(doc, format="shodh")
        restored = load(serialized, format="shodh")
        assert restored.knowledge_graph.entities[0]._extra["x_weight"] == 1.5
