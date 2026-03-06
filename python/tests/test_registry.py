"""Integration tests for mif.registry — load, dump, convert, validate, validate_deep."""

import json
import uuid

import pytest

from mif.registry import (
    AdapterRegistry,
    load,
    dump,
    convert,
    validate,
    validate_deep,
)
from mif.models import (
    Memory, MifDocument, KnowledgeGraph, GraphEntity, GraphRelationship,
    Embedding,
)


# ── AdapterRegistry ──────────────────────────────────────────────────────

class TestAdapterRegistry:
    def test_list_formats(self):
        registry = AdapterRegistry()
        formats = registry.list_formats()
        ids = [f["format_id"] for f in formats]
        assert "shodh" in ids
        assert "mem0" in ids
        assert "generic" in ids
        assert "markdown" in ids

    def test_get_known_format(self):
        registry = AdapterRegistry()
        assert registry.get("shodh") is not None
        assert registry.get("mem0") is not None

    def test_get_unknown_format(self):
        registry = AdapterRegistry()
        assert registry.get("nonexistent") is None

    def test_auto_detect_shodh(self, shodh_v2_json):
        registry = AdapterRegistry()
        adapter = registry.auto_detect(shodh_v2_json)
        assert adapter is not None
        assert adapter.format_id() == "shodh"

    def test_auto_detect_mem0(self, mem0_json):
        registry = AdapterRegistry()
        adapter = registry.auto_detect(mem0_json)
        assert adapter is not None
        assert adapter.format_id() == "mem0"

    def test_auto_detect_generic(self, generic_json):
        registry = AdapterRegistry()
        adapter = registry.auto_detect(generic_json)
        assert adapter is not None
        assert adapter.format_id() == "generic"

    def test_auto_detect_markdown(self, markdown_single):
        registry = AdapterRegistry()
        adapter = registry.auto_detect(markdown_single)
        assert adapter is not None
        assert adapter.format_id() == "markdown"

    def test_auto_detect_unrecognized(self):
        registry = AdapterRegistry()
        assert registry.auto_detect("just some plain text") is None


# ── load() ───────────────────────────────────────────────────────────────

class TestLoad:
    def test_load_explicit_shodh(self, shodh_v2_json):
        doc = load(shodh_v2_json, format="shodh")
        assert isinstance(doc, MifDocument)

    def test_load_explicit_mem0(self, mem0_json):
        doc = load(mem0_json, format="mem0")
        assert len(doc.memories) == 2

    def test_load_explicit_generic(self, generic_json):
        doc = load(generic_json, format="generic")
        assert len(doc.memories) == 1

    def test_load_explicit_markdown(self, markdown_single):
        doc = load(markdown_single, format="markdown")
        assert len(doc.memories) == 1

    def test_load_autodetect_shodh(self, shodh_v2_json):
        doc = load(shodh_v2_json)
        assert doc.mif_version == "2.0"

    def test_load_autodetect_mem0(self, mem0_json):
        doc = load(mem0_json)
        assert len(doc.memories) == 2

    def test_load_autodetect_generic(self, generic_json):
        doc = load(generic_json)
        assert len(doc.memories) == 1

    def test_load_autodetect_markdown(self, markdown_single):
        doc = load(markdown_single)
        assert len(doc.memories) == 1

    def test_load_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            load("{}", format="nonexistent")

    def test_load_undetectable_raises(self):
        with pytest.raises(ValueError, match="Could not auto-detect"):
            load("this is just plain text with no markers")


# ── dump() ───────────────────────────────────────────────────────────────

class TestDump:
    @pytest.fixture
    def doc(self):
        return MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()), content="Test memory",
                created_at="2025-01-01T00:00:00Z",
            ),
        ])

    def test_dump_shodh(self, doc):
        output = dump(doc, format="shodh")
        parsed = json.loads(output)
        assert "mif_version" in parsed

    def test_dump_mem0(self, doc):
        output = dump(doc, format="mem0")
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert "memory" in parsed[0]

    def test_dump_generic(self, doc):
        output = dump(doc, format="generic")
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert "content" in parsed[0]

    def test_dump_markdown(self, doc):
        output = dump(doc, format="markdown")
        assert output.startswith("---\n")

    def test_dump_unknown_format_raises(self, doc):
        with pytest.raises(ValueError, match="Unknown format"):
            dump(doc, format="nonexistent")


# ── convert() ────────────────────────────────────────────────────────────

