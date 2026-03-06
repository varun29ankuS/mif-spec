"""Unit tests for mif.adapters — all format adapters."""

import json
import uuid

import pytest

from mif.adapters import (
    ShodhAdapter,
    Mem0Adapter,
    GenericJsonAdapter,
    MarkdownAdapter,
)
from mif.models import (
    Memory, MifDocument, KnowledgeGraph, GraphEntity, GraphRelationship,
    Source, Embedding, EntityReference,
)


# ── ShodhAdapter ─────────────────────────────────────────────────────────

class TestShodhAdapter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.adapter = ShodhAdapter()

    def test_name_and_format_id(self):
        assert self.adapter.name() == "Shodh Memory (MIF v2/v1)"
        assert self.adapter.format_id() == "shodh"

    # ── detect ──

    def test_detect_v2(self, shodh_v2_json):
        assert self.adapter.detect(shodh_v2_json) is True

    def test_detect_v1(self, shodh_v1_json):
        assert self.adapter.detect(shodh_v1_json) is True

    def test_detect_v2_with_whitespace(self, shodh_v2_json):
        assert self.adapter.detect("  \n" + shodh_v2_json) is True

    def test_detect_rejects_non_json(self):
        assert self.adapter.detect("---\ntype: observation\n---\nhello") is False

    def test_detect_rejects_array(self, mem0_json):
        assert self.adapter.detect(mem0_json) is False

    def test_detect_rejects_plain_object(self):
        assert self.adapter.detect('{"foo": "bar"}') is False

    def test_detect_shodh_memory_marker(self):
        data = json.dumps({"generator": {"name": "shodh-memory"}, "memories": []})
        assert self.adapter.detect(data) is True

    # ── to_mif v2 ──

    def test_to_mif_v2_passthrough(self, shodh_v2_json):
        doc = self.adapter.to_mif(shodh_v2_json)
        assert doc.mif_version == "2.0"
        assert len(doc.memories) >= 1

    def test_to_mif_v2_preserves_knowledge_graph(self):
        data = json.dumps({
            "mif_version": "2.0",
            "memories": [],
            "knowledge_graph": {
                "entities": [{"id": "e1", "name": "A"}],
                "relationships": [],
            },
        })
        doc = self.adapter.to_mif(data)
        assert doc.knowledge_graph is not None
        assert len(doc.knowledge_graph.entities) == 1

    def test_to_mif_v2_preserves_vendor_extensions(self):
        data = json.dumps({
            "mif_version": "2.0",
            "memories": [],
            "vendor_extensions": {"x_foo": "bar"},
        })
        doc = self.adapter.to_mif(data)
        assert doc.vendor_extensions["x_foo"] == "bar"

    # ── to_mif v1 ──

    def test_to_mif_v1_strips_mem_prefix(self, shodh_v1_json):
        doc = self.adapter.to_mif(shodh_v1_json)
        assert len(doc.memories) == 2
        for m in doc.memories:
            assert not m.id.startswith("mem_")
            uuid.UUID(m.id)  # Should be valid UUID

    def test_to_mif_v1_maps_type_field(self, shodh_v1_json):
        doc = self.adapter.to_mif(shodh_v1_json)
        types = {m.memory_type for m in doc.memories}
        assert "observation" in types
        assert "learning" in types

    def test_to_mif_v1_sets_generator(self, shodh_v1_json):
        doc = self.adapter.to_mif(shodh_v1_json)
        assert doc.generator["name"] == "shodh-memory-v1-import"

    def test_to_mif_v1_skips_empty_content(self):
        data = json.dumps({
            "mif_version": "1.0",
            "memories": [
                {"id": "mem_" + str(uuid.uuid4()), "content": "", "type": "observation"},
                {"id": "mem_" + str(uuid.uuid4()), "content": "real content", "type": "observation"},
            ],
        })
        doc = self.adapter.to_mif(data)
        assert len(doc.memories) == 1

    # ── from_mif ──

    def test_from_mif_produces_valid_json(self, sample_mif_doc):
        output = self.adapter.from_mif(sample_mif_doc)
        parsed = json.loads(output)
        assert parsed["mif_version"] == "2.0"
        assert isinstance(parsed["memories"], list)

    # ── empty input ──

    def test_to_mif_empty_memories(self):
        data = json.dumps({"mif_version": "2.0", "memories": []})
        doc = self.adapter.to_mif(data)
        assert doc.memories == []


