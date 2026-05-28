#!/usr/bin/env python3
"""
Upgrade existing repo_knowledge JSON files to new format.
- Deduplicates test_dirs, main_test_files, common_imports
- Adds new fields with default values
- Preserves existing data
"""
import json
from datetime import datetime
from pathlib import Path


def deduplicate_list(lst):
    """Remove duplicates while preserving order."""
    if not lst:
        return []
    seen = set()
    result = []
    for item in lst:
        if isinstance(item, str):
            item = item.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def upgrade_file(json_path):
    """Upgrade a single repo knowledge JSON file."""
    with open(json_path, "r") as f:
        data = json.load(f)

    changes = []

    # Deduplicate test_structure fields
    if "test_structure" in data:
        ts = data["test_structure"]

        if "test_dirs" in ts:
            before = len(ts["test_dirs"])
            ts["test_dirs"] = deduplicate_list(ts["test_dirs"])
            after = len(ts["test_dirs"])
            if before != after:
                changes.append(f"test_dirs: {before} -> {after}")

        if "main_test_files" in ts:
            before = len(ts["main_test_files"])
            ts["main_test_files"] = deduplicate_list(ts["main_test_files"])
            after = len(ts["main_test_files"])
            if before != after:
                changes.append(f"main_test_files: {before} -> {after}")

    # Deduplicate coding_style fields
    if "coding_style" in data:
        cs = data["coding_style"]

        if "common_imports" in cs:
            before = len(cs["common_imports"])
            cs["common_imports"] = deduplicate_list(cs["common_imports"])
            after = len(cs["common_imports"])
            if before != after:
                changes.append(f"common_imports: {before} -> {after}")

        # Add new fields
        if "teardown_pattern" not in cs:
            cs["teardown_pattern"] = None
        if "error_handling_style" not in cs:
            cs["error_handling_style"] = None

    # Add new top-level fields
    if "lessons_learned" not in data:
        data["lessons_learned"] = []
        changes.append("added lessons_learned[]")

    if "key_types" not in data:
        data["key_types"] = []
        changes.append("added key_types[]")

    if "test_templates" not in data:
        data["test_templates"] = {}
        changes.append("added test_templates{}")

    if "setup_boilerplate" not in data:
        data["setup_boilerplate"] = None

    if "build_command" not in data:
        data["build_command"] = None

    if "test_command" not in data:
        data["test_command"] = None

    if "test_timeout" not in data:
        data["test_timeout"] = None

    # Upgrade helper_functions to include new fields
    if "helper_functions" in data:
        for helper in data["helper_functions"]:
            if "parameters" not in helper:
                helper["parameters"] = []
            if "usage_example" not in helper:
                helper["usage_example"] = None
            if "returns" not in helper:
                helper["returns"] = None

    # Upgrade fault_injection to include new fields
    if "fault_injection" in data:
        for fi in data["fault_injection"]:
            if "example_code" not in fi:
                fi["example_code"] = None

    # Update timestamp
    data["last_updated"] = datetime.now().isoformat()

    # Save back
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return changes


def main():
    """Upgrade all repo knowledge files."""
    repo_knowledge_dir = Path(__file__).parent.parent / "data" / "repo_knowledge"

    if not repo_knowledge_dir.exists():
        print(f"Directory not found: {repo_knowledge_dir}")
        return

    json_files = list(repo_knowledge_dir.glob("*.json"))
    print(f"Found {len(json_files)} repo knowledge files to upgrade")

    for json_file in json_files:
        repo_name = json_file.stem
        print(f"\nUpgrading: {repo_name}")

        try:
            changes = upgrade_file(json_file)
            if changes:
                print(f"  Changes: {', '.join(changes)}")
            else:
                print(f"  No changes needed (already up to date)")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n✅ Upgrade complete!")


if __name__ == "__main__":
    main()
