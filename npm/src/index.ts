/** MIF (Memory Interchange Format) — vendor-neutral memory portability for AI agents. */

export type {
  MifDocument,
  Memory,
  KnowledgeGraph,
  GraphEntity,
  GraphRelationship,
  EntityReference,
  Embedding,
  Source,
} from "./models";

export { createMemory, createDocument } from "./models";

export type { MifAdapter } from "./adapters";
export {
  ShodhAdapter,
  Mem0Adapter,
  GenericJsonAdapter,
  MarkdownAdapter,
} from "./adapters";

export { validate, validateDeep } from "./validate";

import { createHash } from "crypto";

/**
 * Deduplicate memories by SHA-256 content hash.
 * Per MIF spec section 6, deduplication uses content hash, not UUID collision.
 *
 * @returns `[deduplicatedDoc, duplicatesRemoved]`
 */
export function deduplicate(doc: MifDocument): [MifDocument, number] {
  const seenHashes = new Set<string>();
  const unique: typeof doc.memories = [];

  for (const mem of doc.memories) {
    const hash = createHash("sha256").update(mem.content).digest("hex");
    if (!seenHashes.has(hash)) {
      seenHashes.add(hash);
      unique.push(mem);
    }
  }

  const removed = doc.memories.length - unique.length;
  const deduped: MifDocument = { ...doc, memories: unique };
  return [deduped, removed];
}

import {
  MifAdapter,
  ShodhAdapter,
  Mem0Adapter,
  GenericJsonAdapter,
  MarkdownAdapter,
} from "./adapters";
import { MifDocument } from "./models";

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

const adapters: MifAdapter[] = [
  new ShodhAdapter(),
  new Mem0Adapter(),
  new GenericJsonAdapter(),
  new MarkdownAdapter(),
];

/** Auto-detect format and parse into a MifDocument. */
export function load(data: string, format?: string): MifDocument {
  if (format) {
    const adapter = adapters.find(a => a.formatId() === format);
    if (!adapter) {
      const available = adapters.map(a => a.formatId()).join(", ");
      throw new Error(`Unknown format: '${format}'. Available: ${available}`);
    }
    return adapter.toMif(data);
  }

  for (const adapter of adapters) {
    if (adapter.detect(data)) {
      return adapter.toMif(data);
    }
  }
  throw new Error(
    "Could not auto-detect format. Supported: shodh (MIF JSON), mem0, generic JSON array, markdown."
  );
}

/** Serialize a MifDocument to a string in the given format. */
export function dump(doc: MifDocument, format: string = "shodh"): string {
  const adapter = adapters.find(a => a.formatId() === format);
  if (!adapter) {
    const available = adapters.map(a => a.formatId()).join(", ");
    throw new Error(`Unknown format: '${format}'. Available: ${available}`);
  }
  return adapter.fromMif(doc);
}

/** Convert between formats in one call. */
export function convert(
  data: string,
  options: { fromFormat?: string; toFormat?: string } = {}
): string {
  const doc = load(data, options.fromFormat);
  return dump(doc, options.toFormat || "shodh");
}

/** List available formats. */
export function listFormats(): { name: string; formatId: string }[] {
  return adapters.map(a => ({ name: a.name(), formatId: a.formatId() }));
}
