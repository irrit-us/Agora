"""
Repository Knowledge Cache - stores learned info about each repo's test structure

Enhanced version with:
- Detailed helper function signatures and usage examples
- Code templates for common test patterns
- Lessons learned from previous issues
- Key types/interfaces index
- Automatic deduplication
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class HelperFunction(BaseModel):
    """A helper function discovered in the test code - with full details"""

    name: str
    file: str
    purpose: str
    signature: str | None = (
        None  # e.g., "func MakeCluster(n int, t *testing.T, conf *Config) *cluster"
    )
    parameters: list[str] = Field(
        default_factory=list
    )  # ["n: number of nodes", "t: testing.T"]
    usage_example: str | None = None  # Code snippet showing how to use it
    returns: str | None = None  # What it returns


class FaultInjectionMethod(BaseModel):
    """A method for injecting faults in tests"""

    fault_type: str
    location: str  # file:function or description
    usage: str  # How to use it
    example_code: str | None = None  # Actual code example


class LessonLearned(BaseModel):
    """A lesson learned from previous test generation attempts"""

    issue: str  # What problem was encountered
    solution: str  # How it was solved
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    related_files: list[str] = Field(default_factory=list)
    error_pattern: str | None = (
        None  # Regex or string pattern to match similar errors
    )


class KeyType(BaseModel):
    """A key type/interface in the repository"""

    name: str  # e.g., "Raft", "FSM"
    file: str  # e.g., "raft.go"
    kind: str  # "struct", "interface", "type_alias"
    purpose: str  # Brief description
    key_methods: list[str] = Field(default_factory=list)  # Important methods
    key_fields: list[str] = Field(
        default_factory=list
    )  # Important fields (for structs)


class TestTemplate(BaseModel):
    """A reusable test code template"""

    name: str  # e.g., "basic_unit_test", "cluster_integration_test"
    description: str
    template: str  # The actual code template with placeholders
    placeholders: list[str] = Field(default_factory=list)  # ["TEST_NAME", "SETUP_CODE"]


class TestStructure(BaseModel):
    """Test structure information for a repository"""

    test_dirs: list[str] = Field(default_factory=list)
    test_pattern: str = "*_test.go"
    main_test_files: list[str] = Field(default_factory=list)
    test_framework: str | None = None  # e.g., "testing", "testify", "cargo test"

    @field_validator("test_dirs", mode="before")
    @classmethod
    def deduplicate_test_dirs(cls, v: list[str]) -> list[str]:
        """Remove duplicates and meaningless entries from test_dirs"""
        if not v:
            return []
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for d in v:
            # Normalize path
            d = d.strip()
            if not d:
                continue
            # Skip if already seen
            if d in seen:
                continue
            seen.add(d)
            result.append(d)
        return result

    @field_validator("main_test_files", mode="before")
    @classmethod
    def deduplicate_test_files(cls, v: list[str]) -> list[str]:
        """Remove duplicates from main_test_files"""
        if not v:
            return []
        seen = set()
        result = []
        for f in v:
            f = f.strip()
            if f and f not in seen:
                seen.add(f)
                result.append(f)
        return result


class CodingStyle(BaseModel):
    """Coding style conventions in the repo"""

    naming_convention: str = "TestXxx"
    setup_pattern: str | None = None
    teardown_pattern: str | None = None  # How cleanup is done
    assertion_style: str | None = None
    common_imports: list[str] = Field(default_factory=list)
    error_handling_style: str | None = None  # How errors are typically checked

    @field_validator("common_imports", mode="before")
    @classmethod
    def deduplicate_imports(cls, v: list[str]) -> list[str]:
        """Remove duplicates from common_imports"""
        if not v:
            return []
        seen = set()
        result = []
        for imp in v:
            imp = imp.strip()
            if imp and imp not in seen:
                seen.add(imp)
                result.append(imp)
        return result


class RepoKnowledgeData(BaseModel):
    """Complete knowledge about a repository's test infrastructure"""

    repo: str
    language: str
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Package/module info (detected from source, not guessed!)
    package_name: str | None = None  # e.g., "raft" for Go
    module_path: str | None = None  # e.g., "github.com/hashicorp/raft"

    # Core structures
    test_structure: TestStructure = Field(default_factory=TestStructure)
    coding_style: CodingStyle = Field(default_factory=CodingStyle)

    # Detailed knowledge
    helper_functions: list[HelperFunction] = Field(default_factory=list)
    fault_injection: list[FaultInjectionMethod] = Field(default_factory=list)
    key_types: list[KeyType] = Field(default_factory=list)  # NEW

    # Templates and patterns
    test_templates: dict[str, TestTemplate] = Field(default_factory=dict)  # NEW
    setup_boilerplate: str | None = None  # Common setup code

    # Learning from experience
    lessons_learned: list[LessonLearned] = Field(
        default_factory=list
    )  # NEW (replaces notes)
    notes: list[str] = Field(default_factory=list)  # Keep for backward compatibility

    # Build and run info
    build_command: str | None = None  # How to build the project
    test_command: str | None = None  # How to run tests
    test_timeout: str | None = None  # Typical test timeout

    # Hash of analyzed files to detect changes
    file_hashes: dict[str, str] = Field(default_factory=dict)

    def get_helper_by_name(self, name: str) -> HelperFunction | None:
        """Get a helper function by name"""
        for h in self.helper_functions:
            if h.name == name:
                return h
        return None

    def get_key_type_by_name(self, name: str) -> KeyType | None:
        """Get a key type by name"""
        for t in self.key_types:
            if t.name == name:
                return t
        return None

    def find_relevant_lessons(self, error_message: str) -> list[LessonLearned]:
        """Find lessons that might be relevant to an error"""
        relevant = []
        error_lower = error_message.lower()
        for lesson in self.lessons_learned:
            # Check if error pattern matches
            if lesson.error_pattern:
                try:
                    if re.search(lesson.error_pattern, error_message, re.IGNORECASE):
                        relevant.append(lesson)
                        continue
                except re.error:
                    pass
            # Fallback: simple keyword matching
            issue_lower = lesson.issue.lower()
            if any(
                word in error_lower for word in issue_lower.split() if len(word) > 4
            ):
                relevant.append(lesson)
        return relevant


