/** Comprehensive test suite for @varunshodh/mif-tools. */

import * as fs from "fs";
import * as path from "path";
import { load, dump, convert, listFormats } from "./index";
import {
  createMemory,
  createDocument,
  MifDocument,
  Memory,
} from "./models";
import {
  ShodhAdapter,
  Mem0Adapter,
  GenericJsonAdapter,
  MarkdownAdapter,
} from "./adapters";

let passed = 0;
let failed = 0;

function assert(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`  FAIL: ${msg}`);
    failed++;
  } else {
    console.log(`  PASS: ${msg}`);
    passed++;
  }
}

function assertThrows(fn: () => void, msg: string): void {
  try {
    fn();
    console.error(`  FAIL: ${msg} (expected throw)`);
    failed++;
  } catch {
    console.log(`  PASS: ${msg}`);
    passed++;
  }
}

function assertDeepEqual(a: unknown, b: unknown, msg: string): void {
  if (JSON.stringify(a) === JSON.stringify(b)) {
    console.log(`  PASS: ${msg}`);
    passed++;
  } else {
    console.error(`  FAIL: ${msg}\n    expected: ${JSON.stringify(b)}\n    got:      ${JSON.stringify(a)}`);
    failed++;
  }
}

// ===================================================================
// UNIT TESTS: Models
// ===================================================================
console.log("\n=== Unit Tests: Models ===");

// -- createMemory --
console.log("\n--- createMemory ---");

{
  const m = createMemory({ content: "hello" });
  assert(m.content === "hello", "createMemory: sets content");
  assert(m.memory_type === "observation", "createMemory: defaults memory_type to observation");
  assert(typeof m.id === "string" && m.id.length === 36, "createMemory: generates valid UUID (36 chars)");
  assert(/^[0-9a-f]{8}-/.test(m.id), "createMemory: UUID starts with hex pattern");
  assert(typeof m.created_at === "string", "createMemory: sets created_at string");
  assert(!isNaN(new Date(m.created_at).getTime()), "createMemory: created_at is valid ISO date");
}

