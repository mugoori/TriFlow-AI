#!/usr/bin/env python
"""
List installed modules

Usage:
    python scripts/list_modules.py
    python scripts/list_modules.py --category feature
"""
import argparse
import json
from pathlib import Path


def list_modules(category_filter: str = None):
    """List installed modules"""
    project_root = Path(__file__).parent.parent
    registry_path = project_root / 'modules' / '_registry.json'

    if not registry_path.exists():
        print("❌ Module registry not found")
        print("Run: python scripts/build_module_registry.py")
        return

    # Load registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    modules = registry.get('modules', [])

    # Filter by category
    if category_filter:
        modules = [m for m in modules if m.get('category') == category_filter]

    if not modules:
        if category_filter:
            print(f"No modules found in category '{category_filter}'")
        else:
            print("No modules installed")
        return

    # Print table
    print("\n" + "=" * 100)
    print(f"{'MODULE_CODE':<25} {'VERSION':<10} {'CATEGORY':<15} {'NAME':<30} {'AUTHOR':<20}")
    print("-" * 100)

    for module in modules:
        module_code = module.get('module_code', '')
        version = module.get('version', '')
        category = module.get('category', '')
        name = module.get('name', '')
        author = module.get('author', 'Unknown')

        print(f"{module_code:<25} {version:<10} {category:<15} {name:<30} {author:<20}")

    print("=" * 100)
    print(f"\nTotal: {len(modules)} module(s)")

    # Category summary
    if not category_filter:
        categories = {}
        for m in modules:
            cat = m.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1

        print("\nBy category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")


def main():
    parser = argparse.ArgumentParser(description="List installed TriFlow modules")
    parser.add_argument(
        '--category', '-c',
        choices=['core', 'feature', 'industry', 'integration'],
        help="Filter by category"
    )

    args = parser.parse_args()
    list_modules(args.category)


if __name__ == "__main__":
    main()