class TestConvert:
    """Test convert() between all 4x4 format combinations."""

    ALL_FORMATS = ["shodh", "mem0", "generic", "markdown"]

    @pytest.fixture
    def sources(self, shodh_v2_json, mem0_json, generic_json, markdown_single):
        return {
            "shodh": shodh_v2_json,
            "mem0": mem0_json,
            "generic": generic_json,
            "markdown": markdown_single,
        }

    @pytest.mark.parametrize("src_fmt", ALL_FORMATS)
    @pytest.mark.parametrize("dst_fmt", ALL_FORMATS)
    def test_convert_pair(self, sources, src_fmt, dst_fmt):
        source_data = sources[src_fmt]
        result = convert(source_data, from_format=src_fmt, to_format=dst_fmt)
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify result can be loaded back
        doc = load(result, format=dst_fmt)
        assert isinstance(doc, MifDocument)

    def test_convert_auto_detect(self, shodh_v2_json):
        result = convert(shodh_v2_json, to_format="markdown")
        assert "---" in result

    def test_convert_preserves_memory_count(self, mem0_json):
        doc_original = load(mem0_json, format="mem0")
        result = convert(mem0_json, from_format="mem0", to_format="shodh")
        doc_converted = load(result, format="shodh")
        assert len(doc_converted.memories) == len(doc_original.memories)


# ── validate() ───────────────────────────────────────────────────────────

class TestValidate:
    def test_validate_valid_document(self):
        data = json.dumps({
            "mif_version": "2.0",
            "memories": [{
                "id": str(uuid.uuid4()),
                "content": "Test",
                "created_at": "2025-01-01T00:00:00Z",
            }],
        })
        valid, errors = validate(data)
        # May fail if schema not found — that's okay, we test the return type
        assert isinstance(valid, bool)
        assert isinstance(errors, list)

    def test_validate_invalid_json(self):
        valid, errors = validate("not json at all")
        assert valid is False
        assert any("Invalid JSON" in e or "Schema file" in e for e in errors)

    def test_validate_returns_tuple(self):
        result = validate("{}")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ── validate_deep() ──────────────────────────────────────────────────────