{
  const m = createMemory({
    content: "custom",
    id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    memory_type: "decision",
    created_at: "2026-01-01T00:00:00Z",
    tags: ["a", "b"],
    metadata: { key: "value" },
    parent_id: "some-parent",
    related_memory_ids: ["rel-1"],
    agent_id: "agent-007",
    external_id: "ext-42",
    version: 3,
  });
  assert(m.id === "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "createMemory: respects custom id");
  assert(m.memory_type === "decision", "createMemory: respects custom memory_type");
  assert(m.created_at === "2026-01-01T00:00:00Z", "createMemory: respects custom created_at");
  assertDeepEqual(m.tags, ["a", "b"], "createMemory: respects custom tags");
  assert(m.metadata?.key === "value", "createMemory: respects custom metadata");
  assert(m.parent_id === "some-parent", "createMemory: respects custom parent_id");
  assertDeepEqual(m.related_memory_ids, ["rel-1"], "createMemory: respects custom related_memory_ids");
  assert(m.agent_id === "agent-007", "createMemory: respects custom agent_id");
  assert(m.external_id === "ext-42", "createMemory: respects custom external_id");
  assert(m.version === 3, "createMemory: respects custom version");
}

{
  const m1 = createMemory({ content: "a" });
  const m2 = createMemory({ content: "b" });
  assert(m1.id !== m2.id, "createMemory: generates unique UUIDs across calls");
}

{
  const m = createMemory({ content: "no optionals" });
  assert(m.tags === undefined, "createMemory: tags undefined when not provided");
  assert(m.entities === undefined, "createMemory: entities undefined when not provided");
  assert(m.metadata === undefined, "createMemory: metadata undefined when not provided");
  assert(m.embeddings === undefined, "createMemory: embeddings undefined when not provided");
  assert(m.source === undefined, "createMemory: source undefined when not provided");
}

{
  const m = createMemory({
    content: "with entities",
    entities: [{ name: "Rust", entity_type: "tech", confidence: 0.9 }],
    embeddings: { model: "test", dimensions: 3, vector: [0.1, 0.2, 0.3], normalized: true },
    source: { source_type: "user", session_id: "s1" },
  });
  assert(m.entities?.length === 1, "createMemory: passes through entities");
  assert(m.embeddings?.model === "test", "createMemory: passes through embeddings");
  assert(m.source?.source_type === "user", "createMemory: passes through source");
}

// -- createDocument --
console.log("\n--- createDocument ---");

{
  const d = createDocument();
  assert(d.mif_version === "2.0", "createDocument: sets mif_version to 2.0");
  assert(Array.isArray(d.memories), "createDocument: memories is array");
  assert(d.memories.length === 0, "createDocument: defaults to empty memories");
  assert(d.generator === undefined, "createDocument: no generator by default");
  assert(d.knowledge_graph === undefined, "createDocument: no knowledge_graph by default");
  assert(d.vendor_extensions === undefined, "createDocument: no vendor_extensions by default");
}

{
  const m = createMemory({ content: "test" });
  const d = createDocument([m]);
  assert(d.memories.length === 1, "createDocument: accepts memories array");
  assert(d.memories[0].content === "test", "createDocument: memories contain correct content");
}

// ===================================================================
// UNIT TESTS: ShodhAdapter
// ===================================================================
console.log("\n=== Unit Tests: ShodhAdapter ===");
const shodh = new ShodhAdapter();

// -- detect --
console.log("\n--- ShodhAdapter.detect ---");

assert(shodh.detect('{"mif_version":"2.0","memories":[]}'), "shodh detect: v2 JSON with mif_version");
assert(shodh.detect('{"mif_version":"1.0","memories":[],"generator":{"name":"shodh-memory"}}'), "shodh detect: v1 JSON with shodh-memory");
assert(shodh.detect('{"generator":{"name":"shodh-memory"},"memories":[]}'), "shodh detect: shodh-memory without mif_version");
assert(!shodh.detect('[{"memory":"hi"}]'), "shodh detect: rejects array (mem0-like)");
assert(!shodh.detect('---\ntype: observation\n---\nhello'), "shodh detect: rejects markdown");
assert(!shodh.detect('[{"content":"hi"}]'), "shodh detect: rejects generic JSON array");
assert(!shodh.detect('plain text'), "shodh detect: rejects plain text");
assert(shodh.detect('  \n  {"mif_version":"2.0","memories":[]}'), "shodh detect: handles leading whitespace");
assert(!shodh.detect('{}'), "shodh detect: rejects empty object (no mif_version or shodh-memory)");

// -- toMif v2 passthrough --
console.log("\n--- ShodhAdapter.toMif (v2 passthrough) ---");

{
  const v2 = JSON.stringify({
    mif_version: "2.0",
    memories: [{ id: "123e4567-e89b-12d3-a456-426614174000", content: "hello", created_at: "2026-01-01T00:00:00Z" }],
    generator: { name: "test", version: "1.0" },
    export_meta: { user_id: "u1" },
    knowledge_graph: { entities: [], relationships: [] },
    vendor_extensions: { custom: { key: "val" } },
  });
  const doc = shodh.toMif(v2);
  assert(doc.mif_version === "2.0", "shodh toMif v2: preserves mif_version");
  assert(doc.memories.length === 1, "shodh toMif v2: preserves memories count");
  assert(doc.memories[0].content === "hello", "shodh toMif v2: preserves content");
  assert(doc.generator?.name === "test", "shodh toMif v2: preserves generator");
  assert((doc.export_meta as any)?.user_id === "u1", "shodh toMif v2: preserves export_meta");
  assert(doc.knowledge_graph != null, "shodh toMif v2: preserves knowledge_graph");
  assert((doc.vendor_extensions as any)?.custom?.key === "val", "shodh toMif v2: preserves vendor_extensions");
}

// -- toMif v1 conversion --
console.log("\n--- ShodhAdapter.toMif (v1 conversion) ---");

{
  const v1 = JSON.stringify({
    mif_version: "1.0",
    memories: [
      { id: "mem_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", content: "v1 memory", type: "DECISION", created_at: "2026-01-01T00:00:00Z", tags: ["t1"] },
      { id: "not-a-uuid", content: "no uuid", type: "learning" },
      { content: "no id", type: "error" },
    ],
  });
  const doc = shodh.toMif(v1);
  assert(doc.mif_version === "2.0", "shodh toMif v1: upgrades to v2.0");
  assert(doc.memories.length === 3, "shodh toMif v1: converts all 3 memories");
  assert(doc.memories[0].id === "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "shodh toMif v1: strips mem_ prefix");
  assert(doc.memories[0].memory_type === "decision", "shodh toMif v1: lowercases type");
  assertDeepEqual(doc.memories[0].tags, ["t1"], "shodh toMif v1: preserves tags");
  assert(doc.generator?.name === "shodh-memory-v1-import", "shodh toMif v1: sets generator name");
  assert(doc.generator?.version === "1.0", "shodh toMif v1: sets generator version from source");
  // Memory with non-UUID id should get a new UUID
  assert(doc.memories[1].id.length === 36, "shodh toMif v1: generates UUID for non-UUID id");
  assert(doc.memories[1].id !== "not-a-uuid", "shodh toMif v1: replaces non-UUID id");
  assert(doc.memories[1].memory_type === "learning", "shodh toMif v1: maps memory_type from type field");
  // Memory with no id should get a UUID
  assert(doc.memories[2].id.length === 36, "shodh toMif v1: generates UUID when id missing");
}

{
  const v1NoType = JSON.stringify({
    mif_version: "1.0",
    memories: [{ content: "no type field", created_at: "2026-01-01T00:00:00Z" }],
  });
  const doc = shodh.toMif(v1NoType);
  assert(doc.memories[0].memory_type === "observation", "shodh toMif v1: defaults to observation when no type");
}

{
  const v1Empty = JSON.stringify({ mif_version: "1.0", memories: [{ id: "a" }] });
  const doc = shodh.toMif(v1Empty);
  assert(doc.memories.length === 0, "shodh toMif v1: skips entries with no content");
}

{
  const v1MemType = JSON.stringify({
    mif_version: "1.2",
    memories: [{ content: "test", memory_type: "error" }],
  });
  const doc = shodh.toMif(v1MemType);
  assert(doc.memories[0].memory_type === "error", "shodh toMif v1: uses memory_type field if type missing");
  assert(doc.generator?.version === "1.2", "shodh toMif v1: captures source version 1.2");
}

// -- fromMif --
console.log("\n--- ShodhAdapter.fromMif ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "test-id", content: "serialized", created_at: "2026-01-01T00:00:00Z" }],
    generator: { name: "gen", version: "v1" },
  };
  const out = shodh.fromMif(doc);
  const parsed = JSON.parse(out);
  assert(parsed.mif_version === "2.0", "shodh fromMif: serializes mif_version");
  assert(parsed.memories[0].content === "serialized", "shodh fromMif: serializes memories");
  assert(parsed.generator.name === "gen", "shodh fromMif: serializes generator");
  assert(out.includes("\n"), "shodh fromMif: pretty-prints with indentation");
}

// ===================================================================
// UNIT TESTS: Mem0Adapter
// ===================================================================
console.log("\n=== Unit Tests: Mem0Adapter ===");
const mem0 = new Mem0Adapter();

// -- detect --
console.log("\n--- Mem0Adapter.detect ---");

assert(mem0.detect('[{"memory":"hello","id":"1"}]'), "mem0 detect: valid mem0 array");
assert(mem0.detect('  [{"memory":"hi"}]'), "mem0 detect: with leading whitespace");
assert(!mem0.detect('{"mif_version":"2.0","memories":[]}'), "mem0 detect: rejects MIF object");
assert(!mem0.detect('[{"content":"hi"}]'), "mem0 detect: rejects generic (no memory field)");
assert(!mem0.detect('---\nhello'), "mem0 detect: rejects markdown");
assert(!mem0.detect('[{"mif_version":"2.0","memory":"hi"}]'), "mem0 detect: rejects array with mif_version");
assert(!mem0.detect('not json'), "mem0 detect: rejects plain text");

// -- toMif: basic --
console.log("\n--- Mem0Adapter.toMif ---");

{
  const data = JSON.stringify([
    { id: "11111111-2222-3333-4444-555555555555", memory: "User likes tea", created_at: "2026-03-01T10:00:00Z", user_id: "u42" },
  ]);
  const doc = mem0.toMif(data);
  assert(doc.mif_version === "2.0", "mem0 toMif: sets mif_version 2.0");
  assert(doc.memories.length === 1, "mem0 toMif: converts 1 memory");
  assert(doc.memories[0].content === "User likes tea", "mem0 toMif: maps memory field to content");
  assert(doc.memories[0].id === "11111111-2222-3333-4444-555555555555", "mem0 toMif: preserves valid UUID id");
  assert(doc.memories[0].source?.source_type === "mem0", "mem0 toMif: sets source_type to mem0");
  assert(doc.generator?.name === "mem0-import", "mem0 toMif: sets generator name");
  assert((doc.export_meta as any)?.user_id === "u42", "mem0 toMif: captures user_id in export_meta");
}

// -- toMif: all 8 category mappings --
console.log("\n--- Mem0Adapter.toMif: category mappings ---");

{
  const categories: [string, string][] = [
    ["preference", "observation"],
    ["preferences", "observation"],
    ["decision", "decision"],
    ["learning", "learning"],
    ["fact", "learning"],
    ["error", "error"],
    ["mistake", "error"],
    ["task", "task"],
    ["todo", "task"],
  ];
  for (const [cat, expectedType] of categories) {
    const data = JSON.stringify([{ memory: `cat: ${cat}`, metadata: { category: cat } }]);
    const doc = mem0.toMif(data);
    assert(doc.memories[0].memory_type === expectedType, `mem0 toMif: category '${cat}' maps to '${expectedType}'`);
  }
}

{
  const data = JSON.stringify([{ memory: "unknown cat", metadata: { category: "random_thing" } }]);
  const doc = mem0.toMif(data);
  assert(doc.memories[0].memory_type === "observation", "mem0 toMif: unknown category defaults to observation");
}

// -- toMif: metadata stringification --
{
  const data = JSON.stringify([
    { memory: "meta test", metadata: { str: "hello", num: 42, obj: { nested: true }, arr: [1, 2] } },
  ]);
  const doc = mem0.toMif(data);
  assert(doc.memories[0].metadata?.str === "hello", "mem0 toMif: string metadata preserved as-is");
  assert(doc.memories[0].metadata?.num === "42", "mem0 toMif: number metadata stringified");
  assert(doc.memories[0].metadata?.obj === '{"nested":true}', "mem0 toMif: object metadata JSON-stringified");
  assert(doc.memories[0].metadata?.arr === "[1,2]", "mem0 toMif: array metadata JSON-stringified");
}

// -- toMif: tags from metadata --
{
  const data = JSON.stringify([{ memory: "tagged", metadata: { tags: "a, b, c" } }]);
  const doc = mem0.toMif(data);
  assertDeepEqual(doc.memories[0].tags, ["a", "b", "c"], "mem0 toMif: parses comma-separated tags from metadata");
}

{
  const data = JSON.stringify([{ memory: "no tags", metadata: {} }]);
  const doc = mem0.toMif(data);
  assertDeepEqual(doc.memories[0].tags, [], "mem0 toMif: empty tags when metadata has no tags field");
}

// -- toMif: agent_id --
{
  const data = JSON.stringify([{ memory: "agent mem", agent_id: "agent-x" }]);
  const doc = mem0.toMif(data);
  assert(doc.memories[0].agent_id === "agent-x", "mem0 toMif: captures agent_id");
}

// -- toMif: external_id --
{
  const data = JSON.stringify([{ id: "ext-non-uuid", memory: "ext" }]);
  const doc = mem0.toMif(data);
  assert(doc.memories[0].external_id === "ext-non-uuid", "mem0 toMif: captures non-UUID id as external_id");
  assert(doc.memories[0].id !== "ext-non-uuid", "mem0 toMif: generates new UUID when id is not valid UUID");
  assert(doc.memories[0].id.length === 36, "mem0 toMif: generated id is valid UUID length");
}

// -- toMif: empty memory skip --
{
  const data = JSON.stringify([{ id: "x", memory: "" }, { id: "y" }, { memory: "valid" }]);
  const doc = mem0.toMif(data);
  assert(doc.memories.length === 1, "mem0 toMif: skips items with empty/missing memory field");
  assert(doc.memories[0].content === "valid", "mem0 toMif: keeps the valid entry");
}

// -- toMif: user_id from first item only --
{
  const data = JSON.stringify([
    { memory: "a", user_id: "first-user" },
    { memory: "b", user_id: "second-user" },
  ]);
  const doc = mem0.toMif(data);
  assert((doc.export_meta as any)?.user_id === "first-user", "mem0 toMif: takes user_id from first item");
}

// -- toMif: no user_id --
{
  const data = JSON.stringify([{ memory: "no user" }]);
  const doc = mem0.toMif(data);
  assert(doc.export_meta === undefined, "mem0 toMif: no export_meta when no user_id");
}

// -- fromMif: basic --
console.log("\n--- Mem0Adapter.fromMif ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [
      { id: "test-id", content: "mem0 out", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
    ],
  };
  const out = mem0.fromMif(doc);
  const parsed = JSON.parse(out);
  assert(Array.isArray(parsed), "mem0 fromMif: outputs array");
  assert(parsed.length === 1, "mem0 fromMif: correct count");
  assert(parsed[0].memory === "mem0 out", "mem0 fromMif: maps content to memory field");
  assert(parsed[0].id === "test-id", "mem0 fromMif: preserves id");
  assert(parsed[0].created_at === "2026-01-01T00:00:00Z", "mem0 fromMif: preserves created_at");
  assert(parsed[0].updated_at === "2026-01-02T00:00:00Z", "mem0 fromMif: preserves updated_at");
}

