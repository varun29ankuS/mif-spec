"""MIF (Memory Interchange Format) — vendor-neutral memory portability for AI agents."""

from mif.models import MifDocument, Memory, KnowledgeGraph, GraphEntity, GraphRelationship
from mif.adapters import CrewAIAdapter, LangChainAdapter
from mif.registry import AdapterRegistry, load, dump, convert, validate, validate_deep, deduplicate

__version__ = "0.1.0"
__all__ = [
    "MifDocument",
    "Memory",
    "KnowledgeGraph",
    "GraphEntity",
    "GraphRelationship",
    "CrewAIAdapter",
    "LangChainAdapter",
    "AdapterRegistry",
    "load",
    "dump",
    "convert",
    "validate",
    "validate_deep",
    "deduplicate",
]
