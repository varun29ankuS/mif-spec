/** Format adapters: convert between external memory formats and MIF v2. */

import { randomUUID } from "crypto";
import { MifDocument, Memory, Source } from "./models";

// ---------------------------------------------------------------------------
// Adapter interface
// ---------------------------------------------------------------------------

export interface MifAdapter {
  name(): string;
  formatId(): string;
  detect(data: string): boolean;
  toMif(data: string): MifDocument;
  fromMif(doc: MifDocument): string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function ensureUuid(s?: string | null): string {
  if (s && UUID_RE.test(s)) return s;
  return randomUUID();
}

function parseDate(s?: string | null): string {
  if (!s) return new Date().toISOString();
  try {
    const d = new Date(s);
    if (!isNaN(d.getTime())) return d.toISOString();
  } catch {}
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Shodh adapter (MIF v2 native + v1 backward compat)
// ---------------------------------------------------------------------------

export class ShodhAdapter implements MifAdapter {
  name() { return "Shodh Memory (MIF v2/v1)"; }
  formatId() { return "shodh"; }

  detect(data: string): boolean {
    const t = data.trimStart();
    if (!t.startsWith("{")) return false;
    return t.includes('"mif_version"') || t.includes('"shodh-memory"');
  }

  toMif(data: string): MifDocument {
    const parsed = JSON.parse(data);
    const version = parsed.mif_version || "";

    if (version === "1" || version.startsWith("1.")) {
      return this.convertV1(parsed);
    }
    // v2 or treat as v2
    if (!parsed.mif_version) parsed.mif_version = "2.0";
    if (!Array.isArray(parsed.memories)) parsed.memories = [];
    return parsed as MifDocument;
  }

  private convertV1(v1: any): MifDocument {
    const memories: Memory[] = [];
    for (const m of v1.memories || []) {
      if (!m.content) continue;
      const rawId: string = m.id || "";
      const id = ensureUuid(rawId.replace(/^mem_/, ""));
      const memoryType = (m.type || m.memory_type || "observation").toLowerCase();
      memories.push({
        id,
        content: m.content,
        memory_type: memoryType,
        created_at: parseDate(m.created_at),
        tags: m.tags || [],
      });
    }
    return {
      mif_version: "2.0",
      memories,
      generator: { name: "shodh-memory-v1-import", version: v1.mif_version || "1.0" },
    };
  }

  fromMif(doc: MifDocument): string {
    return JSON.stringify(doc, null, 2);
  }
}

// ---------------------------------------------------------------------------
// mem0 adapter
// ---------------------------------------------------------------------------

export class Mem0Adapter implements MifAdapter {
  name() { return "mem0"; }
  formatId() { return "mem0"; }

  detect(data: string): boolean {
    const t = data.trimStart();
    if (!t.startsWith("[")) return false;
    return t.includes('"memory"') && !t.includes('"mif_version"');
  }

  toMif(data: string): MifDocument {
    const items: any[] = JSON.parse(data);
    const memories: Memory[] = [];
    let userId = "";

    const typeMap: Record<string, string> = {
      preference: "observation", preferences: "observation",
      decision: "decision", learning: "learning", fact: "learning",
      error: "error", mistake: "error", task: "task", todo: "task",
    };

    for (const item of items) {
      const memoryText = item.memory;
      if (!memoryText) continue;

      if (!userId && item.user_id) userId = item.user_id;

      const metadata: Record<string, unknown> = {};
      if (item.metadata && typeof item.metadata === "object") {
        for (const [k, v] of Object.entries(item.metadata)) {
          metadata[k] = v;
        }
      }

      const category = (typeof metadata.category === "string" ? metadata.category : "") as string;
      const memoryType = typeMap[category] || "observation";

      const rawTags = metadata.tags;
      const tags: string[] = typeof rawTags === "string"
        ? rawTags.split(",").map((t: string) => t.trim()).filter(Boolean)
        : Array.isArray(rawTags)
          ? rawTags.map(String)
          : [];

      memories.push({
        id: ensureUuid(item.id),
        content: memoryText,
        memory_type: memoryType,
        created_at: parseDate(item.created_at),
        tags,
        metadata,
        source: { source_type: "mem0" },
        agent_id: item.agent_id || undefined,
        external_id: item.id || undefined,
      });
    }

    const doc: MifDocument = {
      mif_version: "2.0",
      memories,
      generator: { name: "mem0-import", version: "1.0" },
    };
    if (userId) {
      doc.export_meta = { user_id: userId };
    }
    return doc;
  }

  fromMif(doc: MifDocument): string {
    const userId = (doc.export_meta as any)?.user_id || "";
    const items = doc.memories.map(m => {
      const obj: any = {
        id: m.id,
        memory: m.content,
        created_at: m.created_at,
        updated_at: m.updated_at || m.created_at,
      };
      if (userId) obj.user_id = userId;
      if (m.metadata && Object.keys(m.metadata).length > 0) obj.metadata = m.metadata;
      return obj;
    });
    return JSON.stringify(items, null, 2);
  }
}

// ---------------------------------------------------------------------------
// Generic JSON adapter
// ---------------------------------------------------------------------------

export class GenericJsonAdapter implements MifAdapter {
  name() { return "Generic JSON"; }
  formatId() { return "generic"; }

  detect(data: string): boolean {
    const t = data.trimStart();
    return t.startsWith("[") && t.includes('"content"');
  }

  toMif(data: string): MifDocument {
    const items: any[] = JSON.parse(data);
    const memories: Memory[] = [];

    for (const item of items) {
      const content = item.content;
      if (!content) continue;

      const memoryType = (item.type || item.memory_type || "observation").toLowerCase();
      const created_at = parseDate(item.timestamp || item.created_at || item.date);
      const tags: string[] = Array.isArray(item.tags) ? item.tags.map(String) : [];

      const metadata: Record<string, unknown> = {};
      if (item.metadata && typeof item.metadata === "object") {
        for (const [k, v] of Object.entries(item.metadata)) {
          metadata[k] = v;
        }
      }

      memories.push({
        id: ensureUuid(item.id),
        content,
        memory_type: memoryType,
        created_at,
        tags,
        metadata,
        source: { source_type: "generic_json" },
        external_id: item.id || undefined,
      });
    }

    return {
      mif_version: "2.0",
      memories,
      generator: { name: "generic-json-import", version: "1.0" },
    };
  }

  fromMif(doc: MifDocument): string {
    const items = doc.memories.map(m => {
      const obj: any = {
        id: m.id,
        content: m.content,
        type: m.memory_type || "observation",
        timestamp: m.created_at,
      };
      if (m.tags && m.tags.length > 0) obj.tags = m.tags;
      if (m.metadata && Object.keys(m.metadata).length > 0) obj.metadata = m.metadata;
      return obj;
    });
    return JSON.stringify(items, null, 2);
  }
}

// ---------------------------------------------------------------------------
// Markdown adapter (YAML frontmatter)
// ---------------------------------------------------------------------------

export class MarkdownAdapter implements MifAdapter {
  name() { return "Markdown (YAML frontmatter)"; }
  formatId() { return "markdown"; }

  detect(data: string): boolean {
    return data.trimStart().startsWith("---");
  }

  toMif(data: string): MifDocument {
    const blocks = splitFrontmatterBlocks(data);
    const memories: Memory[] = [];

    for (const [frontmatter, body] of blocks) {
      const content = body.trim().replace(/\\---/g, "---");
      if (!content) continue;

      const fm = parseFrontmatter(frontmatter);
      const id = ensureUuid(fm.id);
      const memoryType = fm.type || "observation";
      const created_at = parseDate(fm.created_at || fm.date);

      let tags: string[] = [];
      if (fm.tags) {
        const cleaned = fm.tags.replace(/^\[/, "").replace(/\]$/, "");
        tags = cleaned.split(",").map(t => t.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean);
      }

      const reserved = new Set(["type", "tags", "created_at", "date", "id"]);
      const metadata: Record<string, string> = {};
      for (const [k, v] of Object.entries(fm)) {
        if (!reserved.has(k)) metadata[k] = v;
      }

      memories.push({
        id,
        content,
        memory_type: memoryType,
        created_at,
        tags,
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
        source: { source_type: "markdown" },
      });
    }

    return {
      mif_version: "2.0",
      memories,
      generator: { name: "markdown-import", version: "1.0" },
    };
  }

  fromMif(doc: MifDocument): string {
    const parts: string[] = [];
    for (const m of doc.memories) {
      let block = "---\n";
      block += `id: ${m.id}\n`;
      block += `type: ${m.memory_type || "observation"}\n`;
      block += `created_at: ${m.created_at}\n`;
      if (m.tags && m.tags.length > 0) {
        const quoted = m.tags.map(t => t.includes(",") ? `"${t}"` : t);
        block += `tags: [${quoted.join(", ")}]\n`;
      }
      block += "---\n";
      const escaped = m.content.split("\n").map(line => line.trim() === "---" ? "\\---" : line).join("\n");
      block += escaped + "\n";
      parts.push(block);
    }
    return parts.join("\n");
  }
}

// ---------------------------------------------------------------------------
// Markdown helpers
// ---------------------------------------------------------------------------

function splitFrontmatterBlocks(text: string): [string, string][] {
  const blocks: [string, string][] = [];
  const lines = text.split("\n");
  if (!lines.length || lines[0].trim() !== "---") return blocks;

  let i = 0;
  while (i < lines.length) {
    if (lines[i].trim() !== "---") { i++; continue; }
    i++; // skip opening ---

    const fmLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "---") {
      fmLines.push(lines[i]);
      i++;
    }
    if (i < lines.length) i++; // skip closing ---

    const bodyLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "---") {
      bodyLines.push(lines[i]);
      i++;
    }

    const fm = fmLines.join("\n");
    const body = bodyLines.join("\n");
    if (fm || body) blocks.push([fm, body]);
  }