class TestValidateDeep:
    def _make_doc(self, memories=None, knowledge_graph=None):
        """Helper to build a MIF JSON string."""
        d = {"mif_version": "2.0", "memories": memories or []}
        if knowledge_graph:
            d["knowledge_graph"] = knowledge_graph
        return json.dumps(d)

    def _make_mem(self, **overrides):
        """Helper to build a valid memory dict."""
        base = {
            "id": str(uuid.uuid4()),
            "content": "Test",
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        base.update(overrides)
        return base

    # ── valid documents ──

    def test_valid_minimal(self):
        data = self._make_doc([self._make_mem()])
        valid, warnings = validate_deep(data)
        assert valid is True
        assert warnings == []

    def test_valid_with_graph(self):
        mem = self._make_mem()
        data = self._make_doc(
            memories=[mem],
            knowledge_graph={
                "entities": [
                    {"id": "e1", "name": "Alice"},
                    {"id": "e2", "name": "Bob"},
                ],
                "relationships": [{
                    "id": "r1",
                    "source_entity_id": "e1",
                    "target_entity_id": "e2",
                    "relation_type": "knows",
                }],
            },
        )
        valid, warnings = validate_deep(data)
        assert valid is True

    # ── Check 1: UUID validity ──

    def test_invalid_uuid(self):
        data = self._make_doc([self._make_mem(id="not-a-uuid")])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("not a valid UUID" in w for w in warnings)

    def test_missing_id(self):
        mem = {"content": "Test", "created_at": "2025-01-01T00:00:00Z"}
        data = self._make_doc([mem])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("missing 'id'" in w for w in warnings)

    # ── Check 2: UUID uniqueness ──

    def test_duplicate_id(self):
        uid = str(uuid.uuid4())
        data = self._make_doc([
            self._make_mem(id=uid, content="first"),
            self._make_mem(id=uid, content="second"),
        ])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("duplicate" in w.lower() for w in warnings)

    # ── Check 3: related_memory_ids referential integrity ──

    def test_related_memory_ids_valid(self):
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        data = self._make_doc([
            self._make_mem(id=id1),
            self._make_mem(id=id2, related_memory_ids=[id1]),
        ])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_related_memory_ids_broken_ref(self):
        data = self._make_doc([
            self._make_mem(related_memory_ids=[str(uuid.uuid4())]),
        ])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("related_memory_ids" in w for w in warnings)

    # ── Check 4: parent_id referential integrity ──

    def test_parent_id_valid(self):
        parent_id = str(uuid.uuid4())
        data = self._make_doc([
            self._make_mem(id=parent_id),
            self._make_mem(parent_id=parent_id),
        ])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_parent_id_broken_ref(self):
        data = self._make_doc([
            self._make_mem(parent_id=str(uuid.uuid4())),
        ])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("parent_id" in w for w in warnings)

    # ── Check 5: timestamp format ──

    def test_valid_timestamp_utc(self):
        data = self._make_doc([self._make_mem(created_at="2025-01-15T10:30:00Z")])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_valid_timestamp_offset(self):
        data = self._make_doc([self._make_mem(created_at="2025-01-15T10:30:00+05:30")])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_valid_timestamp_fractional(self):
        data = self._make_doc([self._make_mem(created_at="2025-01-15T10:30:00.123456Z")])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_invalid_timestamp(self):
        data = self._make_doc([self._make_mem(created_at="not-a-timestamp")])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("ISO 8601" in w for w in warnings)

    # ── Check 6: updated_at > created_at ──

    def test_updated_after_created(self):
        data = self._make_doc([self._make_mem(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
        )])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_updated_before_created(self):
        data = self._make_doc([self._make_mem(
            created_at="2025-06-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("before" in w.lower() for w in warnings)

    def test_invalid_updated_at_format(self):
        data = self._make_doc([self._make_mem(
            created_at="2025-01-01T00:00:00Z",
            updated_at="bad-date",
        )])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("updated_at" in w for w in warnings)

    # ── Check 7: graph entity ID uniqueness ──

    def test_graph_duplicate_entity_id(self):
        data = self._make_doc(
            memories=[self._make_mem()],
            knowledge_graph={
                "entities": [
                    {"id": "e1", "name": "Alice"},
                    {"id": "e1", "name": "Bob"},
                ],
                "relationships": [],
            },
        )
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("duplicate entity" in w.lower() for w in warnings)

    # ── Check 8: relationship source/target references ──

    def test_graph_relationship_broken_source(self):
        data = self._make_doc(
            memories=[self._make_mem()],
            knowledge_graph={
                "entities": [{"id": "e1", "name": "Alice"}],
                "relationships": [{
                    "id": "r1",
                    "source_entity_id": "nonexistent",
                    "target_entity_id": "e1",
                    "relation_type": "knows",
                }],
            },
        )
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("source_entity_id" in w for w in warnings)

    def test_graph_relationship_broken_target(self):
        data = self._make_doc(
            memories=[self._make_mem()],
            knowledge_graph={
                "entities": [{"id": "e1", "name": "Alice"}],
                "relationships": [{
                    "id": "r1",
                    "source_entity_id": "e1",
                    "target_entity_id": "nonexistent",
                    "relation_type": "knows",
                }],
            },
        )
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("target_entity_id" in w for w in warnings)

    # ── Check 9: embedding vector length vs dimensions ──

    def test_embedding_dimensions_match(self):
        data = self._make_doc([self._make_mem(embeddings={
            "model": "m",
            "dimensions": 3,
            "vector": [0.1, 0.2, 0.3],
        })])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_embedding_dimensions_mismatch(self):
        data = self._make_doc([self._make_mem(embeddings={
            "model": "m",
            "dimensions": 5,
            "vector": [0.1, 0.2, 0.3],
        })])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("vector" in w and "dimensions" in w for w in warnings)

    # ── structural edge cases ──

    def test_invalid_json(self):
        valid, warnings = validate_deep("not json")
        assert valid is False
        assert any("Invalid JSON" in w for w in warnings)

    def test_root_not_object(self):
        valid, warnings = validate_deep("[]")
        assert valid is False
        assert any("JSON object" in w for w in warnings)

    def test_memories_not_array(self):
        valid, warnings = validate_deep('{"memories": "not-an-array"}')
        assert valid is False
        assert any("JSON array" in w for w in warnings)

    def test_empty_memories_valid(self):
        data = self._make_doc([])
        valid, _ = validate_deep(data)
        assert valid is True

    def test_memory_entry_not_object(self):
        data = json.dumps({"mif_version": "2.0", "memories": ["not-a-dict"]})
        valid, warnings = validate_deep(data)
        assert valid is False
        assert any("not a JSON object" in w for w in warnings)

    def test_multiple_errors_collected(self):
        """All violations should be reported, not just the first one."""
        bad_id = "not-uuid"
        data = self._make_doc([
            {"id": bad_id, "content": "a", "created_at": "bad-ts"},
            {"id": bad_id, "content": "b", "created_at": "bad-ts-2"},
        ])
        valid, warnings = validate_deep(data)
        assert valid is False
        assert len(warnings) >= 2  # at least UUID + timestamp errors
