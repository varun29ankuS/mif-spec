#!/usr/bin/env node

import * as fs from "fs";
import { load, dump, listFormats } from "./index";
import { validate, validateDeep } from "./validate";
import type { MifDocument } from "./models";

const args = process.argv.slice(2);
const command = args[0];

function usage(): void {
  console.log(`mif — Memory Interchange Format tools

Commands:
  convert <input> [options]   Convert between memory formats
  validate <file...>          Validate MIF JSON documents
  inspect <input>             Show summary of a memory file
  formats                     List available formats

Options:
  -f, --from <format>    Source format (auto-detected if omitted)
  -t, --to <format>      Target format (default: shodh)
  -o, --output <file>    Output file (stdout if omitted)

Examples:
  mif convert export.json --from mem0 --to shodh -o memories.mif.json
  mif convert memories.mif.json --to markdown
  mif inspect memories.json
  mif formats`);
}

function getFlag(flag: string, short?: string): string | undefined {
  for (let i = 0; i < args.length; i++) {
    if (args[i] === flag || (short && args[i] === short)) {
      return args[i + 1];
    }
  }
  return undefined;
}

function cmdConvert(): void {
  const input = args[1];
  if (!input) { console.error("Error: input file required"); process.exit(1); }

  const fromFormat = getFlag("--from", "-f");
  const toFormat = getFlag("--to", "-t") || "shodh";
  const output = getFlag("--output", "-o");

  const data = fs.readFileSync(input, "utf-8");
  const doc = load(data, fromFormat);
  const result = dump(doc, toFormat);

  if (output) {
    fs.writeFileSync(output, result, "utf-8");
    console.log(`Converted ${doc.memories.length} memories → ${output} (${toFormat})`);
  } else {
    process.stdout.write(result);
  }
}

function cmdValidate(): void {
  const files = args.slice(1);
  if (!files.length) { console.error("Error: at least one file required"); process.exit(1); }

  let passed = 0;
  for (const filepath of files) {
    try {
      const data = fs.readFileSync(filepath, "utf-8");

      const [schemaOk, schemaErrors] = validate(data);
      if (!schemaOk) {
        console.log(`FAIL ${filepath}: ${schemaErrors.length} error(s)`);
        for (const err of schemaErrors.slice(0, 5)) console.log(`     ${err}`);
        if (schemaErrors.length > 5) console.log(`     ... and ${schemaErrors.length - 5} more`);
        continue;
      }

      const doc = load(data);
      const hasGraph = doc.knowledge_graph != null;
      const hasExt = doc.vendor_extensions && Object.keys(doc.vendor_extensions).length > 0;

      const [deepOk, deepWarnings] = validateDeep(data);
      if (deepOk) {
        console.log(`PASS ${filepath}`);
        console.log(`     ${doc.memories.length} memories, graph=${hasGraph ? "yes" : "no"}, extensions=${hasExt ? "yes" : "no"}`);
      } else {
        console.log(`WARN ${filepath}: schema OK, ${deepWarnings.length} semantic warning(s)`);
        for (const w of deepWarnings.slice(0, 5)) console.log(`     ${w}`);
        if (deepWarnings.length > 5) console.log(`     ... and ${deepWarnings.length - 5} more`);
      }
      passed++;
    } catch (e: any) {
      console.log(`FAIL ${filepath}: ${e.message}`);
    }
  }
  console.log(`\n${passed}/${files.length} files passed validation`);
  if (passed < files.length) process.exit(1);
}

function cmdInspect(): void {
  const input = args[1];
  if (!input) { console.error("Error: input file required"); process.exit(1); }

  const fromFormat = getFlag("--from", "-f");
  const data = fs.readFileSync(input, "utf-8");
  const doc = load(data, fromFormat);

  console.log(`File: ${input}`);
  console.log(`MIF version: ${doc.mif_version}`);
  if (doc.generator) console.log(`Generator: ${doc.generator.name} ${doc.generator.version}`);
  console.log(`Memories: ${doc.memories.length}`);

  if (doc.memories.length > 0) {
    const types: Record<string, number> = {};
    const allTags = new Set<string>();
    for (const m of doc.memories) {
      const t = m.memory_type || "observation";
      types[t] = (types[t] || 0) + 1;
      for (const tag of m.tags || []) allTags.add(tag);
    }
    console.log(`Types: ${Object.entries(types).map(([t, n]) => `${t}(${n})`).join(", ")}`);
    if (allTags.size > 0) console.log(`Tags: ${[...allTags].sort().join(", ")}`);
  }

  if (doc.knowledge_graph) {
    const kg = doc.knowledge_graph;
    console.log(`Graph: ${(kg.entities || []).length} entities, ${(kg.relationships || []).length} relationships`);
  }

  if (doc.vendor_extensions && Object.keys(doc.vendor_extensions).length > 0) {
    console.log(`Extensions: ${Object.keys(doc.vendor_extensions).join(", ")}`);
  }
}

function cmdFormats(): void {
  console.log("Available formats:\n");
  for (const f of listFormats()) {
    console.log(`  ${f.formatId.padEnd(12)}  ${f.name}`);
  }
  console.log("\nUsage:");
  console.log("  mif convert input.json --from mem0 --to shodh -o output.mif.json");
  console.log("  mif convert input.json --to markdown    # auto-detect source");
}

switch (command) {
  case "convert": cmdConvert(); break;
  case "validate": cmdValidate(); break;
  case "inspect": cmdInspect(); break;
  case "formats": cmdFormats(); break;
  default: usage(); if (!command) process.exit(1); break;
}
