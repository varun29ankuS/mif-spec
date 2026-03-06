/** MIF v2.0 data models. */

import { randomUUID } from "crypto";

export interface EntityReference {
  name: string;
  entity_type?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface Embedding {
  model: string;
  dimensions: number;
  vector: number[];
  normalized?: boolean;
}

export interface Source {
  source_type?: string;
  session_id?: string;
  agent_name?: string;
  [key: string]: unknown;
}

export interface Memory {
  id: string;
  content: string;
  created_at: string;
  memory_type?: string;
  updated_at?: string;
  tags?: string[];
  entities?: EntityReference[];
  metadata?: Record<string, unknown>;
  embeddings?: Embedding;
  source?: Source;
  parent_id?: string | null;
  related_memory_ids?: string[];
  agent_id?: string | null;
  external_id?: string | null;
  version?: number;
  [key: string]: unknown;
}

export interface GraphEntity {
  id: string;
  name: string;
  types?: string[];
  attributes?: Record<string, unknown>;
  summary?: string;
  created_at?: string;
  last_seen_at?: string;
  [key: string]: unknown;
}

export interface GraphRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  context?: string;
  confidence?: number;
  created_at?: string;
  invalidated_at?: string | null;
  [key: string]: unknown;
}

export interface KnowledgeGraph {
  entities?: GraphEntity[];
  relationships?: GraphRelationship[];
  [key: string]: unknown;
}

export interface MifDocument {
  mif_version: string;
  memories: Memory[];
  generator?: { name: string; version: string };
  export_meta?: Record<string, unknown>;
  knowledge_graph?: KnowledgeGraph | null;
  vendor_extensions?: Record<string, unknown>;
  [key: string]: unknown;
}

/** Create a minimal Memory object with defaults. */
export function createMemory(partial: Partial<Memory> & { content: string }): Memory {
  return {
    ...partial,
    id: partial.id || randomUUID(),
    content: partial.content,
    created_at: partial.created_at || new Date().toISOString(),
    memory_type: partial.memory_type || "observation",
  };
}

/** Create a minimal MifDocument. */
export function createDocument(memories: Memory[] = []): MifDocument {
  return {
    mif_version: "2.0",
    memories,
  };
}