  return blocks;
}

function parseFrontmatter(fm: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of fm.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const pos = trimmed.indexOf(":");
    if (pos > 0) {
      const key = trimmed.substring(0, pos).trim();
      const value = trimmed.substring(pos + 1).trim();
      if (key) result[key] = value;
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// CrewAI adapter (LTMSQLiteStorage JSON export)
// ---------------------------------------------------------------------------

export class CrewAIAdapter implements MifAdapter {
  name() { return "CrewAI"; }
  formatId() { return "crewai"; }

  detect(data: string): boolean {
    const t = data.trimStart();
    if (!t.startsWith("[")) return false;
    return t.includes('"task_description"');
  }

  toMif(data: string): MifDocument {
    const items: any[] = JSON.parse(data);
    const memories: Memory[] = [];

    for (const item of items) {
      const content = item.task_description;
      if (!content) continue;

      // Parse metadata (may be JSON string or object)
      let metadata: Record<string, unknown> = {};
      const rawMeta = item.metadata;
      if (typeof rawMeta === "string") {
        try { metadata = JSON.parse(rawMeta); } catch { metadata = { raw: rawMeta }; }
      } else if (rawMeta && typeof rawMeta === "object") {
        metadata = { ...rawMeta };
      }

      // Parse datetime (Unix timestamp string or ISO)
      let created_at: string;
      const rawDt = item.datetime;
      if (rawDt) {
        const ts = parseFloat(rawDt);
        if (!isNaN(ts)) {
          created_at = new Date(ts * 1000).toISOString();
        } else {
          created_at = parseDate(String(rawDt));
        }
      } else {
        created_at = parseDate(null);
      }

      // Preserve score in metadata
      if (item.score != null) {
        metadata.score = item.score;
      }

      memories.push({
        id: ensureUuid(),
        content,
        memory_type: "observation",
        created_at,
        metadata,
        source: { source_type: "crewai" },
      });
    }

    return {
      mif_version: "2.0",
      memories,
      generator: { name: "crewai-import", version: "1.0" },
    };
  }

  fromMif(doc: MifDocument): string {
    const items = doc.memories.map(m => {
      const meta = { ...(m.metadata || {}) };
      const score = meta.score;
      delete meta.score;

      const obj: any = {
        task_description: m.content,
        metadata: JSON.stringify(meta),
        datetime: String(new Date(m.created_at).getTime() / 1000),
      };
      if (score != null) obj.score = score;
      return obj;
    });
    return JSON.stringify(items, null, 2);
  }
}

// ---------------------------------------------------------------------------
// LangChain / LangMem adapter
// ---------------------------------------------------------------------------

export class LangChainAdapter implements MifAdapter {
  name() { return "LangChain"; }
  formatId() { return "langchain"; }

  detect(data: string): boolean {
    const t = data.trimStart();
    if (!t.startsWith("[")) return false;
    return t.includes('"namespace"') && t.includes('"value"');
  }

  toMif(data: string): MifDocument {
    const items: any[] = JSON.parse(data);
    const memories: Memory[] = [];

    const typeMap: Record<string, string> = {
      memory: "observation",
      fact: "learning",
      preference: "observation",
      note: "observation",
    };

    for (const item of items) {
      const value = item.value;
      let content: string;
      let kind = "";

      if (typeof value === "string") {
        content = value;
      } else if (value && typeof value === "object") {
        content = value.content || "";
        kind = value.kind || "";
      } else {
        continue;
      }

      if (!content) continue;

      const rawType = kind.toLowerCase() || "observation";
      const memoryType = typeMap[rawType] || rawType || "observation";

      // Namespace → tags
      const namespace = item.namespace;
      const tags: string[] = Array.isArray(namespace) ? namespace.map(String) : [];

      // Metadata
      const metadata: Record<string, unknown> = {};
      if (item.score != null) metadata.score = item.score;

      memories.push({
        id: ensureUuid(),
        content,
        memory_type: memoryType,
        created_at: parseDate(item.created_at),
        updated_at: item.updated_at ? parseDate(item.updated_at) : undefined,
        tags,
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
        source: { source_type: "langchain" },
        external_id: item.key || undefined,
      });
    }

    return {
      mif_version: "2.0",
      memories,
      generator: { name: "langchain-import", version: "1.0" },
    };
  }

  fromMif(doc: MifDocument): string {
    const items = doc.memories.map(m => {
      const meta = { ...(m.metadata || {}) };
      const score = meta.score;
      delete meta.score;

      const kind = (m.memory_type || "observation").charAt(0).toUpperCase()
        + (m.memory_type || "observation").slice(1);

      const obj: any = {
        namespace: m.tags && m.tags.length > 0 ? m.tags : ["memories"],
        key: m.external_id || m.id,
        value: { kind, content: m.content },
        created_at: m.created_at,
      };
      if (m.updated_at) obj.updated_at = m.updated_at;
      if (score != null) obj.score = score;
      return obj;
    });
    return JSON.stringify(items, null, 2);
  }
}
