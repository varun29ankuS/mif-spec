---
layout: default
title: MCP Server
nav_order: 6
---

# MIF MCP Server

The MIF MCP server exposes memory conversion and validation tools via the [Model Context Protocol](https://modelcontextprotocol.io), making MIF accessible to any MCP-compatible AI client.

---

## Installation

```bash
pip install mif-tools[mcp]
```

## Starting the Server

```bash
mif mcp
```

Or programmatically:

```python
from mif.mcp_server import create_server

server = create_server()
server.run()
```

## Available Tools

### `export_memories`

Convert memories from any supported format to MIF v2 JSON.

**Parameters:**
- `data` (string, required) — Input data string
- `from_format` (string, optional) — Source format ID. Auto-detected if omitted.

**Returns:** MIF v2 JSON string.

### `import_memories`

Convert MIF v2 JSON to a target format.

**Parameters:**
- `data` (string, required) — MIF v2 JSON string
- `to_format` (string, optional) — Target format ID. Default: `shodh`

**Returns:** Converted string in the target format.

### `validate_memories`

Validate a MIF JSON document against the schema and run semantic checks.

**Parameters:**
- `data` (string, required) — MIF JSON string

**Returns:** JSON object with validation results:

```json
{
  "valid": true,
  "schema_valid": true,
  "semantic_valid": true,
  "semantic_warnings": [],
  "summary": {
    "memories": 42,
    "has_graph": false,
    "has_extensions": false
  }
}
```

### `list_formats`

List all available memory format adapters.

**Returns:** JSON array of format objects.

```json
[
  { "name": "Shodh Memory (MIF v2/v1)", "format_id": "shodh" },
  { "name": "mem0", "format_id": "mem0" },
  { "name": "CrewAI", "format_id": "crewai" },
  { "name": "LangChain", "format_id": "langchain" },
  { "name": "Generic JSON", "format_id": "generic" },
  { "name": "Markdown (YAML frontmatter)", "format_id": "markdown" }
]
```

### `inspect_memories`

Show a summary of a memory file.

**Parameters:**
- `data` (string, required) — Input data string
- `from_format` (string, optional) — Source format ID

**Returns:** JSON summary object.

## MCP Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mif": {
      "command": "mif",
      "args": ["mcp"]
    }
  }
}
```

### Claude Code

Add to your MCP settings:

```json
{
  "mcpServers": {
    "mif": {
      "command": "mif",
      "args": ["mcp"]
    }
  }
}
```