# ── Mem0Adapter ──────────────────────────────────────────────────────────

class TestMem0Adapter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.adapter = Mem0Adapter()

    def test_name_and_format_id(self):
        assert self.adapter.name() == "mem0"
        assert self.adapter.format_id() == "mem0"

    # ── detect ──

    def test_detect_mem0(self, mem0_json):
        assert self.adapter.detect(mem0_json) is True

    def test_detect_rejects_non_array(self):
        assert self.adapter.detect('{"memory": "test"}') is False

    def test_detect_rejects_generic_json(self, generic_json):
        # generic has "content" not "memory"
        # But generic_json also doesn't have "memory", so mem0 should not detect it
        assert self.adapter.detect(generic_json) is False

    def test_detect_rejects_mif_array(self):
        """An array that also contains mif_version should not be detected as mem0."""
        data = json.dumps([{"memory": "x", "mif_version": "2.0"}])
        assert self.adapter.detect(data) is False

    def test_detect_with_whitespace(self, mem0_json):
        assert self.adapter.detect("   \n" + mem0_json) is True

    # ── to_mif ──

    def test_to_mif_basic(self, mem0_json):
        doc = self.adapter.to_mif(mem0_json)
        assert len(doc.memories) == 2
        assert doc.generator["name"] == "mem0-import"

    def test_to_mif_user_id_preserved(self, mem0_json):
        doc = self.adapter.to_mif(mem0_json)
        assert doc.export_meta is not None
        assert doc.export_meta["user_id"] == "user-42"

    def test_to_mif_category_mappings(self):
        """Test all mem0 category -> memory_type mappings."""
        mappings = {
            "preference": "observation",
            "preferences": "observation",
            "decision": "decision",
            "learning": "learning",
            "fact": "learning",
            "error": "error",
            "mistake": "error",
            "task": "task",
            "todo": "task",
            "unknown_cat": "observation",  # unmapped defaults to observation
        }
        for category, expected_type in mappings.items():
            data = json.dumps([{
                "id": str(uuid.uuid4()),
                "memory": f"Test {category}",
                "created_at": "2025-01-01T00:00:00Z",
                "metadata": {"category": category},
            }])
            doc = self.adapter.to_mif(data)
            assert doc.memories[0].memory_type == expected_type, (
                f"category={category!r} should map to {expected_type!r}, "
                f"got {doc.memories[0].memory_type!r}"
            )

    def test_to_mif_tags_from_metadata(self):
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "metadata": {"tags": "python, rust, go"},
        }])
        doc = self.adapter.to_mif(data)
        assert doc.memories[0].tags == ["python", "rust", "go"]

    def test_to_mif_source_set_to_mem0(self, mem0_json):
        doc = self.adapter.to_mif(mem0_json)
        for m in doc.memories:
            assert m.source is not None
            assert m.source.source_type == "mem0"

    def test_to_mif_external_id_preserved(self, mem0_json):
        doc = self.adapter.to_mif(mem0_json)
        assert doc.memories[0].external_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_to_mif_skips_empty_memory(self):
        data = json.dumps([
            {"id": str(uuid.uuid4()), "memory": "", "created_at": "2025-01-01T00:00:00Z"},
            {"id": str(uuid.uuid4()), "memory": "real", "created_at": "2025-01-01T00:00:00Z"},
        ])
        doc = self.adapter.to_mif(data)
        assert len(doc.memories) == 1

    def test_to_mif_non_array_raises(self):
        with pytest.raises(ValueError, match="JSON array"):
            self.adapter.to_mif('{"memory": "test"}')

    def test_to_mif_agent_id_preserved(self):
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "agent_id": "agent-99",
        }])
        doc = self.adapter.to_mif(data)
        assert doc.memories[0].agent_id == "agent-99"

    def test_to_mif_no_user_id(self):
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
        }])
        doc = self.adapter.to_mif(data)
        assert doc.export_meta is None

    def test_to_mif_metadata_values_stringified(self):
        data = json.dumps([{
            "id": str(uuid.uuid4()),
            "memory": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "metadata": {"count": 42, "flag": True},
        }])
        doc = self.adapter.to_mif(data)
        meta = doc.memories[0].metadata
        assert meta["count"] == "42"
        assert meta["flag"] == "True"

    # ── from_mif ──

    def test_from_mif_basic(self, sample_mif_doc):
        output = self.adapter.from_mif(sample_mif_doc)
        items = json.loads(output)
        assert isinstance(items, list)
        assert len(items) == 1
        assert "memory" in items[0]
        assert "id" in items[0]

    def test_from_mif_preserves_user_id(self):
        doc = MifDocument(
            memories=[Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z")],
            export_meta={"user_id": "user-7"},
        )
        output = self.adapter.from_mif(doc)
        items = json.loads(output)
        assert items[0]["user_id"] == "user-7"

    def test_from_mif_updated_at_fallback(self):
        doc = MifDocument(
            memories=[Memory(
                id=str(uuid.uuid4()), content="x",
                created_at="2025-01-01T00:00:00Z",
            )],
        )
        output = self.adapter.from_mif(doc)
        items = json.loads(output)
        assert items[0]["updated_at"] == "2025-01-01T00:00:00Z"

    def test_from_mif_empty(self):
        doc = MifDocument(memories=[])
        output = self.adapter.from_mif(doc)
        assert json.loads(output) == []


# ── GenericJsonAdapter ───────────────────────────────────────────────────

class TestGenericJsonAdapter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.adapter = GenericJsonAdapter()

    def test_name_and_format_id(self):
        assert self.adapter.name() == "Generic JSON"
        assert self.adapter.format_id() == "generic"

    # ── detect ──

    def test_detect_generic(self, generic_json):
        assert self.adapter.detect(generic_json) is True

    def test_detect_rejects_object(self):
        assert self.adapter.detect('{"content": "test"}') is False

    def test_detect_rejects_array_without_content(self, mem0_json):
        # mem0_json has "memory" not "content"
        assert self.adapter.detect(mem0_json) is False

    # ── to_mif ──

    def test_to_mif_basic(self, generic_json):
        doc = self.adapter.to_mif(generic_json)
        assert len(doc.memories) == 1
        assert doc.memories[0].content == "Remember to check logs daily."
        assert doc.memories[0].memory_type == "task"
        assert doc.memories[0].tags == ["ops", "logging"]

    def test_to_mif_timestamp_field(self):
        data = json.dumps([{
            "content": "Test",
            "timestamp": "2025-06-15T12:00:00Z",
        }])
        doc = self.adapter.to_mif(data)
        assert "2025-06-15" in doc.memories[0].created_at

    def test_to_mif_date_field(self):
        data = json.dumps([{
            "content": "Test",
            "date": "2025-06-15T12:00:00Z",
        }])
        doc = self.adapter.to_mif(data)
        assert "2025-06-15" in doc.memories[0].created_at

    def test_to_mif_created_at_field(self):
        data = json.dumps([{
            "content": "Test",
            "created_at": "2025-06-15T12:00:00Z",
        }])
        doc = self.adapter.to_mif(data)
        assert "2025-06-15" in doc.memories[0].created_at

    def test_to_mif_metadata_stringified(self):
        data = json.dumps([{
            "content": "Test",
            "metadata": {"level": 5},
        }])
        doc = self.adapter.to_mif(data)
        assert doc.memories[0].metadata["level"] == "5"

    def test_to_mif_source_set(self, generic_json):
        doc = self.adapter.to_mif(generic_json)
        assert doc.memories[0].source.source_type == "generic_json"

    def test_to_mif_external_id_preserved(self, generic_json):
        doc = self.adapter.to_mif(generic_json)
        assert doc.memories[0].external_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_to_mif_skips_empty_content(self):
        data = json.dumps([
            {"content": ""},
            {"content": "real"},
        ])
        doc = self.adapter.to_mif(data)
        assert len(doc.memories) == 1

    def test_to_mif_non_array_raises(self):
        with pytest.raises(ValueError, match="JSON array"):
            self.adapter.to_mif('{"content": "test"}')

    def test_to_mif_memory_type_field(self):
        data = json.dumps([{"content": "Test", "memory_type": "decision"}])
        doc = self.adapter.to_mif(data)
        assert doc.memories[0].memory_type == "decision"

    def test_to_mif_type_lowercased(self):
        data = json.dumps([{"content": "Test", "type": "LEARNING"}])
        doc = self.adapter.to_mif(data)
        assert doc.memories[0].memory_type == "learning"

    def test_to_mif_missing_id_generates_uuid(self):
        data = json.dumps([{"content": "no id"}])
        doc = self.adapter.to_mif(data)
        uuid.UUID(doc.memories[0].id)

    def test_to_mif_invalid_id_generates_uuid(self):
        data = json.dumps([{"content": "bad id", "id": "not-a-uuid"}])
        doc = self.adapter.to_mif(data)
        uuid.UUID(doc.memories[0].id)

    # ── from_mif ──

    def test_from_mif_basic(self, sample_mif_doc):
        output = self.adapter.from_mif(sample_mif_doc)
        items = json.loads(output)
        assert isinstance(items, list)
        assert len(items) == 1
        assert "content" in items[0]
        assert "type" in items[0]
        assert "timestamp" in items[0]

    def test_from_mif_includes_tags(self):
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()), content="x",
                created_at="2025-01-01T00:00:00Z", tags=["a", "b"],
            ),
        ])
        output = self.adapter.from_mif(doc)
        items = json.loads(output)
        assert items[0]["tags"] == ["a", "b"]

    def test_from_mif_omits_empty_tags(self):
        doc = MifDocument(memories=[
            Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z"),
        ])
        output = self.adapter.from_mif(doc)
        items = json.loads(output)
        assert "tags" not in items[0]

    def test_from_mif_empty(self):
        doc = MifDocument(memories=[])
        output = self.adapter.from_mif(doc)
        assert json.loads(output) == []


