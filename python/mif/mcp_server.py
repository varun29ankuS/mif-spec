"""MIF MCP Server — expose MIF tools via Model Context Protocol."""

from __future__ import annotations

import json

from mif.registry import AdapterRegistry, load, dump, validate, validate_deep

_registry = AdapterRegistry()


def create_server():
    """Create and return a FastMCP server with MIF tools."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "MIF Tools",
        description="Memory Interchange Format — convert, validate, and inspect AI agent memories",
    )

    @mcp.tool()
    def export_memories(
        data: str,
        from_format: str | None = None,
    ) -> str:
        """Convert memories from any supported format to MIF v2 JSON.

        Args:
            data: Input data string (JSON, markdown, etc.)
            from_format: Source format ID (auto-detected if omitted).
                         Options: shodh, mem0, crewai, langchain, generic, markdown
        """
        doc = load(data, format=from_format)
        return dump(doc, format="shodh")

    @mcp.tool()
    def import_memories(
        data: str,
        to_format: str = "shodh",
    ) -> str:
        """Convert MIF v2 JSON to a target format.

        Args:
            data: MIF v2 JSON string
            to_format: Target format ID.
                       Options: shodh, mem0, crewai, langchain, generic, markdown
        """
        doc = load(data, format="shodh")
        return dump(doc, format=to_format)

    @mcp.tool()
    def validate_memories(data: str) -> str:
        """Validate a MIF JSON document against the schema and run semantic checks.

        Args:
            data: MIF JSON string to validate

        Returns:
            JSON object with validation results
        """
        schema_ok, schema_errors = validate(data)
        if not schema_ok:
            return json.dumps({
                "valid": False,
                "schema_errors": schema_errors,
            }, indent=2)

        deep_ok, deep_warnings = validate_deep(data)
        doc = load(data)
        return json.dumps({
            "valid": True,
            "schema_valid": True,
            "semantic_valid": deep_ok,
            "semantic_warnings": deep_warnings,
            "summary": {
                "memories": len(doc.memories),
                "has_graph": doc.knowledge_graph is not None,
                "has_extensions": bool(doc.vendor_extensions),
            },
        }, indent=2)

    @mcp.tool()
    def list_formats() -> str:
        """List all available memory format adapters.

        Returns:
            JSON array of format objects with name and format_id
        """
        formats = _registry.list_formats()
        return json.dumps(formats, indent=2)

    @mcp.tool()
    def inspect_memories(
        data: str,
        from_format: str | None = None,
    ) -> str:
        """Show a summary of a memory file.

        Args:
            data: Input data string
            from_format: Source format ID (auto-detected if omitted)
        """
        doc = load(data, format=from_format)

        types: dict[str, int] = {}
        all_tags: set[str] = set()
        for m in doc.memories:
            types[m.memory_type] = types.get(m.memory_type, 0) + 1
            all_tags.update(m.tags)

        result = {
            "mif_version": doc.mif_version,
            "memory_count": len(doc.memories),
            "types": types,
            "tags": sorted(all_tags),
            "has_graph": doc.knowledge_graph is not None,
            "has_extensions": bool(doc.vendor_extensions),
        }
        if doc.generator:
            result["generator"] = doc.generator

        return json.dumps(result, indent=2)

    return mcp


def main():
    """Run the MIF MCP server."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