// -- fromMif: updated_at fallback to created_at --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "2026-05-01T00:00:00Z" }],
  };
  const parsed = JSON.parse(mem0.fromMif(doc));
  assert(parsed[0].updated_at === "2026-05-01T00:00:00Z", "mem0 fromMif: updated_at falls back to created_at");
}

// -- fromMif: user_id from export_meta --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "2026-01-01T00:00:00Z" }],
    export_meta: { user_id: "u99" },
  };
  const parsed = JSON.parse(mem0.fromMif(doc));
  assert(parsed[0].user_id === "u99", "mem0 fromMif: includes user_id from export_meta");
}

// -- fromMif: no user_id when export_meta empty --
{
  const doc: MifDocument = { mif_version: "2.0", memories: [{ id: "id", content: "c", created_at: "2026-01-01T00:00:00Z" }] };
  const parsed = JSON.parse(mem0.fromMif(doc));
  assert(parsed[0].user_id === undefined, "mem0 fromMif: no user_id when export_meta absent");
}

// -- fromMif: metadata --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "2026-01-01T00:00:00Z", metadata: { key: "val" } }],
  };
  const parsed = JSON.parse(mem0.fromMif(doc));
  assert(parsed[0].metadata.key === "val", "mem0 fromMif: includes metadata");
}

// -- fromMif: no metadata key when metadata empty --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "2026-01-01T00:00:00Z", metadata: {} }],
  };
  const parsed = JSON.parse(mem0.fromMif(doc));
  assert(parsed[0].metadata === undefined, "mem0 fromMif: omits empty metadata");
}

// ===================================================================
// UNIT TESTS: GenericJsonAdapter
// ===================================================================
console.log("\n=== Unit Tests: GenericJsonAdapter ===");
const generic = new GenericJsonAdapter();

// -- detect --
console.log("\n--- GenericJsonAdapter.detect ---");

assert(generic.detect('[{"content":"hello"}]'), "generic detect: array with content field");
assert(generic.detect('  [{"content":"x","type":"observation"}]'), "generic detect: with whitespace");
assert(!generic.detect('{"content":"hello"}'), "generic detect: rejects plain object (not array)");
assert(!generic.detect('[{"memory":"hello"}]'), "generic detect: rejects array without content field");
assert(!generic.detect('---\nhello'), "generic detect: rejects markdown");
assert(!generic.detect('plain text'), "generic detect: rejects plain text");

// -- toMif: basic --
console.log("\n--- GenericJsonAdapter.toMif ---");

