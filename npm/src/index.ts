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
  CrewAIAdapter,
  LangChainAdapter,
  GenericJsonAdapter,
  MarkdownAdapter,
} from "./adapters";

export { validate, validateDeep } from "./validate";

import { createHash } from "crypto";
import {
  MifAdapter,
  ShodhAdapter,
  Mem0Adapter,
  CrewAIAdapter,
  LangChainAdapter,
  GenericJsonAdapter,
  MarkdownAdapter,
} from "./adapters";
import { MifDocument } from "./models";

// ---------------------------------------------------------------------------
// AdapterRegistry — matches Python's AdapterRegistry class
// ---------------------------------------------------------------------------

/**
 * Registry of format adapters with auto-detection.
 *
 * Detection order (most specific first):
 * 1. Shodh (MIF v2/v1) — has mif_version or shodh-memory marker
 * 2. mem0 — JSON array with "memory" field
 * 3. Generic JSON — JSON array with "content" field
 * 4. Markdown — starts with "---"
 */
export class AdapterRegistry {
  adapters: MifAdapter[];

  constructor() {
    this.adapters = [
      new ShodhAdapter(),
      new Mem0Adapter(),
      new CrewAIAdapter(),
      new LangChainAdapter(),
      new GenericJsonAdapter(),
      new MarkdownAdapter(),
    ];
  }

  /** Find the first adapter that detects the format. */
  autoDetect(data: string): MifAdapter | null {
    for (const adapter of this.adapters) {
      if (adapter.detect(data)) return adapter;
    }
    return null;
  }

  /** Get adapter by format ID. */
  get(formatId: string): MifAdapter | null {
    for (const adapter of this.adapters) {
      if (adapter.formatId() === formatId) return adapter;
    }
    return null;
  }

  /** Register a custom adapter. Prepends to give it higher detection priority. */
  register(adapter: MifAdapter): void {
    this.adapters.unshift(adapter);
  }

  /** Unregister an adapter by format ID. */
  unregister(formatId: string): boolean {
    const idx = this.adapters.findIndex(a => a.formatId() === formatId);
    if (idx === -1) return false;
    this.adapters.splice(idx, 1);
    return true;
  }

  /** List all available adapters. */
  listFormats(): { name: string; formatId: string }[] {
    return this.adapters.map(a => ({ name: a.name(), formatId: a.formatId() }));
  }
}

// Module-level registry
const _registry = new AdapterRegistry();

/** Auto-detect format and parse into a MifDocument. */
export function load(data: string, format?: string): MifDocument {
  if (format) {
    const adapter = _registry.get(format);
    if (!adapter) {
      const available = _registry.adapters.map(a => a.formatId()).join(", ");
      throw new Error(`Unknown format: '${format}'. Available: ${available}`);
    }
    return adapter.toMif(data);
  }

  const adapter = _registry.autoDetect(data);
  if (!adapter) {
    throw new Error(
      "Could not auto-detect format. Supported: shodh (MIF JSON), mem0, generic JSON array, markdown."
    );
  }
  return adapter.toMif(data);
}

/** Serialize a MifDocument to a string in the given format. */
export function dump(doc: MifDocument, format: string = "shodh"): string {
  const adapter = _registry.get(format);
  if (!adapter) {
    const available = _registry.adapters.map(a => a.formatId()).join(", ");
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
  return _registry.listFormats();
}

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
