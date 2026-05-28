#!/usr/bin/env python3
"""
Memory Cleanup Script
Cleans up pattern memory files:
1. Delete empty files
2. Remove repo prefix from pattern memory filenames
3. Clean redundant fields (timestamp, source_agent, repo)
4. Clean id prefixes (bug_pattern_)
"""
import json
from pathlib import Path

# Known repo prefixes to remove from pattern memory filenames
REPO_PREFIXES = [
    "bftsmart_",
    "hotstuff_",
    "cometbft_",
    "sui_",
    "fabric_",
    "zookeeper_",
    "raft_rs_",
    "hashicorp_raft_",
    "phxpaxos_",
    "epaxos_",
    "raft_",
    "hashicorp-raft_",
]

# Fields to remove
FIELDS_TO_REMOVE_PATTERN = ["timestamp", "source_agent", "repo"]


def remove_repo_prefix(filename: str) -> str:
    """Remove repo prefix from filename."""
    name = filename
    for prefix in sorted(REPO_PREFIXES, key=len, reverse=True):  # Longest first
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name


def clean_id(id_value: str) -> str:
    """Remove redundant prefixes from id."""
    # Remove bug_pattern_ prefix
    if id_value.startswith("bug_pattern_"):
        id_value = id_value[len("bug_pattern_") :]
    # Also remove repo prefixes from id
    for prefix in sorted(REPO_PREFIXES, key=len, reverse=True):
        if id_value.startswith(prefix):
            id_value = id_value[len(prefix) :]
            break
    return id_value


def is_empty_or_useless(data: dict) -> bool:
    """Check if a memory entry is empty or useless."""
    # Pattern memory uses 'description' or 'content' field
    content = data.get("description", "") or data.get("content", "")

    if not content or content.strip() == "":
        return True
    # Check for placeholder content (like "False positive in xxx: ")
    if content.strip().endswith(":") and len(content.strip()) < 50:
        return True
    return False


def normalize_pattern_format(data: dict, subdir: str) -> tuple[dict, list[str]]:
    """
    Normalize pattern data to BugPattern model format.

    Old format: id, protocol, content
    New format: pattern_id, protocol_type, description

    Returns: (normalized_data, list_of_changes)
    """
    changes = []

    # Normalize id -> pattern_id
    if "id" in data and "pattern_id" not in data:
        data["pattern_id"] = data.pop("id")
        changes.append("id -> pattern_id")

    # Normalize protocol -> protocol_type
    if "protocol" in data and "protocol_type" not in data:
        data["protocol_type"] = data.pop("protocol")
        changes.append("protocol -> protocol_type")

    # Ensure protocol_type matches directory
    if "protocol_type" not in data:
        data["protocol_type"] = subdir
        changes.append(f"added protocol_type={subdir}")

    # Normalize content -> description
    if "content" in data and "description" not in data:
        data["description"] = data.pop("content")
        changes.append("content -> description")

    return data, changes


def clean_pattern_memory(base_path: Path, dry_run: bool = True):
    """Clean pattern memory files."""
    print("\n=== Cleaning Pattern Memory ===")

    for subdir in ["cft", "bft"]:
        dir_path = base_path / "data" / "pattern_memory" / subdir
        if not dir_path.exists():
            continue

        print(f"\n--- {subdir.upper()} ---")

        for json_file in dir_path.glob("*.json"):
            original_name = json_file.stem
            new_name = remove_repo_prefix(original_name)

            # Read file
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"  ❌ Error reading {json_file.name}: {e}")
                if not dry_run:
                    json_file.unlink()
                    print(f"     Deleted corrupted file")
                continue

            # Check if empty
            if is_empty_or_useless(data):
                print(f"  🗑️  {json_file.name} - EMPTY/USELESS")
                if not dry_run:
                    json_file.unlink()
                    print(f"     Deleted")
                continue

            # Clean data
            modified = False
            all_changes = []

            # Normalize to BugPattern format
            data, format_changes = normalize_pattern_format(data, subdir)
            if format_changes:
                modified = True
                all_changes.extend(format_changes)

            # Clean pattern_id field (remove prefixes)
            if "pattern_id" in data:
                old_id = data["pattern_id"]
                new_id = clean_id(old_id)
                if old_id != new_id:
                    data["pattern_id"] = new_id
                    modified = True
                    all_changes.append(f"pattern_id '{old_id}' -> '{new_id}'")

            # Remove redundant fields
            for field in FIELDS_TO_REMOVE_PATTERN:
                if field in data:
                    del data[field]
                    modified = True
                    all_changes.append(f"removed '{field}'")

            # Print changes
            if all_changes:
                print(f"  📝 {json_file.name}: {', '.join(all_changes)}")

            # Rename file if needed
            if original_name != new_name:
                new_path = dir_path / f"{new_name}.json"
                print(f"  📁 Rename: {original_name}.json -> {new_name}.json")

                if not dry_run:
                    # Save with new name
                    with open(new_path, "w") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    # Delete old file
                    json_file.unlink()
            elif modified and not dry_run:
                # Just save modified data
                with open(json_file, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)


def clean_lock_files(base_path: Path, dry_run: bool = True):
    """Remove all .lock files created by filelock library."""
    print("\n=== Cleaning Lock Files ===")

    lock_files = list(base_path.rglob("*.lock"))
    print(f"Found {len(lock_files)} .lock files")

    if not dry_run and lock_files:
        for lock_file in lock_files:
            lock_file.unlink()
        print(f"  🗑️  Deleted {len(lock_files)} .lock files")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean memory files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be done without making changes (default)",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform the cleanup"
    )
    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Run with --execute to apply changes\n")
    else:
        print("⚠️  EXECUTE MODE - Changes will be applied\n")

    # Find base path
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent  # agent/

    print(f"Base path: {base_path}")

    clean_pattern_memory(base_path, dry_run)
    clean_lock_files(base_path, dry_run)

    if dry_run:
        print("\n" + "=" * 50)
        print("Run with --execute to apply these changes")


if __name__ == "__main__":
    main()