{
  const data = JSON.stringify([
    { id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", content: "generic test", type: "Decision", timestamp: "2026-02-01T12:00:00Z", tags: ["x", "y"] },
  ]);
  const doc = generic.toMif(data);
  assert(doc.mif_version === "2.0", "generic toMif: sets mif_version");
  assert(doc.memories.length === 1, "generic toMif: 1 memory");
  assert(doc.memories[0].content === "generic test", "generic toMif: preserves content");
  assert(doc.memories[0].id === "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "generic toMif: preserves valid UUID id");
  assert(doc.memories[0].memory_type === "decision", "generic toMif: lowercases type");
  assertDeepEqual(doc.memories[0].tags, ["x", "y"], "generic toMif: preserves tags array");
  assert(doc.memories[0].source?.source_type === "generic_json", "generic toMif: sets source_type");
  assert(doc.generator?.name === "generic-json-import", "generic toMif: sets generator");
}

// -- toMif: timestamp/date/created_at field priority --
{
  const withTimestamp = JSON.stringify([{ content: "ts", timestamp: "2026-01-01T00:00:00Z" }]);
  const doc1 = generic.toMif(withTimestamp);
  assert(doc1.memories[0].created_at === "2026-01-01T00:00:00.000Z", "generic toMif: uses timestamp field");

  const withCreatedAt = JSON.stringify([{ content: "ca", created_at: "2026-02-01T00:00:00Z" }]);
  const doc2 = generic.toMif(withCreatedAt);
  assert(doc2.memories[0].created_at === "2026-02-01T00:00:00.000Z", "generic toMif: uses created_at field");

  const withDate = JSON.stringify([{ content: "dt", date: "2026-03-01T00:00:00Z" }]);
  const doc3 = generic.toMif(withDate);
  assert(doc3.memories[0].created_at === "2026-03-01T00:00:00.000Z", "generic toMif: uses date field");
}

// -- toMif: metadata stringification --
{
  const data = JSON.stringify([{ content: "meta", metadata: { str: "val", num: 7 } }]);
  const doc = generic.toMif(data);
  assert(doc.memories[0].metadata?.str === "val", "generic toMif: string metadata preserved");
  assert(doc.memories[0].metadata?.num === "7", "generic toMif: non-string metadata stringified");
}

// -- toMif: empty content skip --
{
  const data = JSON.stringify([{ content: "" }, { content: "valid" }, {}]);
  const doc = generic.toMif(data);
  assert(doc.memories.length === 1, "generic toMif: skips items with empty/missing content");
}

// -- toMif: type from memory_type field --
{
  const data = JSON.stringify([{ content: "mt", memory_type: "Error" }]);
  const doc = generic.toMif(data);
  assert(doc.memories[0].memory_type === "error", "generic toMif: uses memory_type field, lowercased");
}

// -- toMif: defaults to observation --
{
  const data = JSON.stringify([{ content: "no type" }]);
  const doc = generic.toMif(data);
  assert(doc.memories[0].memory_type === "observation", "generic toMif: defaults to observation when no type");
}

// -- toMif: external_id --
{
  const data = JSON.stringify([{ id: "custom-id", content: "ext" }]);
  const doc = generic.toMif(data);
  assert(doc.memories[0].external_id === "custom-id", "generic toMif: captures non-UUID id as external_id");
}

// -- toMif: non-array tags become empty --
{
  const data = JSON.stringify([{ content: "bad tags", tags: "not-array" }]);
  const doc = generic.toMif(data);
  assertDeepEqual(doc.memories[0].tags, [], "generic toMif: non-array tags become empty array");
}

// -- fromMif: basic --
console.log("\n--- GenericJsonAdapter.fromMif ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "abc", content: "out", created_at: "2026-01-01T00:00:00Z", memory_type: "learning" }],
  };
  const parsed = JSON.parse(generic.fromMif(doc));
  assert(parsed.length === 1, "generic fromMif: correct count");
  assert(parsed[0].content === "out", "generic fromMif: preserves content");
  assert(parsed[0].type === "learning", "generic fromMif: maps memory_type to type");
  assert(parsed[0].timestamp === "2026-01-01T00:00:00Z", "generic fromMif: maps created_at to timestamp");
  assert(parsed[0].id === "abc", "generic fromMif: preserves id");
}

// -- fromMif: tags --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t", tags: ["a", "b"] }],
  };
  const parsed = JSON.parse(generic.fromMif(doc));
  assertDeepEqual(parsed[0].tags, ["a", "b"], "generic fromMif: includes tags when present");
}

// -- fromMif: no tags when empty --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t", tags: [] }],
  };
  const parsed = JSON.parse(generic.fromMif(doc));
  assert(parsed[0].tags === undefined, "generic fromMif: omits empty tags");
}

// -- fromMif: metadata --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t", metadata: { k: "v" } }],
  };
  const parsed = JSON.parse(generic.fromMif(doc));
  assert(parsed[0].metadata.k === "v", "generic fromMif: includes metadata");
}

// -- fromMif: defaults type to observation --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t" }],
  };
  const parsed = JSON.parse(generic.fromMif(doc));
  assert(parsed[0].type === "observation", "generic fromMif: defaults type to observation");
}

// ===================================================================
// UNIT TESTS: MarkdownAdapter
// ===================================================================
console.log("\n=== Unit Tests: MarkdownAdapter ===");
const md = new MarkdownAdapter();

// -- detect --
console.log("\n--- MarkdownAdapter.detect ---");

assert(md.detect("---\ntype: observation\n---\nhello"), "md detect: standard frontmatter");
assert(md.detect("  ---\ntype: observation\n---\nhello"), "md detect: with leading whitespace");
assert(!md.detect('[{"content":"hi"}]'), "md detect: rejects JSON array");
assert(!md.detect('{"mif_version":"2.0"}'), "md detect: rejects JSON object");
assert(!md.detect("hello world"), "md detect: rejects plain text");

// -- toMif: single block --
console.log("\n--- MarkdownAdapter.toMif ---");

{
  const input = "---\ntype: decision\ncreated_at: 2026-01-15T10:00:00Z\n---\nUser prefers dark mode\n";
  const doc = md.toMif(input);
  assert(doc.memories.length === 1, "md toMif single: 1 memory");
  assert(doc.memories[0].content === "User prefers dark mode", "md toMif single: content extracted");
  assert(doc.memories[0].memory_type === "decision", "md toMif single: type from frontmatter");
  assert(doc.memories[0].created_at === "2026-01-15T10:00:00.000Z", "md toMif single: created_at parsed");
  assert(doc.memories[0].id.length === 36, "md toMif single: UUID generated");
  assert(doc.memories[0].source?.source_type === "markdown", "md toMif single: source is markdown");
  assert(doc.generator?.name === "markdown-import", "md toMif single: generator set");
}

// -- toMif: multiple blocks --
{
  const input = "---\ntype: observation\n---\nFirst memory\n\n---\ntype: learning\n---\nSecond memory\n";
  const doc = md.toMif(input);
  assert(doc.memories.length === 2, "md toMif multi: 2 memories");
  assert(doc.memories[0].content === "First memory", "md toMif multi: first content");
  assert(doc.memories[0].memory_type === "observation", "md toMif multi: first type");
  assert(doc.memories[1].content === "Second memory", "md toMif multi: second content");
  assert(doc.memories[1].memory_type === "learning", "md toMif multi: second type");
}

// -- toMif: tags with brackets --
{
  const input = "---\ntags: [rust, wasm, \"web\"]\n---\nTagged content\n";
  const doc = md.toMif(input);
  assertDeepEqual(doc.memories[0].tags, ["rust", "wasm", "web"], "md toMif: bracket-wrapped tags parsed");
}

// -- toMif: tags with commas (no brackets) --
{
  const input = "---\ntags: alpha, beta, gamma\n---\nComma tags\n";
  const doc = md.toMif(input);
  assertDeepEqual(doc.memories[0].tags, ["alpha", "beta", "gamma"], "md toMif: comma-separated tags parsed");
}

