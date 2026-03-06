---
layout: default
title: npm
nav_order: 5
---

# npm Package

`@varunshodh/mif-tools` — TypeScript/JavaScript library and CLI for MIF.

---

## Installation

```bash
npm install @varunshodh/mif-tools
```

## API Reference

### `load(data, format?) -> MifDocument`

Parse a string into a MifDocument. Auto-detects format unless specified.

```typescript
import { load } from "@varunshodh/mif-tools";

const doc = load(fs.readFileSync("memories.json", "utf-8"));
const doc2 = load(data, "mem0");
```

### `dump(doc, format?) -> string`

Serialize a MifDocument to a string.

```typescript
import { dump } from "@varunshodh/mif-tools";

const json = dump(doc);                     // MIF v2 JSON
const md = dump(doc, "markdown");           // YAML frontmatter markdown
```

### `convert(data, options?) -> string`

Convert between formats in one call.

```typescript
import { convert } from "@varunshodh/mif-tools";

const result = convert(data, { fromFormat: "mem0", toFormat: "markdown" });
```

### `validate(data) -> [boolean, string[]]`

Validate a MIF JSON string against the schema.

```typescript
import { validate } from "@varunshodh/mif-tools";

const [isValid, errors] = validate(jsonString);
```

### `validateDeep(data) -> [boolean, string[]]`

Semantic validation.

```typescript
import { validateDeep } from "@varunshodh/mif-tools";

const [isValid, warnings] = validateDeep(jsonString);
```

### `deduplicate(doc) -> [MifDocument, number]`

Deduplicate memories by SHA-256 content hash.

```typescript
import { deduplicate } from "@varunshodh/mif-tools";

const [dedupedDoc, removedCount] = deduplicate(doc);
```

### `AdapterRegistry`

Manage format adapters dynamically.

```typescript
import { AdapterRegistry } from "@varunshodh/mif-tools";

const registry = new AdapterRegistry();
registry.register(myAdapter);      // prepend custom adapter
registry.unregister("myformat");   // remove by format ID
registry.listFormats();            // list all adapters
```

## Models

```typescript
import { createMemory, createDocument } from "@varunshodh/mif-tools";

const memory = createMemory({
  content: "User prefers dark mode",
  memory_type: "observation",
  tags: ["preferences"],
});

const doc = createDocument({ memories: [memory] });
```

## CLI

```bash
npx mif convert export.json --from mem0 --to shodh -o output.mif.json
npx mif validate file1.json file2.json
npx mif inspect memories.json
npx mif formats
```