# ── MarkdownAdapter ──────────────────────────────────────────────────────

class TestMarkdownAdapter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.adapter = MarkdownAdapter()

    def test_name_and_format_id(self):
        assert self.adapter.name() == "Markdown (YAML frontmatter)"
        assert self.adapter.format_id() == "markdown"

    # ── detect ──

    def test_detect_markdown(self, markdown_single):
        assert self.adapter.detect(markdown_single) is True

    def test_detect_with_leading_whitespace(self):
        assert self.adapter.detect("  ---\ntype: observation\n---\nhello") is True

    def test_detect_rejects_json(self):
        assert self.adapter.detect('{"mif_version": "2.0"}') is False

    def test_detect_rejects_array(self):
        assert self.adapter.detect('[{"content": "x"}]') is False

    # ── to_mif single block ──

    def test_to_mif_single_block(self, markdown_single):
        doc = self.adapter.to_mif(markdown_single)
        assert len(doc.memories) == 1
        assert doc.memories[0].content == "User prefers pytest over unittest."
        assert doc.memories[0].memory_type == "observation"
        assert "2025-06-15" in doc.memories[0].created_at

    def test_to_mif_tags_bracket_syntax(self, markdown_single):
        doc = self.adapter.to_mif(markdown_single)
        assert doc.memories[0].tags == ["python", "testing"]

    # ── to_mif multiple blocks ──

    def test_to_mif_multiple_blocks(self, markdown_multi):
        doc = self.adapter.to_mif(markdown_multi)
        assert len(doc.memories) == 2
        assert doc.memories[0].memory_type == "observation"
        assert doc.memories[1].memory_type == "decision"

    # ── to_mif with extra frontmatter ──

    def test_to_mif_extra_frontmatter_to_metadata(self):
        md = (
            "---\n"
            "type: observation\n"
            "created_at: 2025-01-01T00:00:00Z\n"
            "author: Alice\n"
            "priority: high\n"
            "---\n"
            "Some content.\n"
        )
        doc = self.adapter.to_mif(md)
        m = doc.memories[0]
        assert m.metadata["author"] == "Alice"
        assert m.metadata["priority"] == "high"

    def test_to_mif_source_set_to_markdown(self, markdown_single):
        doc = self.adapter.to_mif(markdown_single)
        assert doc.memories[0].source.source_type == "markdown"

    def test_to_mif_generates_uuid(self, markdown_single):
        doc = self.adapter.to_mif(markdown_single)
        uuid.UUID(doc.memories[0].id)

    def test_to_mif_skips_empty_body(self):
        md = "---\ntype: observation\n---\n"
        doc = self.adapter.to_mif(md)
        assert len(doc.memories) == 0

    def test_to_mif_tags_comma_syntax(self):
        md = (
            "---\n"
            "type: observation\n"
            "tags: alpha, beta, gamma\n"
            "---\n"
            "Content here.\n"
        )
        doc = self.adapter.to_mif(md)
        assert doc.memories[0].tags == ["alpha", "beta", "gamma"]

    def test_to_mif_date_field(self):
        md = (
            "---\n"
            "date: 2025-03-01T00:00:00Z\n"
            "---\n"
            "Content.\n"
        )
        doc = self.adapter.to_mif(md)
        assert "2025-03-01" in doc.memories[0].created_at

    def test_to_mif_with_id_in_frontmatter(self):
        uid = str(uuid.uuid4())
        md = (
            "---\n"
            f"id: {uid}\n"
            "---\n"
            "Content.\n"
        )
        doc = self.adapter.to_mif(md)
        assert doc.memories[0].id == uid

    # ── from_mif ──

    def test_from_mif_basic(self, sample_mif_doc):
        output = self.adapter.from_mif(sample_mif_doc)
        assert output.startswith("---\n")
        assert "type:" in output

    def test_from_mif_includes_tags(self):
        doc = MifDocument(memories=[
            Memory(
                id=str(uuid.uuid4()), content="x",
                created_at="2025-01-01T00:00:00Z",
                tags=["a", "b"],
            ),
        ])
        output = self.adapter.from_mif(doc)
        assert "tags: [a, b]" in output

    def test_from_mif_no_tags_line_when_empty(self):
        doc = MifDocument(memories=[
            Memory(id=str(uuid.uuid4()), content="x", created_at="2025-01-01T00:00:00Z"),
        ])
        output = self.adapter.from_mif(doc)
        assert "tags:" not in output

    def test_from_mif_empty(self):
        doc = MifDocument(memories=[])
        output = self.adapter.from_mif(doc)
        assert output == ""

    def test_from_mif_multiple_memories(self):
        doc = MifDocument(memories=[
            Memory(id=str(uuid.uuid4()), content="First", created_at="2025-01-01T00:00:00Z"),
            Memory(id=str(uuid.uuid4()), content="Second", created_at="2025-01-02T00:00:00Z"),
        ])
        output = self.adapter.from_mif(doc)
        assert output.count("---") >= 4  # at least 2 opening + 2 closing

    # ── empty / edge cases ──

    def test_to_mif_empty_string(self):
        doc = self.adapter.to_mif("")
        assert doc.memories == []

    def test_to_mif_no_frontmatter(self):
        doc = self.adapter.to_mif("just plain text\nno frontmatter")
        assert doc.memories == []