// -- toMif: extra frontmatter becomes metadata --
{
  const input = "---\ntype: observation\nauthor: Alice\nproject: MIF\n---\nWith metadata\n";
  const doc = md.toMif(input);
  assert(doc.memories[0].metadata?.author === "Alice", "md toMif: extra field 'author' in metadata");
  assert(doc.memories[0].metadata?.project === "MIF", "md toMif: extra field 'project' in metadata");
  assert(doc.memories[0].metadata?.type === undefined, "md toMif: reserved 'type' not in metadata");
}

// -- toMif: empty body skip --
{
  const input = "---\ntype: observation\n---\n\n---\ntype: learning\n---\nActual content\n";
  const doc = md.toMif(input);
  assert(doc.memories.length === 1, "md toMif: skips block with empty body");
  assert(doc.memories[0].memory_type === "learning", "md toMif: keeps block with content");
}

// -- toMif: date field as alternative to created_at --
{
  const input = "---\ndate: 2026-06-15T08:00:00Z\n---\nDate field test\n";
  const doc = md.toMif(input);
  assert(doc.memories[0].created_at === "2026-06-15T08:00:00.000Z", "md toMif: uses 'date' field for created_at");
}

// -- toMif: defaults type to observation --
{
  const input = "---\ncreated_at: 2026-01-01T00:00:00Z\n---\nNo type field\n";
  const doc = md.toMif(input);
  assert(doc.memories[0].memory_type === "observation", "md toMif: defaults to observation when type missing");
}

// -- toMif: no metadata when only reserved fields --
{
  const input = "---\ntype: decision\ncreated_at: 2026-01-01T00:00:00Z\ntags: a, b\n---\nClean\n";
  const doc = md.toMif(input);
  assert(doc.memories[0].metadata === undefined, "md toMif: no metadata when only reserved fields present");
}

// -- fromMif: basic --
console.log("\n--- MarkdownAdapter.fromMif ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "md out", created_at: "2026-01-01T00:00:00Z", memory_type: "learning" }],
  };
  const out = md.fromMif(doc);
  assert(out.includes("---"), "md fromMif: has frontmatter delimiters");
  assert(out.includes("type: learning"), "md fromMif: includes type");
  assert(out.includes("created_at: 2026-01-01T00:00:00Z"), "md fromMif: includes created_at");
  assert(out.includes("md out"), "md fromMif: includes content");
}

// -- fromMif: with tags --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "tagged", created_at: "t", tags: ["a", "b"] }],
  };
  const out = md.fromMif(doc);
  assert(out.includes("tags: [a, b]"), "md fromMif: includes tags in brackets");
}

// -- fromMif: no tags line when empty --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "no tags", created_at: "t", tags: [] }],
  };
  const out = md.fromMif(doc);
  assert(!out.includes("tags:"), "md fromMif: omits tags line when empty");
}

// -- fromMif: multiple memories --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [
      { id: "1", content: "first", created_at: "t1", memory_type: "observation" },
      { id: "2", content: "second", created_at: "t2", memory_type: "decision" },
    ],
  };
  const out = md.fromMif(doc);
  assert(out.includes("first"), "md fromMif multi: contains first");
  assert(out.includes("second"), "md fromMif multi: contains second");
  assert(out.includes("type: observation"), "md fromMif multi: first type");
  assert(out.includes("type: decision"), "md fromMif multi: second type");
  // Count frontmatter blocks
  const dashes = out.split("---").length - 1;
  assert(dashes >= 4, "md fromMif multi: at least 4 frontmatter delimiters for 2 blocks");
}

// -- fromMif: defaults type to observation --
{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "no type", created_at: "t" }],
  };
  const out = md.fromMif(doc);
  assert(out.includes("type: observation"), "md fromMif: defaults type to observation");
}

// ===================================================================
// INTEGRATION TESTS
// ===================================================================
console.log("\n=== Integration Tests ===");

// -- load() with explicit format --
console.log("\n--- load() with explicit format ---");

{
  const shodhData = JSON.stringify({ mif_version: "2.0", memories: [{ id: "a", content: "x", created_at: "t" }] });
  const doc = load(shodhData, "shodh");
  assert(doc.memories.length === 1, "load(shodh): explicit format works");
}

{
  const mem0Data = JSON.stringify([{ memory: "hello" }]);
  const doc = load(mem0Data, "mem0");
  assert(doc.memories.length === 1, "load(mem0): explicit format works");
}

{
  const genData = JSON.stringify([{ content: "hi", type: "observation" }]);
  const doc = load(genData, "generic");
  assert(doc.memories.length === 1, "load(generic): explicit format works");
}

{
  const mdData = "---\ntype: observation\n---\nhello\n";
  const doc = load(mdData, "markdown");
  assert(doc.memories.length === 1, "load(markdown): explicit format works");
}

// -- load() with auto-detect --
console.log("\n--- load() with auto-detect ---");

{
  const doc = load(JSON.stringify({ mif_version: "2.0", memories: [{ id: "a", content: "x", created_at: "t" }] }));
  assert(doc.memories[0].content === "x", "load auto-detect: shodh");
}

{
  const doc = load(JSON.stringify([{ memory: "hello" }]));
  assert(doc.memories[0].content === "hello", "load auto-detect: mem0");
}

{
  const doc = load(JSON.stringify([{ content: "hi" }]));
  assert(doc.memories[0].content === "hi", "load auto-detect: generic");
}

{
  const doc = load("---\ntype: observation\n---\nhello\n");
  assert(doc.memories[0].content === "hello", "load auto-detect: markdown");
}

// -- load() error cases --
console.log("\n--- load() error cases ---");

assertThrows(() => load('{"memories":[]}', "nonexistent"), "load: throws on unknown format");
assertThrows(() => load("random plain text that nobody can parse"), "load: throws on undetectable data");
assertThrows(() => load("12345"), "load: throws on numeric string");

// -- dump() --
console.log("\n--- dump() ---");

{
  const doc: MifDocument = { mif_version: "2.0", memories: [{ id: "id", content: "c", created_at: "t" }] };
  const shodhOut = dump(doc, "shodh");
  assert(shodhOut.includes('"mif_version"'), "dump(shodh): produces MIF JSON");

  const mem0Out = dump(doc, "mem0");
  assert(mem0Out.includes('"memory"'), "dump(mem0): produces mem0 array");

  const genOut = dump(doc, "generic");
  assert(genOut.includes('"content"'), "dump(generic): produces generic JSON");

  const mdOut = dump(doc, "markdown");
  assert(mdOut.includes("---"), "dump(markdown): produces markdown");
}

assertThrows(() => dump({ mif_version: "2.0", memories: [] }, "nonexistent"), "dump: throws on unknown format");

// -- convert() --
console.log("\n--- convert() ---");

