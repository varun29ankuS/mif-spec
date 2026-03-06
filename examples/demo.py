#!/usr/bin/env python3
"""
MIF (Memory Interchange Format) end-to-end demo.

Demonstrates the full portability pipeline:
  mem0 JSON  ->  MIF v2  ->  Markdown  ->  Generic JSON  ->  MIF v2 (round-trip)

Run:
    cd mif-spec
    pip install -e python/
    python examples/demo.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Allow running from repo root without `pip install -e`
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from mif import load, dump, convert


# ---------------------------------------------------------------------------
# Step 1 — Realistic mem0 sample data
# ---------------------------------------------------------------------------

MEM0_DATA = json.dumps([
    {
        "id": "a1b2c3d4-0001-0001-0001-000000000001",
        "memory": "User prefers Rust for backend services because of memory safety and zero-cost abstractions.",
        "user_id": "dev-alice",
        "created_at": "2026-01-10T09:15:00Z",
        "metadata": {"category": "preference", "tags": "rust, backend, language"},
    },
    {
        "id": "a1b2c3d4-0002-0002-0002-000000000002",
        "memory": "Decided to use RocksDB with column families to reduce file-descriptor pressure (~85% reduction).",
        "user_id": "dev-alice",
        "created_at": "2026-01-12T14:30:00Z",
        "metadata": {"category": "decision", "tags": "database, rocksdb, architecture"},
    },
    {
        "id": "a1b2c3d4-0003-0003-0003-000000000003",
        "memory": "Hebbian learning in the knowledge graph uses additive boost (+0.025) and multiplicative decay (*0.90) — asymmetric by design.",
        "user_id": "dev-alice",
        "created_at": "2026-01-14T11:00:00Z",
        "metadata": {"category": "learning", "tags": "hebbian, graph, neuroscience"},
    },
    {
        "id": "a1b2c3d4-0004-0004-0004-000000000004",
        "memory": "parking_lot::Mutex is NOT re-entrant. Sharing one lock map between get_user_memory() and get_user_graph() caused a deadlock on first access.",
        "user_id": "dev-alice",
        "created_at": "2026-01-20T16:45:00Z",
        "metadata": {"category": "error", "tags": "concurrency, deadlock, parking-lot"},
    },
    {
        "id": "a1b2c3d4-0005-0005-0005-000000000005",
        "memory": "Vector search auto-switches from Vamana (<100k entries) to SPANN (>100k entries) with product quantization compression.",
        "user_id": "dev-alice",
        "created_at": "2026-01-22T10:20:00Z",
        "metadata": {"category": "learning", "tags": "vector-search, vamana, spann"},
    },
    {
        "id": "a1b2c3d4-0006-0006-0006-000000000006",
        "memory": "MiniLM-L6-v2 produces 384-dimensional embeddings via ONNX Runtime. Model URLs must be pinned to immutable HuggingFace commits.",
        "user_id": "dev-alice",
        "created_at": "2026-01-25T08:00:00Z",
        "metadata": {"category": "learning", "tags": "embeddings, minilm, onnx"},
    },
    {
        "id": "a1b2c3d4-0007-0007-0007-000000000007",
        "memory": "All production changes go through PR workflow: branch -> commit -> push -> PR -> CI green -> merge. No direct pushes to main.",
        "user_id": "dev-alice",
        "created_at": "2026-02-01T09:00:00Z",
        "metadata": {"category": "decision", "tags": "workflow, git, ci"},
    },
    {
        "id": "a1b2c3d4-0008-0008-0008-000000000008",
        "memory": "Fact decay now uses a glacial exponential half-life model: 90-day grace period, then half_life = 180 + (30 * support_count) days.",
        "user_id": "dev-alice",
        "created_at": "2026-02-10T13:00:00Z",
        "metadata": {"category": "decision", "tags": "decay, facts, memory-science"},
    },
])


def hr(title: str) -> None:
    """Print a section header."""
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def preview_json(text: str, max_lines: int = 25) -> None:
    """Print a truncated JSON preview."""
    lines = text.splitlines()
    for line in lines[:max_lines]:
        print(line)
    if len(lines) > max_lines:
        print(f"  ... ({len(lines) - max_lines} more lines)")


def main() -> None:
    # -----------------------------------------------------------------------
    # Step 1: Show source mem0 data
    # -----------------------------------------------------------------------
    hr("Step 1 — Source: mem0 JSON (8 memories)")
    items = json.loads(MEM0_DATA)
    print(f"Input: {len(items)} mem0 records for user '{items[0]['user_id']}'")
    print()
    for item in items:
        category = item["metadata"].get("category", "?")
        print(f"  [{category:10s}] {item['memory'][:75]}{'...' if len(item['memory']) > 75 else ''}")

    # -----------------------------------------------------------------------
    # Step 2: Convert mem0 -> MIF v2
    # -----------------------------------------------------------------------
    hr("Step 2 — Convert mem0 -> MIF v2")
    mif_json = convert(MEM0_DATA, from_format="mem0", to_format="shodh")
    doc = load(mif_json, format="shodh")

    print(f"MIF version : {doc.mif_version}")
    print(f"Generator   : {doc.generator}")
    print(f"Memories    : {len(doc.memories)}")
    print()
    print("MIF JSON output (first 25 lines):")
    preview_json(mif_json)

    # -----------------------------------------------------------------------
    # Step 3: Convert MIF v2 -> Markdown
    # -----------------------------------------------------------------------
    hr("Step 3 — Convert MIF v2 -> Markdown (YAML frontmatter)")
    markdown_output = dump(doc, format="markdown")
    lines = markdown_output.splitlines()
    delimiter_count = len([l for l in lines if l.strip() == "---"])
    print(f"Generated {delimiter_count} frontmatter delimiters across {len(doc.memories)} blocks")
    print()
    # Show first two complete memory blocks (each block = 2 delimiters: open + close frontmatter)
    delimiters_seen = 0
    for line in lines:
        if line.strip() == "---":
            delimiters_seen += 1
            if delimiters_seen == 5:
                # Reached the opening delimiter of the third block — stop
                print(f"... ({len(doc.memories) - 2} more memory blocks)")
                break
        print(line)

    # -----------------------------------------------------------------------
    # Step 4: Convert MIF v2 -> Generic JSON
    # -----------------------------------------------------------------------
    hr("Step 4 — Convert MIF v2 -> Generic JSON")
    generic_json = dump(doc, format="generic")
    generic_items = json.loads(generic_json)
    print(f"Generic JSON: {len(generic_items)} items")
    print()
    print("First item:")
    print(json.dumps(generic_items[0], indent=2))

    # -----------------------------------------------------------------------
    # Step 5: Round-trip — load markdown back and verify
    # -----------------------------------------------------------------------
    hr("Step 5 — Round-trip: Markdown -> MIF v2")
    doc_from_md = load(markdown_output, format="markdown")

    original_contents = {m.content for m in doc.memories}
    restored_contents = {m.content for m in doc_from_md.memories}
    preserved = original_contents & restored_contents
    lost = original_contents - restored_contents

    print(f"Original memories : {len(doc.memories)}")
    print(f"Restored memories : {len(doc_from_md.memories)}")
    print(f"Content preserved : {len(preserved)}/{len(original_contents)}")

    if lost:
        print(f"Lost ({len(lost)}):")
        for c in sorted(lost):
            print(f"  - {c[:80]}")
    else:
        print("Round-trip: ALL memory content preserved.")

    # Verify types survive the round-trip
    original_types = {m.content: m.memory_type for m in doc.memories}
    restored_types = {m.content: m.memory_type for m in doc_from_md.memories}
    type_mismatches = [
        (content[:50], original_types[content], restored_types.get(content, "missing"))
        for content in original_contents & restored_contents
        if original_types[content] != restored_types.get(content)
    ]
    if type_mismatches:
        print(f"\nType mismatches ({len(type_mismatches)}):")
        for content, orig, restored in type_mismatches:
            print(f"  '{content}': {orig} -> {restored}")
    else:
        print("Round-trip: ALL memory types preserved.")

    # Verify tags survive the round-trip
    original_tags = {m.content: set(m.tags) for m in doc.memories}
    restored_tags = {m.content: set(m.tags) for m in doc_from_md.memories}
    tag_mismatches = [
        content
        for content in original_contents & restored_contents
        if original_tags[content] != restored_tags.get(content, set())
    ]
    if tag_mismatches:
        print(f"\nTag mismatches ({len(tag_mismatches)} memories):")
        for content in tag_mismatches:
            print(f"  '{content[:50]}': {original_tags[content]} -> {restored_tags.get(content)}")
    else:
        print("Round-trip: ALL tags preserved.")

    # -----------------------------------------------------------------------
    # Step 6: Stats
    # -----------------------------------------------------------------------
    hr("Step 6 — Stats")

    type_counts = Counter(m.memory_type for m in doc.memories)
    all_tags = [tag for m in doc.memories for tag in m.tags]
    tag_counts = Counter(all_tags)

    print(f"Total memories    : {len(doc.memories)}")
    print()
    print("Memory types:")
    for mtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        bar = "#" * count
        print(f"  {mtype:15s} {bar} ({count})")

    print()
    print("Tag frequency (top 10):")
    for tag, count in tag_counts.most_common(10):
        bar = "#" * count
        print(f"  {tag:20s} {bar} ({count})")

    print()
    print("Adapters available:")
    from mif.registry import AdapterRegistry
    registry = AdapterRegistry()
    for fmt in registry.list_formats():
        print(f"  {fmt['format_id']:10s}  {fmt['name']}")

    hr("Done")
    print("MIF successfully moved 8 memories through the full pipeline:")
    print("  mem0 JSON  ->  MIF v2  ->  Markdown  ->  MIF v2  (lossless)")
    print("  MIF v2     ->  Generic JSON            (partial: content/type/tags)")
    print()


if __name__ == "__main__":
    main()
