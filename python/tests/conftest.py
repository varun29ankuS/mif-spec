"""Shared fixtures for MIF test suite."""

import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from mif.models import (
    Memory, MifDocument, KnowledgeGraph, GraphEntity, GraphRelationship,
    EntityReference, Embedding, Source,
)


def _ts(offset_hours: int = 0) -> str:
    """Return an ISO 8601 timestamp with optional hour offset from now."""
    dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc) + timedelta(hours=offset_hours)
    return dt.isoformat()


@pytest.fixture
def fixed_uuid():
    """A deterministic UUID for tests that need a stable ID."""
    return "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.fixture
def another_uuid():
    return "b2c3d4e5-f6a7-8901-bcde-f12345678901"


@pytest.fixture
def sample_memory(fixed_uuid):
    """A minimal Memory with only required fields."""
    return Memory(
        id=fixed_uuid,
        content="The user prefers dark mode.",
        created_at=_ts(),
    )


@pytest.fixture
def full_memory(fixed_uuid, another_uuid):
    """A Memory with every optional field populated."""
    return Memory(
        id=fixed_uuid,
        content="User deployed service to production.",
        created_at=_ts(),
        memory_type="decision",
        updated_at=_ts(1),
        tags=["deployment", "production"],
        entities=[
            EntityReference(name="user", entity_type="person", confidence=0.95),
            EntityReference(name="service", entity_type="software"),
        ],
        metadata={"environment": "prod", "region": "us-east-1"},
        embeddings=Embedding(
            model="text-embedding-ada-002",
            dimensions=3,
            vector=[0.1, 0.2, 0.3],
            normalized=True,
        ),
        source=Source(source_type="api", session_id="sess-123", agent_name="claude"),
        parent_id=another_uuid,
        related_memory_ids=[another_uuid],
        agent_id="agent-42",
        external_id="ext-99",
        version=2,
        _extra={"x_custom": "hello"},
    )


@pytest.fixture
def sample_graph():
    """A minimal knowledge graph with two entities and one relationship."""
    e1 = GraphEntity(id="ent-1", name="Alice", types=["person"])
    e2 = GraphEntity(id="ent-2", name="Bob", types=["person"])
    r1 = GraphRelationship(
        id="rel-1",
        source_entity_id="ent-1",
        target_entity_id="ent-2",
        relation_type="knows",
        confidence=0.9,
    )
    return KnowledgeGraph(entities=[e1, e2], relationships=[r1])


@pytest.fixture
def sample_mif_doc(sample_memory, sample_graph):
    """A full MifDocument with memories, graph, and extensions."""
    return MifDocument(
        memories=[sample_memory],
        generator={"name": "test", "version": "0.0.1"},
        export_meta={"user_id": "user-1"},
        knowledge_graph=sample_graph,
        vendor_extensions={"x_test": {"key": "value"}},
    )


@pytest.fixture
def shodh_v2_json(sample_mif_doc):
    """Serialized shodh/MIF v2 JSON string."""
    return json.dumps(sample_mif_doc.to_dict(), indent=2)


@pytest.fixture
def shodh_v1_json():
    """A v1-style shodh JSON export."""
    return json.dumps({
        "mif_version": "1.0",
        "generator": {"name": "shodh-memory", "version": "0.1.50"},
        "memories": [
            {
                "id": "mem_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "content": "User likes Python.",
                "type": "observation",
                "created_at": "2025-06-15T12:00:00+00:00",
                "tags": ["python"],
            },
            {
                "id": "mem_b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "content": "User uses VS Code.",
                "type": "learning",
                "created_at": "2025-06-15T13:00:00+00:00",
                "tags": [],
            },
        ],
    })


@pytest.fixture
def mem0_json():
    """A mem0-format JSON array."""
    return json.dumps([
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "memory": "User prefers TypeScript over JavaScript.",
            "user_id": "user-42",
            "created_at": "2025-06-15T12:00:00Z",
            "metadata": {"category": "preference", "tags": "typescript, javascript"},
        },
        {
            "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "memory": "Decided to use PostgreSQL.",
            "user_id": "user-42",
            "created_at": "2025-06-15T13:00:00Z",
            "metadata": {"category": "decision"},
        },
    ])


@pytest.fixture
def generic_json():
    """A generic JSON array of memories."""
    return json.dumps([
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "content": "Remember to check logs daily.",
            "type": "task",
            "timestamp": "2025-06-15T12:00:00Z",
            "tags": ["ops", "logging"],
            "metadata": {"priority": "high"},
        },
    ])


@pytest.fixture
def markdown_single():
    """A single markdown memory block."""
    return (
        "---\n"
        "type: observation\n"
        "created_at: 2025-06-15T12:00:00+00:00\n"
        "tags: [python, testing]\n"
        "---\n"
        "User prefers pytest over unittest.\n"
    )


@pytest.fixture
def markdown_multi():
    """Multiple markdown memory blocks."""
    return (
        "---\n"
        "type: observation\n"
        "created_at: 2025-06-15T12:00:00+00:00\n"
        "tags: [python]\n"
        "---\n"
        "User prefers pytest.\n"
        "\n"
        "---\n"
        "type: decision\n"
        "created_at: 2025-06-15T13:00:00+00:00\n"
        "---\n"
        "Decided to use FastAPI.\n"
    )