{
  const pairs: [string, string, string][] = [
    ["shodh", "mem0", JSON.stringify({ mif_version: "2.0", memories: [{ id: "a", content: "x", created_at: "t" }] })],
    ["shodh", "generic", JSON.stringify({ mif_version: "2.0", memories: [{ id: "a", content: "x", created_at: "t" }] })],
    ["shodh", "markdown", JSON.stringify({ mif_version: "2.0", memories: [{ id: "a", content: "x", created_at: "t" }] })],
    ["mem0", "shodh", JSON.stringify([{ memory: "hello" }])],
    ["mem0", "generic", JSON.stringify([{ memory: "hello" }])],
    ["mem0", "markdown", JSON.stringify([{ memory: "hello" }])],
    ["generic", "shodh", JSON.stringify([{ content: "hi" }])],
    ["generic", "mem0", JSON.stringify([{ content: "hi" }])],
    ["generic", "markdown", JSON.stringify([{ content: "hi" }])],
    ["markdown", "shodh", "---\ntype: observation\n---\nhello\n"],
    ["markdown", "mem0", "---\ntype: observation\n---\nhello\n"],
    ["markdown", "generic", "---\ntype: observation\n---\nhello\n"],
  ];
  for (const [from, to, data] of pairs) {
    const result = convert(data, { fromFormat: from, toFormat: to });
    assert(typeof result === "string" && result.length > 0, `convert: ${from} -> ${to}`);
  }
}

// -- convert() default toFormat --
{
  const result = convert(JSON.stringify([{ memory: "hi" }]), { fromFormat: "mem0" });
  assert(result.includes('"mif_version"'), "convert: defaults toFormat to shodh");
}

// -- listFormats() --
console.log("\n--- listFormats() ---");

{
  const fmts = listFormats();
  assert(fmts.length === 4, "listFormats: returns 4 formats");
  const ids = fmts.map(f => f.formatId);
  assert(ids.includes("shodh"), "listFormats: includes shodh");
  assert(ids.includes("mem0"), "listFormats: includes mem0");
  assert(ids.includes("generic"), "listFormats: includes generic");
  assert(ids.includes("markdown"), "listFormats: includes markdown");
  for (const f of fmts) {
    assert(typeof f.name === "string" && f.name.length > 0, `listFormats: ${f.formatId} has non-empty name`);
  }
}

// ===================================================================
// REGRESSION TESTS
// ===================================================================
console.log("\n=== Regression Tests ===");

// -- Round-trip memory count preservation --
console.log("\n--- Round-trip preservation ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [
      { id: "11111111-1111-1111-1111-111111111111", content: "first", created_at: "2026-01-01T00:00:00Z", memory_type: "observation" },
      { id: "22222222-2222-2222-2222-222222222222", content: "second", created_at: "2026-01-02T00:00:00Z", memory_type: "decision" },
      { id: "33333333-3333-3333-3333-333333333333", content: "third", created_at: "2026-01-03T00:00:00Z", memory_type: "learning" },
    ],
  };

  for (const fmt of ["shodh", "mem0", "generic", "markdown"] as const) {
    const serialized = dump(doc, fmt);
    const restored = load(serialized, fmt);
    assert(restored.memories.length === 3, `round-trip ${fmt}: preserves memory count`);
  }
}

// -- Unicode content preservation --
console.log("\n--- Unicode preservation ---");

{
  const unicodeContents = [
    "Emoji test: \u{1F680}\u{1F30D}\u{1F4A1}\u{2728}\u{1F916}",
    "CJK: \u4F60\u597D\u4E16\u754C\u3002\u3053\u3093\u306B\u3061\u306F\u4E16\u754C\u3002\uC548\uB155\uD558\uC138\uC694 \uC138\uACC4.",
    "Arabic: \u0645\u0631\u062D\u0628\u064B\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645",
    "Mixed: caf\u00E9 na\u00EFve r\u00E9sum\u00E9 \u00FCber \u00F1",
    "Math: \u2200x \u2208 \u211D, \u2203y : x\u00B2 + y\u00B2 = 1",
  ];

  for (const content of unicodeContents) {
    const doc: MifDocument = {
      mif_version: "2.0",
      memories: [{ id: "11111111-1111-1111-1111-111111111111", content, created_at: "2026-01-01T00:00:00Z" }],
    };

    for (const fmt of ["shodh", "mem0", "generic", "markdown"] as const) {
      const serialized = dump(doc, fmt);
      const restored = load(serialized, fmt);
      assert(restored.memories[0].content === content, `unicode ${fmt}: '${content.substring(0, 20)}...'`);
    }
  }
}

// -- Large content preservation --
console.log("\n--- Large content ---");

{
  const largeContent = "A".repeat(100_000);
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "11111111-1111-1111-1111-111111111111", content: largeContent, created_at: "2026-01-01T00:00:00Z" }],
  };

  for (const fmt of ["shodh", "mem0", "generic", "markdown"] as const) {
    const serialized = dump(doc, fmt);
    const restored = load(serialized, fmt);
    assert(restored.memories[0].content.length === 100_000, `large content ${fmt}: 100K chars preserved`);
  }
}

// -- Empty memories array --
console.log("\n--- Empty memories ---");

{
  const doc: MifDocument = { mif_version: "2.0", memories: [] };
  for (const fmt of ["shodh", "mem0", "generic"] as const) {
    const serialized = dump(doc, fmt);
    const restored = load(serialized, fmt);
    assert(restored.memories.length === 0, `empty memories ${fmt}: preserved`);
  }
  // Markdown with no memories produces empty string, which won't auto-detect
  const mdEmpty = dump(doc, "markdown");
  assert(mdEmpty === "", "empty memories markdown: produces empty string");
}

// -- Knowledge graph survives shodh round-trip --
console.log("\n--- Knowledge graph round-trip ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t" }],
    knowledge_graph: {
      entities: [
        { id: "e1", name: "Rust", types: ["technology"], attributes: { lang: "systems" }, summary: "A language", created_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-03-01T00:00:00Z" },
        { id: "e2", name: "RocksDB", types: ["database"] },
      ],
      relationships: [
        { id: "r1", source_entity_id: "e1", target_entity_id: "e2", relation_type: "uses", context: "storage", confidence: 0.95, created_at: "2026-01-01T00:00:00Z", invalidated_at: null },
      ],
    },
  };
  const serialized = dump(doc, "shodh");
  const restored = load(serialized, "shodh");
  assert(restored.knowledge_graph != null, "kg round-trip: knowledge_graph present");
  assert(restored.knowledge_graph!.entities?.length === 2, "kg round-trip: 2 entities");
  assert(restored.knowledge_graph!.relationships?.length === 1, "kg round-trip: 1 relationship");
  assert(restored.knowledge_graph!.entities![0].name === "Rust", "kg round-trip: entity name preserved");
  assert(restored.knowledge_graph!.entities![0].types?.[0] === "technology", "kg round-trip: entity types preserved");
  assert(restored.knowledge_graph!.entities![0].attributes?.lang === "systems", "kg round-trip: entity attributes preserved");
  assert(restored.knowledge_graph!.entities![0].summary === "A language", "kg round-trip: entity summary preserved");
  assert(restored.knowledge_graph!.relationships![0].relation_type === "uses", "kg round-trip: relationship type preserved");
  assert(restored.knowledge_graph!.relationships![0].confidence === 0.95, "kg round-trip: relationship confidence preserved");
  assert(restored.knowledge_graph!.relationships![0].invalidated_at === null, "kg round-trip: invalidated_at null preserved");
}