class RepoKnowledge:
    """
    Manages repository knowledge cache.
    SubAgent learns about repo test structure once and caches it.
    """

    def __init__(self, base_path: Path | None = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "repo_knowledge"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, repo: str) -> Path:
        """Get the cache file path for a repo"""
        safe_name = repo.replace("/", "_").replace("\\", "_")
        return self.base_path / f"{safe_name}.json"

    async def get(self, repo: str) -> RepoKnowledgeData | None:
        """Get cached knowledge for a repo"""
        file_path = self._get_file_path(repo)

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Handle field name migration: repo_name -> repo
            if "repo_name" in data and "repo" not in data:
                data["repo"] = data.pop("repo_name")

            # Pydantic validators will auto-deduplicate during parsing
            return RepoKnowledgeData(**data)
        except json.JSONDecodeError as e:
            # Corrupted JSON file - log and return None to allow graceful degradation
            logger.warning(f"Invalid JSON in repo knowledge for {repo}: {e}")
            return None
        except OSError as e:
            # File read error - log and return None to allow graceful degradation
            logger.warning(f"Failed to read repo knowledge for {repo}: {e}")
            return None
        except (KeyError, TypeError, ValueError) as e:
            # Invalid data structure - log and return None to allow graceful degradation
            logger.warning(f"Invalid data structure in repo knowledge for {repo}: {e}")
            return None

    async def save(self, knowledge: RepoKnowledgeData) -> None:
        """Save or update knowledge for a repo"""
        knowledge.last_updated = datetime.now().isoformat()
        file_path = self._get_file_path(knowledge.repo)

        with open(file_path, "w") as f:
            json.dump(knowledge.model_dump(), f, indent=2, ensure_ascii=False)

    async def update_helpers(self, repo: str, helpers: list[HelperFunction]) -> None:
        """Update helper functions for a repo"""
        knowledge = await self.get(repo)
        if knowledge:
            # Merge helpers, avoiding duplicates by name
            def get_name(h: Any) -> str:
                if isinstance(h, dict):
                    return h.get("name", "")
                return getattr(h, "name", "")

            existing_names = {get_name(h) for h in knowledge.helper_functions}
            for helper in helpers:
                helper_name = get_name(helper)
                if helper_name and helper_name not in existing_names:
                    if isinstance(helper, dict):
                        knowledge.helper_functions.append(HelperFunction(**helper))
                    else:
                        knowledge.helper_functions.append(helper)
                    existing_names.add(helper_name)
            await self.save(knowledge)

    async def update_helper_details(
        self,
        repo: str,
        helper_name: str,
        signature: str | None = None,
        parameters: list[str] | None = None,
        usage_example: str | None = None,
        returns: str | None = None,
    ) -> bool:
        """Update details for an existing helper function"""
        knowledge = await self.get(repo)
        if not knowledge:
            return False

        for helper in knowledge.helper_functions:
            if helper.name == helper_name:
                if signature:
                    helper.signature = signature
                if parameters:
                    helper.parameters = parameters
                if usage_example:
                    helper.usage_example = usage_example
                if returns:
                    helper.returns = returns
                await self.save(knowledge)
                return True
        return False

    async def update_fault_injection(
        self, repo: str, methods: list[FaultInjectionMethod]
    ) -> None:
        """Update fault injection methods for a repo"""
        knowledge = await self.get(repo)
        if knowledge:
            existing = {(m.fault_type, m.location) for m in knowledge.fault_injection}
            for method in methods:
                if (method.fault_type, method.location) not in existing:
                    if isinstance(method, dict):
                        knowledge.fault_injection.append(FaultInjectionMethod(**method))
                    else:
                        knowledge.fault_injection.append(method)
            await self.save(knowledge)

    async def add_key_type(self, repo: str, key_type: KeyType) -> None:
        """Add a key type to the repo knowledge"""
        knowledge = await self.get(repo)
        if knowledge:
            # Check if type already exists
            existing_names = {t.name for t in knowledge.key_types}
            if key_type.name not in existing_names:
                knowledge.key_types.append(key_type)
                await self.save(knowledge)

    async def add_test_template(self, repo: str, template: TestTemplate) -> None:
        """Add or update a test template"""
        knowledge = await self.get(repo)
        if knowledge:
            knowledge.test_templates[template.name] = template
            await self.save(knowledge)

    async def add_lesson_learned(
        self,
        repo: str,
        issue: str,
        solution: str,
        related_files: list[str] | None = None,
        error_pattern: str | None = None,
    ) -> None:
        """Add a lesson learned from test generation experience"""
        knowledge = await self.get(repo)
        if knowledge:
            lesson = LessonLearned(
                issue=issue,
                solution=solution,
                related_files=related_files or [],
                error_pattern=error_pattern,
            )
            # Avoid duplicate lessons
            existing_issues = {l.issue for l in knowledge.lessons_learned}
            if issue not in existing_issues:
                knowledge.lessons_learned.append(lesson)
                await self.save(knowledge)

    async def add_note(self, repo: str, note: str) -> None:
        """Add a note about the repo (legacy method, prefer add_lesson_learned)"""
        knowledge = await self.get(repo)
        if knowledge:
            knowledge.notes.append(f"[{datetime.now().isoformat()}] {note}")
            await self.save(knowledge)

    async def set_setup_boilerplate(self, repo: str, boilerplate: str) -> None:
        """Set the common setup boilerplate code"""
        knowledge = await self.get(repo)
        if knowledge:
            knowledge.setup_boilerplate = boilerplate
            await self.save(knowledge)

    async def set_build_commands(
        self,
        repo: str,
        build_command: str | None = None,
        test_command: str | None = None,
        test_timeout: str | None = None,
    ) -> None:
        """Set build and test commands"""
        knowledge = await self.get(repo)
        if knowledge:
            if build_command:
                knowledge.build_command = build_command
            if test_command:
                knowledge.test_command = test_command
            if test_timeout:
                knowledge.test_timeout = test_timeout
            await self.save(knowledge)

    async def needs_update(self, repo: str, file_hashes: dict[str, str]) -> bool:
        """Check if repo knowledge needs to be updated based on file changes"""
        knowledge = await self.get(repo)
        if knowledge is None:
            return True

        # Check if any tracked files have changed
        for file_path, new_hash in file_hashes.items():
            if knowledge.file_hashes.get(file_path) != new_hash:
                return True

        return False

    async def cleanup_duplicates(self, repo: str) -> bool:
        """Force cleanup of any duplicate data in existing knowledge"""
        knowledge = await self.get(repo)
        if not knowledge:
            return False

        # Re-save will trigger validators to deduplicate
        await self.save(knowledge)
        return True

    async def get_compact_summary(self, repo: str) -> str | None:
        """Get a compact summary optimized for LLM context"""
        knowledge = await self.get(repo)
        if not knowledge:
            return None

        summary_parts = [
            f"# Repository: {knowledge.repo}",
            f"Language: {knowledge.language}",
        ]

        if knowledge.package_name:
            summary_parts.append(f"Package: {knowledge.package_name}")
        if knowledge.module_path:
            summary_parts.append(f"Module: {knowledge.module_path}")

        # Test structure
        summary_parts.append("\n## Test Structure")
        if knowledge.test_structure.test_dirs:
            summary_parts.append(
                f"Dirs: {', '.join(knowledge.test_structure.test_dirs)}"
            )
        summary_parts.append(f"Pattern: {knowledge.test_structure.test_pattern}")
        if knowledge.test_command:
            summary_parts.append(f"Test command: {knowledge.test_command}")

        # Coding style
        summary_parts.append("\n## Coding Style")
        summary_parts.append(f"Naming: {knowledge.coding_style.naming_convention}")
        if knowledge.coding_style.assertion_style:
            summary_parts.append(
                f"Assertions: {knowledge.coding_style.assertion_style}"
            )
        if knowledge.coding_style.common_imports:
            summary_parts.append(
                f"Common imports: {', '.join(knowledge.coding_style.common_imports[:5])}"
            )

        # Helper functions (with signatures if available)
        if knowledge.helper_functions:
            summary_parts.append("\n## Key Helper Functions")
            for h in knowledge.helper_functions[:10]:  # Limit to top 10
                if h.signature:
                    summary_parts.append(f"- `{h.signature}` - {h.purpose}")
                else:
                    summary_parts.append(f"- `{h.name}` ({h.file}) - {h.purpose}")
                if h.usage_example:
                    summary_parts.append(f"  Example: ```{h.usage_example}```")

        # Setup boilerplate
        if knowledge.setup_boilerplate:
            summary_parts.append(
                f"\n## Setup Boilerplate\n```\n{knowledge.setup_boilerplate}\n```"
            )

        # Lessons learned
        if knowledge.lessons_learned:
            summary_parts.append("\n## Lessons Learned")
            for lesson in knowledge.lessons_learned[-5:]:  # Last 5 lessons
                summary_parts.append(f"- **Issue**: {lesson.issue}")
                summary_parts.append(f"  **Solution**: {lesson.solution}")

        return "\n".join(summary_parts)
