"""CLI for MIF tools."""

import argparse
import sys
from pathlib import Path

from mif.registry import AdapterRegistry, load, dump, validate, validate_deep


def main():
    parser = argparse.ArgumentParser(
        prog="mif",
        description="MIF (Memory Interchange Format) — convert, validate, and inspect AI agent memories.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # convert
    convert_p = subparsers.add_parser("convert", help="Convert between memory formats")
    convert_p.add_argument("input", help="Input file path")
    convert_p.add_argument("-f", "--from", dest="from_format", help="Source format (auto-detected if omitted)")
    convert_p.add_argument("-t", "--to", dest="to_format", default="shodh", help="Target format (default: shodh/MIF v2)")
    convert_p.add_argument("-o", "--output", help="Output file (stdout if omitted)")

    # validate
    validate_p = subparsers.add_parser("validate", help="Validate MIF JSON against schema")
    validate_p.add_argument("files", nargs="+", help="MIF JSON files to validate")

    # inspect
    inspect_p = subparsers.add_parser("inspect", help="Show summary of a memory file")
    inspect_p.add_argument("input", help="Input file path")
    inspect_p.add_argument("-f", "--from", dest="from_format", help="Source format (auto-detected if omitted)")

    # formats
    subparsers.add_parser("formats", help="List available formats")

    args = parser.parse_args()

    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "formats":
        cmd_formats()
    else:
        parser.print_help()
        sys.exit(1)


def cmd_convert(args):
    data = Path(args.input).read_text(encoding="utf-8")
    doc = load(data, format=args.from_format)
    output = dump(doc, format=args.to_format)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Converted {len(doc.memories)} memories → {args.output} ({args.to_format})")
    else:
        print(output)


def cmd_validate(args):
    passed = 0
    total = len(args.files)

    for filepath in args.files:
        data = Path(filepath).read_text(encoding="utf-8")
        is_valid, errors = validate(data)

        if is_valid:
            doc = load(data)
            has_graph = doc.knowledge_graph is not None
            has_ext = bool(doc.vendor_extensions)

            # Run semantic (deep) validation
            deep_valid, deep_warnings = validate_deep(data)

            if deep_valid:
                print(f"PASS {filepath}")
                print(f"     {len(doc.memories)} memories, graph={'yes' if has_graph else 'no'}, extensions={'yes' if has_ext else 'no'}")
                passed += 1
            else:
                print(f"WARN {filepath}: schema OK, {len(deep_warnings)} semantic warning(s)")
                for w in deep_warnings[:5]:
                    print(f"     {w}")
                if len(deep_warnings) > 5:
                    print(f"     ... and {len(deep_warnings) - 5} more")
                passed += 1  # schema passed, semantic warnings are non-fatal
        else:
            print(f"FAIL {filepath}: {len(errors)} error(s)")
            for err in errors[:5]:
                print(f"     {err}")
            if len(errors) > 5:
                print(f"     ... and {len(errors) - 5} more")

    print(f"\n{passed}/{total} files passed validation")
    sys.exit(0 if passed == total else 1)


def cmd_inspect(args):
    data = Path(args.input).read_text(encoding="utf-8")
    doc = load(data, format=args.from_format)

    print(f"File: {args.input}")
    print(f"MIF version: {doc.mif_version}")
    if doc.generator:
        print(f"Generator: {doc.generator.get('name', '?')} {doc.generator.get('version', '?')}")
    print(f"Memories: {len(doc.memories)}")

    if doc.memories:
        types: dict[str, int] = {}
        for m in doc.memories:
            types[m.memory_type] = types.get(m.memory_type, 0) + 1
        print(f"Types: {', '.join(f'{t}({n})' for t, n in sorted(types.items()))}")

        all_tags = set()
        for m in doc.memories:
            all_tags.update(m.tags)
        if all_tags:
            print(f"Tags: {', '.join(sorted(all_tags))}")

    if doc.knowledge_graph:
        kg = doc.knowledge_graph
        print(f"Graph: {len(kg.entities)} entities, {len(kg.relationships)} relationships")

    if doc.vendor_extensions:
        print(f"Extensions: {', '.join(doc.vendor_extensions.keys())}")


def cmd_formats():
    registry = AdapterRegistry()
    print("Available formats:\n")
    for info in registry.list_formats():
        print(f"  {info['format_id']:12s}  {info['name']}")
    print()
    print("Usage:")
    print("  mif convert input.json --from mem0 --to shodh -o output.mif.json")
    print("  mif convert input.json --to markdown    # auto-detect source")


if __name__ == "__main__":
    main()