// -- vendor_extensions preserved --
console.log("\n--- vendor_extensions ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t" }],
    vendor_extensions: {
      "shodh-memory": { hebbian_rate: 0.1, tiers: ["Working", "Session", "LongTerm"] },
      "custom-vendor": { flag: true, count: 42 },
    },
  };
  const serialized = dump(doc, "shodh");
  const restored = load(serialized, "shodh");
  assert(restored.vendor_extensions != null, "vendor_extensions: present after round-trip");
  assert((restored.vendor_extensions as any)["shodh-memory"].hebbian_rate === 0.1, "vendor_extensions: shodh-memory data preserved");
  assert((restored.vendor_extensions as any)["custom-vendor"].flag === true, "vendor_extensions: custom vendor data preserved");
}

// -- export_meta preserved --
console.log("\n--- export_meta ---");

{
  const doc: MifDocument = {
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t" }],
    export_meta: {
      id: "export-1",
      created_at: "2026-03-01T00:00:00Z",
      user_id: "dev-1",
      checksum: "sha256:abc123",
      privacy: { pii_detected: false, redacted_fields: [] },
    },
  };
  const serialized = dump(doc, "shodh");
  const restored = load(serialized, "shodh");
  assert(restored.export_meta != null, "export_meta: present after round-trip");
  assert((restored.export_meta as any).user_id === "dev-1", "export_meta: user_id preserved");
  assert((restored.export_meta as any).checksum === "sha256:abc123", "export_meta: checksum preserved");
  assert((restored.export_meta as any).privacy?.pii_detected === false, "export_meta: nested privacy preserved");
}

// -- Timestamps with timezone offsets --
console.log("\n--- Timezone handling ---");

{
  const offsets = [
    "2026-01-15T10:30:00+05:30",
    "2026-01-15T10:30:00-08:00",
    "2026-01-15T10:30:00Z",
    "2026-01-15T10:30:00.000Z",
    "2026-06-15",
  ];
  for (const ts of offsets) {
    const data = JSON.stringify([{ content: "tz test", created_at: ts }]);
    const doc = load(data, "generic");
    const parsed = new Date(doc.memories[0].created_at);
    assert(!isNaN(parsed.getTime()), `timezone: '${ts}' parsed to valid date`);
  }
}

// -- All optional Memory fields survive shodh round-trip --
console.log("\n--- All optional fields shodh round-trip ---");

{
  const fullMemory: Memory = {
    id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    content: "full memory with all fields",
    created_at: "2026-01-15T10:30:00Z",
    memory_type: "decision",
    updated_at: "2026-02-01T12:00:00Z",
    tags: ["tag1", "tag2", "tag3"],
    entities: [
      { name: "Entity1", entity_type: "concept", confidence: 0.9 },
      { name: "Entity2", entity_type: "person" },
    ],
    metadata: { importance: 0.85, access_count: 12, custom: "value" },
    embeddings: { model: "minilm-l6-v2", dimensions: 384, vector: [0.1, -0.2, 0.3], normalized: true },
    source: { source_type: "user", session_id: "session-42", agent_name: "claude" },
    parent_id: null,
    related_memory_ids: ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"],
    agent_id: "agent-007",
    external_id: "ext:abc123",
    version: 2,
  };

  const doc: MifDocument = { mif_version: "2.0", memories: [fullMemory] };
  const serialized = dump(doc, "shodh");
  const restored = load(serialized, "shodh");
  const m = restored.memories[0];

  assert(m.id === fullMemory.id, "full shodh rt: id preserved");
  assert(m.content === fullMemory.content, "full shodh rt: content preserved");
  assert(m.created_at === fullMemory.created_at, "full shodh rt: created_at preserved");
  assert(m.memory_type === fullMemory.memory_type, "full shodh rt: memory_type preserved");
  assert(m.updated_at === fullMemory.updated_at, "full shodh rt: updated_at preserved");
  assertDeepEqual(m.tags, fullMemory.tags, "full shodh rt: tags preserved");
  assert(m.entities?.length === 2, "full shodh rt: entities count preserved");
  assert(m.entities?.[0].name === "Entity1", "full shodh rt: entity name preserved");
  assert(m.entities?.[0].confidence === 0.9, "full shodh rt: entity confidence preserved");
  assert((m.metadata as any)?.importance === 0.85, "full shodh rt: metadata preserved");
  assert(m.embeddings?.model === "minilm-l6-v2", "full shodh rt: embeddings model preserved");
  assert(m.embeddings?.dimensions === 384, "full shodh rt: embeddings dimensions preserved");
  assertDeepEqual(m.embeddings?.vector, [0.1, -0.2, 0.3], "full shodh rt: embeddings vector preserved");
  assert(m.embeddings?.normalized === true, "full shodh rt: embeddings normalized preserved");
  assert(m.source?.source_type === "user", "full shodh rt: source type preserved");
  assert(m.source?.session_id === "session-42", "full shodh rt: source session_id preserved");
  assert(m.parent_id === null, "full shodh rt: parent_id null preserved");
  assertDeepEqual(m.related_memory_ids, ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"], "full shodh rt: related_memory_ids preserved");
  assert(m.agent_id === "agent-007", "full shodh rt: agent_id preserved");
  assert(m.external_id === "ext:abc123", "full shodh rt: external_id preserved");
  assert(m.version === 2, "full shodh rt: version preserved");
}

// -- Content with special characters --
console.log("\n--- Special characters ---");

{
  const specials = [
    'Content with "double quotes" inside',
    "Content with 'single quotes' inside",
    "Content with\nnewlines\ninside",
    "Content with\ttabs\tinside",
    "Content with backslash \\ inside",
    "Content with --- markdown delimiters",
  ];

  for (const content of specials) {
    for (const fmt of ["shodh", "mem0", "generic"] as const) {
      const doc: MifDocument = {
        mif_version: "2.0",
        memories: [{ id: "11111111-1111-1111-1111-111111111111", content, created_at: "2026-01-01T00:00:00Z" }],
      };
      const serialized = dump(doc, fmt);
      const restored = load(serialized, fmt);
      assert(restored.memories[0].content === content, `special chars ${fmt}: '${content.substring(0, 30)}...'`);
    }
  }
}

// -- Adapter name() and formatId() consistency --
console.log("\n--- Adapter method consistency ---");

{
  const adapters = [new ShodhAdapter(), new Mem0Adapter(), new GenericJsonAdapter(), new MarkdownAdapter()];
  for (const a of adapters) {
    assert(typeof a.name() === "string" && a.name().length > 0, `${a.formatId()}: name() returns non-empty string`);
    assert(typeof a.formatId() === "string" && a.formatId().length > 0, `${a.formatId()}: formatId() returns non-empty string`);
  }
}

// ===================================================================
// FULL EXAMPLE FILE TEST
// ===================================================================
console.log("\n=== Full Example File Test ===");

const examplePath = path.resolve(__dirname, "../../examples/full.mif.json");
if (fs.existsSync(examplePath)) {
  const fullData = fs.readFileSync(examplePath, "utf-8");

  // Load and validate structure
  const fullDoc = load(fullData);
  assert(fullDoc.mif_version === "2.0", "full example: mif_version is 2.0");
  assert(fullDoc.memories.length === 3, "full example: 3 memories");
  assert(fullDoc.generator?.name === "shodh-memory", "full example: generator is shodh-memory");
  assert(fullDoc.generator?.version === "0.1.80", "full example: generator version 0.1.80");
  assert(fullDoc.knowledge_graph != null, "full example: has knowledge graph");
  assert(fullDoc.knowledge_graph!.entities?.length === 2, "full example: 2 graph entities");
  assert(fullDoc.knowledge_graph!.relationships?.length === 1, "full example: 1 graph relationship");
  assert(fullDoc.vendor_extensions != null, "full example: has vendor_extensions");
  assert(fullDoc.export_meta != null, "full example: has export_meta");

  // Validate specific memory fields
  const m0 = fullDoc.memories[0];
  assert(m0.id === "123e4567-e89b-12d3-a456-426614174000", "full example: memory 0 id");
  assert(m0.memory_type === "decision", "full example: memory 0 type");
  assert(m0.entities?.length === 1, "full example: memory 0 entities");
  assert(m0.embeddings?.model === "minilm-l6-v2", "full example: memory 0 embeddings model");
  assert(m0.embeddings?.dimensions === 384, "full example: memory 0 embeddings dimensions");
  assert(m0.source?.agent_name === "claude-code", "full example: memory 0 source agent");

  const m1 = fullDoc.memories[1];
  assert(m1.agent_id === "claude-code-prod", "full example: memory 1 agent_id");
  assert(m1.external_id === "mem0:abc123def456", "full example: memory 1 external_id");
  assert(m1.updated_at === "2026-02-15T11:00:00Z", "full example: memory 1 updated_at");

  const m2 = fullDoc.memories[2];
  assert(m2.related_memory_ids?.length === 1, "full example: memory 2 related_memory_ids");

  // Round-trip through all formats
  for (const fmt of ["shodh", "mem0", "generic", "markdown"] as const) {
    const out = dump(fullDoc, fmt);
    const rt = load(out, fmt);
    assert(rt.memories.length === fullDoc.memories.length, `full example ${fmt} round-trip: count preserved`);
    assert(rt.memories[0].content === fullDoc.memories[0].content, `full example ${fmt} round-trip: content preserved`);
  }

  // Shodh round-trip preserves knowledge_graph and vendor_extensions
  {
    const shodhRt = load(dump(fullDoc, "shodh"), "shodh");
    assert(shodhRt.knowledge_graph?.entities?.length === 2, "full example shodh rt: knowledge_graph entities");
    assert(shodhRt.vendor_extensions != null, "full example shodh rt: vendor_extensions");
    assert((shodhRt.vendor_extensions as any)["shodh-memory"] != null, "full example shodh rt: shodh-memory extension");
  }

} else {
  console.log("  SKIP: examples/full.mif.json not found at", examplePath);
}

// ===================================================================
// EDGE CASES
// ===================================================================
console.log("\n=== Edge Cases ===");

// -- Shodh v2 with extra top-level fields --
{
  const data = JSON.stringify({
    mif_version: "2.0",
    memories: [{ id: "id", content: "c", created_at: "t" }],
    custom_field: "should survive",
  });
  const doc = load(data, "shodh");
  assert((doc as any).custom_field === "should survive", "edge: extra top-level fields pass through shodh");
}

// -- mem0 with no metadata --
{
  const data = JSON.stringify([{ memory: "no meta" }]);
  const doc = load(data, "mem0");
  assert(doc.memories[0].content === "no meta", "edge: mem0 item with no metadata");
  assertDeepEqual(doc.memories[0].metadata, {}, "edge: mem0 no metadata creates empty object");
  assertDeepEqual(doc.memories[0].tags, [], "edge: mem0 no tags creates empty array");
}

// -- Generic JSON with numeric tags --
{
  const data = JSON.stringify([{ content: "num tags", tags: [1, 2, 3] }]);
  const doc = load(data, "generic");
  assertDeepEqual(doc.memories[0].tags, ["1", "2", "3"], "edge: numeric tags converted to strings");
}

// -- Markdown with id in frontmatter (valid UUID) --
{
  const input = "---\nid: 11111111-2222-3333-4444-555555555555\ntype: error\n---\nWith UUID id\n";
  const doc = load(input, "markdown");
  assert(doc.memories[0].id === "11111111-2222-3333-4444-555555555555", "edge: markdown preserves valid UUID from frontmatter");
}

// -- Markdown with non-UUID id in frontmatter --
{
  const input = "---\nid: not-a-uuid\ntype: observation\n---\nWith bad id\n";
  const doc = load(input, "markdown");
  assert(doc.memories[0].id !== "not-a-uuid", "edge: markdown replaces non-UUID id");
  assert(doc.memories[0].id.length === 36, "edge: markdown generates valid UUID for non-UUID id");
}

// -- Single-item arrays --
{
  const singleMem0 = JSON.stringify([{ memory: "solo" }]);
  assert(load(singleMem0, "mem0").memories.length === 1, "edge: single-item mem0 array");

  const singleGeneric = JSON.stringify([{ content: "solo" }]);
  assert(load(singleGeneric, "generic").memories.length === 1, "edge: single-item generic array");
}

// -- Empty string input to detect --
{
  assert(!shodh.detect(""), "edge: shodh detect empty string");
  assert(!mem0.detect(""), "edge: mem0 detect empty string");
  assert(!generic.detect(""), "edge: generic detect empty string");
  assert(!md.detect(""), "edge: markdown detect empty string");
}

// -- Whitespace-only to detect --
{
  assert(!shodh.detect("   \n\t  "), "edge: shodh detect whitespace-only");
  assert(!mem0.detect("   \n\t  "), "edge: mem0 detect whitespace-only");
  assert(!generic.detect("   \n\t  "), "edge: generic detect whitespace-only");
  assert(!md.detect("   \n\t  "), "edge: markdown detect whitespace-only");
}

// -- v1 shodh with no memories array --
{
  const v1NoMem = JSON.stringify({ mif_version: "1.0" });
  const doc = load(v1NoMem, "shodh");
  assert(doc.memories.length === 0, "edge: v1 with no memories array produces 0 memories");
}

// -- mem0 detect specificity: array with both memory and mif_version --
{
  const ambiguous = JSON.stringify([{ memory: "hi", mif_version: "2.0" }]);
  assert(!mem0.detect(ambiguous), "edge: mem0 detect rejects array with mif_version field");
}

// -- Generator field in v1 shodh conversion --
{
  const v1NoVersion = JSON.stringify({ mif_version: "1", memories: [{ content: "x" }] });
  const doc = load(v1NoVersion, "shodh");
  assert(doc.generator?.version === "1", "edge: v1 generator version from source mif_version");
}

// ===================================================================
// Summary
// ===================================================================
console.log(`\n${"=".repeat(60)}`);
console.log(`TOTAL: ${passed + failed} tests | PASSED: ${passed} | FAILED: ${failed}`);
console.log(`${"=".repeat(60)}`);
if (failed > 0) process.exit(1);
