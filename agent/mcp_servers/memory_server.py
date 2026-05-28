"""
Memory MCP Server - Provides memory tools for Claude Agent SDK
Wraps PatternMemory, RepoKnowledge, and TestHistory
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import existing memory modules
from ..memory.pattern_memory import BugPattern, PatternMemory
from ..memory.repo_knowledge import RepoKnowledge, RepoKnowledgeData
from ..memory.test_history import TestHistory, TestRecord


@dataclass
class MemoryServer:
    """Container for all memory instances"""

    pattern_memory: PatternMemory
    repo_knowledge: RepoKnowledge
    test_history: TestHistory


def create_memory_server(
    base_path: Path | None = None,
    api_key: str | None = None,
    embedding_model: str = "openai/text-embedding-3-small",
) -> "MemoryServer":
    """
    Create and initialize all memory components.

    Args:
        base_path: Base path for memory storage (defaults to agent directory)
        api_key: OpenRouter API key (kept for compatibility, not used)
        embedding_model: Model to use for embeddings (kept for compatibility, not used)

    Returns:
        MemoryServer with all components initialized
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent

    # Initialize memory components
    pattern_memory = PatternMemory(base_path / "data" / "pattern_memory")
    repo_knowledge = RepoKnowledge(base_path / "data" / "repo_knowledge")
    test_history = TestHistory(base_path / "data" / "test_history")

    return MemoryServer(
        pattern_memory=pattern_memory,
        repo_knowledge=repo_knowledge,
        test_history=test_history,
    )


# ============================================================
# Memory Tools for Claude Agent SDK
# ============================================================


class MemoryTools:
    """
    Memory tools for Claude Agent SDK.
    Each method is a tool that can be called by the agent.
    """

    def __init__(self, memory_server: MemoryServer):
        self.memory = memory_server

    # ==================== Pattern Memory Tools ====================

    async def pattern_get(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get bug patterns for a specific protocol type.

        Args:
            protocol_type: "cft" or "bft"
            not_tested_in: Optional repo name to exclude already tested patterns
            bug_category: Optional filter by category (safety/liveness/agreement)
        """
        protocol_type = args.get("protocol_type", "cft")
        not_tested_in = args.get("not_tested_in")
        bug_category = args.get("bug_category")

        patterns = await self.memory.pattern_memory.get_patterns_for_protocol(
            protocol_type=protocol_type,
            not_tested_in=not_tested_in,
            bug_category=bug_category,
        )

        # Format patterns for LLM
        result = []
        for p in patterns:
            result.append(
                {
                    "pattern_id": p.pattern_id,
                    "fault_type": p.fault_type,
                    "bug_category": p.bug_category,
                    "trigger_condition": p.trigger_condition,
                    "description": p.description,
                    "confirmed_in_repos": p.confirmed_in_repos,
                }
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result)} patterns:\n\n"
                    + json.dumps(result, indent=2, ensure_ascii=False),
                }
            ]
        }

    async def pattern_add(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add a new bug pattern to Pattern Memory.

        Args:
            pattern_id: Summary/identifier for the bug pattern (required)
            protocol_type: "cft" or "bft"
            fault_type: Type of fault that triggers this bug
            bug_category: "safety", "liveness", or "agreement"
            trigger_condition: Description of what triggers the bug
            description: Detailed explanation of the bug pattern
            discovered_in_repo: Repository where this was discovered
        """
        # pattern_id is required
        pattern_id = args.get("pattern_id")
        if not pattern_id:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: pattern_id is required",
                    }
                ],
                "isError": True,
            }

        pattern = BugPattern(
            pattern_id=pattern_id,
            protocol_type=args.get("protocol_type", "cft"),
            fault_type=args.get("fault_type", ""),
            bug_category=args.get("bug_category", "safety"),
            trigger_condition=args.get("trigger_condition", ""),
            description=args.get("description", ""),
            discovered_in_repo=args.get("discovered_in_repo"),
            test_template=args.get("test_template", ""),
        )

        pattern_id = await self.memory.pattern_memory.add_pattern(pattern)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully added pattern with ID: {pattern_id}",
                }
            ]
        }

    async def pattern_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Search patterns by various criteria.

        Args:
            protocol_type: Optional filter by protocol type
            fault_type: Optional filter by fault type
            bug_category: Optional filter by category
        """
        protocol_type = args.get("protocol_type")
        patterns = await self.memory.pattern_memory.get_all_patterns(protocol_type)

        # Apply additional filters
        fault_type = args.get("fault_type")
        bug_category = args.get("bug_category")

        if fault_type:
            patterns = [
                p for p in patterns if fault_type.lower() in p.fault_type.lower()
            ]
        if bug_category:
            patterns = [p for p in patterns if p.bug_category == bug_category]

        result = []
        for p in patterns:
            result.append(
                {
                    "pattern_id": p.pattern_id,
                    "protocol_type": p.protocol_type,
                    "fault_type": p.fault_type,
                    "bug_category": p.bug_category,
                    "description": (
                        p.description[:200] + "..."
                        if len(p.description) > 200
                        else p.description
                    ),
                }
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result)} matching patterns:\n\n"
                    + json.dumps(result, indent=2, ensure_ascii=False),
                }
            ]
        }

    async def pattern_list(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        List all patterns with only summary information (pattern_id).
        Strategy Agent should call this first to see available patterns,
        then use pattern_get_detail to get full details of interesting ones.

        Args:
            protocol_type: Optional filter by protocol type ("cft" or "bft")
        """
        protocol_type = args.get("protocol_type")
        patterns = await self.memory.pattern_memory.get_all_patterns(protocol_type)

        # Return only summary info - pattern_id serves as the summary
        result = []
        for p in patterns:
            result.append(
                {
                    "pattern_id": p.pattern_id,
                    "protocol_type": p.protocol_type,
                    "bug_category": p.bug_category,
                }
            )

        # Add guidance to prevent context window explosion
        guidance = (
            "\n\n---\n"
            "**IMPORTANT**: To manage context efficiently, only call `pattern_get_detail` "
            "for the 2-3 most relevant patterns based on your target protocol and attack strategy. "
            "Do NOT retrieve all patterns - the pattern_id already contains a summary of each pattern."
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result)} patterns:\n\n"
                    + json.dumps(result, indent=2, ensure_ascii=False)
                    + guidance,
                }
            ]
        }

    async def pattern_get_detail(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get full details of a specific pattern by pattern_id.
        Use pattern_list first to see available patterns.

        Args:
            pattern_id: The pattern_id to retrieve (required)
            protocol_type: Protocol type "cft" or "bft" (required)
        """
        pattern_id = args.get("pattern_id")
        protocol_type = args.get("protocol_type")

        if not pattern_id:
            return {
                "content": [{"type": "text", "text": "Error: pattern_id is required"}]
            }

        if not protocol_type:
            return {
                "content": [
                    {"type": "text", "text": "Error: protocol_type is required"}
                ]
            }

        pattern = await self.memory.pattern_memory.get_pattern(
            pattern_id, protocol_type
        )

        if not pattern:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Pattern not found: {pattern_id} (protocol_type: {protocol_type})",
                    }
                ]
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        pattern.model_dump(), indent=2, ensure_ascii=False
                    ),
                }
            ]
        }

    # ==================== Repo Knowledge Tools ====================

    async def repo_knowledge_get(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get cached knowledge about a repository's test structure.

        Args:
            repo: Repository name
            compact: If True, return a compact summary optimized for LLM context
        """
        repo = args.get("repo", "")
        compact = args.get("compact", False)

        knowledge = await self.memory.repo_knowledge.get(repo)

        if knowledge is None:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No cached knowledge found for repository: {repo}. You may need to analyze the repository first.",
                    }
                ]
            }

        # Return compact summary if requested
        if compact:
            summary = await self.memory.repo_knowledge.get_compact_summary(repo)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": summary or f"No summary available for {repo}",
                    }
                ]
            }

        # Full result with all new fields
        def safe_get_attr(obj, attr, default=""):
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        result = {
            "repo": knowledge.repo,
            "language": knowledge.language,
            "package_name": knowledge.package_name,
            "module_path": knowledge.module_path,
            "build_command": knowledge.build_command,
            "test_command": knowledge.test_command,
            "test_timeout": knowledge.test_timeout,
            "test_structure": {
                "test_dirs": knowledge.test_structure.test_dirs,
                "test_pattern": knowledge.test_structure.test_pattern,
                "main_test_files": knowledge.test_structure.main_test_files,
                "test_framework": knowledge.test_structure.test_framework,
            },
            "coding_style": {
                "naming_convention": knowledge.coding_style.naming_convention,
                "setup_pattern": knowledge.coding_style.setup_pattern,
                "teardown_pattern": knowledge.coding_style.teardown_pattern,
                "assertion_style": knowledge.coding_style.assertion_style,
                "error_handling_style": knowledge.coding_style.error_handling_style,
                "common_imports": knowledge.coding_style.common_imports,
            },
            "helper_functions": [
                {
                    "name": safe_get_attr(h, "name"),
                    "file": safe_get_attr(h, "file"),
                    "purpose": safe_get_attr(h, "purpose"),
                    "signature": safe_get_attr(h, "signature"),
                    "parameters": safe_get_attr(h, "parameters", []),
                    "usage_example": safe_get_attr(h, "usage_example"),
                    "returns": safe_get_attr(h, "returns"),
                }
                for h in knowledge.helper_functions[:15]  # Top 15
            ],
            "fault_injection": [
                {
                    "fault_type": safe_get_attr(f, "fault_type"),
                    "location": safe_get_attr(f, "location"),
                    "usage": safe_get_attr(f, "usage"),
                    "example_code": safe_get_attr(f, "example_code"),
                }
                for f in knowledge.fault_injection[:10]
            ],
            "key_types": [
                {
                    "name": safe_get_attr(t, "name"),
                    "file": safe_get_attr(t, "file"),
                    "kind": safe_get_attr(t, "kind"),
                    "purpose": safe_get_attr(t, "purpose"),
                    "key_methods": safe_get_attr(t, "key_methods", []),
                }
                for t in knowledge.key_types[:10]
            ],
            "setup_boilerplate": knowledge.setup_boilerplate,
            "test_templates": {
                name: {
                    "description": safe_get_attr(t, "description"),
                    "template": safe_get_attr(t, "template"),
                    "placeholders": safe_get_attr(t, "placeholders", []),
                }
                for name, t in list(knowledge.test_templates.items())[:5]
            },
            "lessons_learned": [
                {
                    "issue": l.issue,
                    "solution": l.solution,
                    "error_pattern": l.error_pattern,
                }
                for l in knowledge.lessons_learned[-10:]  # Last 10 lessons
            ],
            "notes": knowledge.notes[-5:],  # Last 5 notes (backward compat)
        }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, ensure_ascii=False),
                }
            ]
        }

    async def repo_knowledge_save(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Save or update repository knowledge.

        Args:
            repo: Repository name
            language: Programming language
            package_name: Package/module name
            module_path: Module path
            test_structure: Test structure information
            coding_style: Coding style conventions
            build_command: Build command
            test_command: Test command
            setup_boilerplate: Common setup code
        """
        from ..memory.repo_knowledge import CodingStyle, TestStructure

        # Merge with existing knowledge if present
        existing = await self.memory.repo_knowledge.get(args.get("repo", ""))

        knowledge = RepoKnowledgeData(
            repo=args.get("repo", ""),
            language=args.get("language", existing.language if existing else ""),
            package_name=args.get(
                "package_name", existing.package_name if existing else None
            ),
            module_path=args.get(
                "module_path", existing.module_path if existing else None
            ),
            test_structure=TestStructure(
                **args.get(
                    "test_structure",
                    existing.test_structure.model_dump() if existing else {},
                )
            ),
            coding_style=CodingStyle(
                **args.get(
                    "coding_style",
                    existing.coding_style.model_dump() if existing else {},
                )
            ),
            build_command=args.get(
                "build_command", existing.build_command if existing else None
            ),
            test_command=args.get(
                "test_command", existing.test_command if existing else None
            ),
            test_timeout=args.get(
                "test_timeout", existing.test_timeout if existing else None
            ),
            setup_boilerplate=args.get(
                "setup_boilerplate", existing.setup_boilerplate if existing else None
            ),
            # Preserve existing data
            helper_functions=existing.helper_functions if existing else [],
            fault_injection=existing.fault_injection if existing else [],
            key_types=existing.key_types if existing else [],
            test_templates=existing.test_templates if existing else {},
            lessons_learned=existing.lessons_learned if existing else [],
            notes=existing.notes if existing else [],
            file_hashes=existing.file_hashes if existing else {},
        )

        await self.memory.repo_knowledge.save(knowledge)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully saved knowledge for repository: {knowledge.repo}",
                }
            ]
        }

    async def repo_knowledge_add_helper(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add or update a helper function with detailed information.

        Args:
            repo: Repository name
            name: Function name
            file: File where defined
            purpose: What the function does
            signature: Full function signature (optional)
            parameters: List of parameter descriptions (optional)
            usage_example: Code example showing usage (optional)
            returns: Description of return value (optional)
        """
        from ..memory.repo_knowledge import HelperFunction

        repo = args.get("repo", "")
        helper = HelperFunction(
            name=args.get("name", ""),
            file=args.get("file", ""),
            purpose=args.get("purpose", ""),
            signature=args.get("signature"),
            parameters=args.get("parameters", []),
            usage_example=args.get("usage_example"),
            returns=args.get("returns"),
        )

        # Try to update existing or add new
        updated = await self.memory.repo_knowledge.update_helper_details(
            repo=repo,
            helper_name=helper.name,
            signature=helper.signature,
            parameters=helper.parameters,
            usage_example=helper.usage_example,
            returns=helper.returns,
        )

        if not updated:
            # Add as new helper
            await self.memory.repo_knowledge.update_helpers(repo, [helper])

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully {'updated' if updated else 'added'} helper function: {helper.name}",
                }
            ]
        }

    async def repo_knowledge_add_lesson(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add a lesson learned from test generation experience.
        Call this after fixing an error to help future test generation.

        Args:
            repo: Repository name
            issue: What problem was encountered
            solution: How it was solved
            related_files: List of related file paths (optional)
            error_pattern: Regex pattern to match similar errors (optional)
        """
        repo = args.get("repo", "")
        await self.memory.repo_knowledge.add_lesson_learned(
            repo=repo,
            issue=args.get("issue", ""),
            solution=args.get("solution", ""),
            related_files=args.get("related_files", []),
            error_pattern=args.get("error_pattern"),
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully added lesson learned for {repo}: {args.get('issue', '')[:50]}...",
                }
            ]
        }

    async def repo_knowledge_find_lessons(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Find lessons learned that might be relevant to an error message.
        Use this when encountering test compilation or execution errors.

        Args:
            repo: Repository name
            error_message: The error message to find relevant lessons for
        """
        repo = args.get("repo", "")
        error_message = args.get("error_message", "")

        knowledge = await self.memory.repo_knowledge.get(repo)
        if not knowledge:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No knowledge found for repository: {repo}",
                    }
                ]
            }

        relevant = knowledge.find_relevant_lessons(error_message)

        if not relevant:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No relevant lessons found for this error. This might be a new issue.",
                    }
                ]
            }

        result = []
        for lesson in relevant:
            result.append(
                {
                    "issue": lesson.issue,
                    "solution": lesson.solution,
                    "related_files": lesson.related_files,
                }
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result)} relevant lessons:\n\n"
                    + json.dumps(result, indent=2, ensure_ascii=False),
                }
            ]
        }

    async def repo_knowledge_add_template(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add a reusable test code template.

        Args:
            repo: Repository name
            name: Template name (e.g., "basic_unit_test", "cluster_test")
            description: What the template is for
            template: The code template with placeholders like {{TEST_NAME}}
            placeholders: List of placeholder names used in the template
        """
        from ..memory.repo_knowledge import TestTemplate

        repo = args.get("repo", "")
        template = TestTemplate(
            name=args.get("name", ""),
            description=args.get("description", ""),
            template=args.get("template", ""),
            placeholders=args.get("placeholders", []),
        )

        await self.memory.repo_knowledge.add_test_template(repo, template)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully added test template: {template.name}",
                }
            ]
        }

    async def repo_knowledge_add_key_type(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add a key type/interface that is important for testing.

        Args:
            repo: Repository name
            name: Type name (e.g., "Raft", "FSM")
            file: File where defined
            kind: "struct", "interface", or "type_alias"
            purpose: Brief description
            key_methods: List of important method names (optional)
            key_fields: List of important field names for structs (optional)
        """
        from ..memory.repo_knowledge import KeyType

        repo = args.get("repo", "")
        key_type = KeyType(
            name=args.get("name", ""),
            file=args.get("file", ""),
            kind=args.get("kind", "struct"),
            purpose=args.get("purpose", ""),
            key_methods=args.get("key_methods", []),
            key_fields=args.get("key_fields", []),
        )

        await self.memory.repo_knowledge.add_key_type(repo, key_type)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully added key type: {key_type.name}",
                }
            ]
        }

    async def repo_knowledge_cleanup(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Clean up duplicate data in repository knowledge.

        Args:
            repo: Repository name
        """
        repo = args.get("repo", "")
        success = await self.memory.repo_knowledge.cleanup_duplicates(repo)

        if success:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully cleaned up duplicates for repository: {repo}",
                    }
                ]
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No knowledge found for repository: {repo}",
                    }
                ]
            }

    # ==================== Test History Tools ====================

    async def test_history_add(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Add a test execution record.

        Args:
            protocol: Protocol name
            protocol_type: "cft" or "bft"
            language: Programming language
            model: LLM model used for test generation
            scenario_name: Name of the test scenario
            scenario_description: Description of the scenario
            fault_type: Type of fault tested
            bug_category: Category of bug targeted
            steps: List of test steps
            strategy_source: Where the strategy came from
            test_name: Name of the test
            test_file: Path to test file
            test_code: The test code
            test_passed: Whether the test passed
            test_output: Test output
            is_real_bug: Whether a real bug was found
            is_realistic_scenario: Whether the scenario is realistic
        """
        record = TestRecord(
            id=f"{args.get('protocol', 'unknown')}-{args.get('test_name', 'test')}",
            protocol=args.get("protocol", ""),
            protocol_type=args.get("protocol_type", "cft"),
            language=args.get("language", ""),
            model=args.get("model", ""),
            scenario_name=args.get("scenario_name", ""),
            scenario_description=args.get("scenario_description", ""),
            fault_type=args.get("fault_type", ""),
            bug_category=args.get("bug_category", ""),
            steps=args.get("steps", []),
            strategy_source=args.get("strategy_source", ""),
            test_name=args.get("test_name", ""),
            test_file=args.get("test_file", ""),
            test_code=args.get("test_code", ""),
            test_passed=args.get("test_passed", True),
            test_output=args.get("test_output", ""),
            validated=args.get("validated"),
            is_real_bug=args.get("is_real_bug"),
            is_realistic_scenario=args.get("is_realistic_scenario"),
            validation_reason=args.get("validation_reason"),
        )

        record_id = await self.memory.test_history.add_record(record)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully added test record with ID: {record_id}",
                }
            ]
        }

    async def test_history_get_stats(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get test history statistics.

        Args:
            protocol: Optional protocol name to filter by
            model: Optional model name to filter by
        """
        protocol = args.get("protocol")
        model = args.get("model", "")
        stats = await self.memory.test_history.get_stats(protocol, model)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Test Statistics:\n\n" + json.dumps(stats, indent=2),
                }
            ]
        }

    async def test_history_get_bugs(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get confirmed bugs.

        Args:
            protocol: Optional protocol name to filter by
            model: Optional model name to filter by
        """
        protocol = args.get("protocol")
        model = args.get("model", "")

        if protocol:
            bugs = await self.memory.test_history.get_bugs(protocol, model)
        else:
            bugs = await self.memory.test_history.get_all_bugs()

        result = []
        for bug in bugs:
            result.append(
                {
                    "id": bug.id,
                    "protocol": bug.protocol,
                    "bug_category": bug.bug_category,
                    "scenario_name": bug.scenario_name,
                    "status": bug.status,
                    "issue_url": bug.issue_url,
                }
            )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(result)} bugs:\n\n"
                    + json.dumps(result, indent=2, ensure_ascii=False),
                }
            ]
        }


def get_memory_tools_list(memory_tools: MemoryTools) -> list[dict[str, Any]]:
    """
    Get list of tool definitions for Claude Agent SDK.

    Args:
        memory_tools: MemoryTools instance to bind handlers to.

    Returns:
        List of tool definitions in the format expected by create_sdk_mcp_server.
    """
    tools = [
        # Pattern Memory
        {
            "name": "pattern_get",
            "description": "Get bug patterns for a protocol type. Use to find known vulnerability patterns that may apply.",
            "parameters": {
                "protocol_type": {
                    "type": "string",
                    "description": "Protocol type: 'cft' or 'bft'",
                },
                "not_tested_in": {
                    "type": "string",
                    "description": "Optional: exclude patterns already tested in this repo",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Optional: filter by 'safety', 'liveness', or 'agreement'",
                },
            },
            "handler": memory_tools.pattern_get,
        },
        {
            "name": "pattern_add",
            "description": "Add a new confirmed bug pattern to Pattern Memory for cross-protocol learning.",
            "parameters": {
                "protocol_type": {
                    "type": "string",
                    "description": "Protocol type: 'cft' or 'bft'",
                },
                "fault_type": {
                    "type": "string",
                    "description": "Type of fault that triggers this bug",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Category: 'safety', 'liveness', or 'agreement'",
                },
                "trigger_condition": {
                    "type": "string",
                    "description": "Description of what triggers the bug",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed explanation of the bug pattern",
                },
                "discovered_in_repo": {
                    "type": "string",
                    "description": "Repository where discovered",
                },
            },
            "handler": memory_tools.pattern_add,
        },
        {
            "name": "pattern_search",
            "description": "Search bug patterns by various criteria.",
            "parameters": {
                "protocol_type": {
                    "type": "string",
                    "description": "Optional: filter by 'cft' or 'bft'",
                },
                "fault_type": {
                    "type": "string",
                    "description": "Optional: filter by fault type",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Optional: filter by category",
                },
            },
            "handler": memory_tools.pattern_search,
        },
        {
            "name": "pattern_list",
            "description": "List all known bug patterns with summary info (pattern_id only). Call this first to see available patterns, then use pattern_get_detail for interesting ones.",
            "parameters": {
                "protocol_type": {
                    "type": "string",
                    "description": "Optional: filter by 'cft' or 'bft'",
                }
            },
            "handler": memory_tools.pattern_list,
        },
        {
            "name": "pattern_get_detail",
            "description": "Get full details of a specific bug pattern. Use pattern_list first to see available patterns.",
            "parameters": {
                "pattern_id": {
                    "type": "string",
                    "description": "The pattern_id to retrieve (required)",
                },
                "protocol_type": {
                    "type": "string",
                    "description": "Protocol type 'cft' or 'bft' (required)",
                },
            },
            "handler": memory_tools.pattern_get_detail,
        },
        # Repo Knowledge
        {
            "name": "repo_knowledge_get",
            "description": "Get cached knowledge about a repository's test structure, coding style, helpers, and lessons learned. Use compact=True for LLM-optimized summary.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "compact": {
                    "type": "boolean",
                    "description": "If True, return compact LLM-optimized summary (default: False)",
                },
            },
            "handler": memory_tools.repo_knowledge_get,
        },
        {
            "name": "repo_knowledge_save",
            "description": "Save or update basic repository knowledge. Use specific tools (add_helper, add_lesson, etc.) for incremental updates.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "language": {"type": "string", "description": "Programming language"},
                "package_name": {
                    "type": "string",
                    "description": "Package/module name",
                },
                "module_path": {
                    "type": "string",
                    "description": "Module path (e.g., github.com/xxx)",
                },
                "test_structure": {
                    "type": "object",
                    "description": "Test structure info",
                },
                "coding_style": {
                    "type": "object",
                    "description": "Coding style conventions",
                },
                "build_command": {"type": "string", "description": "Build command"},
                "test_command": {"type": "string", "description": "Test command"},
                "setup_boilerplate": {
                    "type": "string",
                    "description": "Common setup code",
                },
            },
            "handler": memory_tools.repo_knowledge_save,
        },
        {
            "name": "repo_knowledge_add_helper",
            "description": "Add or update a helper function with detailed signature, parameters, and usage example.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "name": {"type": "string", "description": "Function name"},
                "file": {"type": "string", "description": "File where defined"},
                "purpose": {"type": "string", "description": "What the function does"},
                "signature": {
                    "type": "string",
                    "description": "Full function signature",
                },
                "parameters": {
                    "type": "array",
                    "description": "List of parameter descriptions",
                },
                "usage_example": {
                    "type": "string",
                    "description": "Code example showing usage",
                },
                "returns": {
                    "type": "string",
                    "description": "Return value description",
                },
            },
            "handler": memory_tools.repo_knowledge_add_helper,
        },
        {
            "name": "repo_knowledge_add_lesson",
            "description": "Record a lesson learned after fixing a test issue. ALWAYS call this after fixing errors to help future test generation.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "issue": {
                    "type": "string",
                    "description": "What problem was encountered",
                },
                "solution": {"type": "string", "description": "How it was solved"},
                "related_files": {"type": "array", "description": "Related file paths"},
                "error_pattern": {
                    "type": "string",
                    "description": "Regex to match similar errors",
                },
            },
            "handler": memory_tools.repo_knowledge_add_lesson,
        },
        {
            "name": "repo_knowledge_find_lessons",
            "description": "Find lessons learned relevant to an error message. Call this FIRST when encountering errors.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "error_message": {
                    "type": "string",
                    "description": "The error message to find lessons for",
                },
            },
            "handler": memory_tools.repo_knowledge_find_lessons,
        },
        {
            "name": "repo_knowledge_add_template",
            "description": "Add a reusable test code template.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "name": {"type": "string", "description": "Template name"},
                "description": {
                    "type": "string",
                    "description": "Template description",
                },
                "template": {
                    "type": "string",
                    "description": "Code template with {{PLACEHOLDERS}}",
                },
                "placeholders": {
                    "type": "array",
                    "description": "List of placeholder names",
                },
            },
            "handler": memory_tools.repo_knowledge_add_template,
        },
        {
            "name": "repo_knowledge_add_key_type",
            "description": "Add a key type/interface important for testing.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"},
                "name": {"type": "string", "description": "Type name"},
                "file": {"type": "string", "description": "File where defined"},
                "kind": {
                    "type": "string",
                    "description": "struct, interface, or type_alias",
                },
                "purpose": {"type": "string", "description": "Brief description"},
                "key_methods": {
                    "type": "array",
                    "description": "Important method names",
                },
                "key_fields": {
                    "type": "array",
                    "description": "Important field names (for structs)",
                },
            },
            "handler": memory_tools.repo_knowledge_add_key_type,
        },
        {
            "name": "repo_knowledge_cleanup",
            "description": "Clean up duplicate data in repository knowledge.",
            "parameters": {
                "repo": {"type": "string", "description": "Repository name"}
            },
            "handler": memory_tools.repo_knowledge_cleanup,
        },
        # Test History
        {
            "name": "test_history_add",
            "description": "Record a test execution with results.",
            "parameters": {
                "protocol": {"type": "string", "description": "Protocol name"},
                "protocol_type": {"type": "string", "description": "'cft' or 'bft'"},
                "model": {
                    "type": "string",
                    "description": "LLM model used for test generation",
                },
                "scenario_name": {
                    "type": "string",
                    "description": "Test scenario name",
                },
                "test_name": {"type": "string", "description": "Test function name"},
                "test_passed": {
                    "type": "boolean",
                    "description": "Whether test passed",
                },
                "test_output": {"type": "string", "description": "Test output"},
                "is_real_bug": {
                    "type": "boolean",
                    "description": "Whether a real bug was found",
                },
            },
            "handler": memory_tools.test_history_add,
        },
        {
            "name": "test_history_get_stats",
            "description": "Get test history statistics.",
            "parameters": {
                "protocol": {
                    "type": "string",
                    "description": "Optional: filter by protocol",
                },
                "model": {
                    "type": "string",
                    "description": "Optional: filter by model",
                },
            },
            "handler": memory_tools.test_history_get_stats,
        },
        {
            "name": "test_history_get_bugs",
            "description": "Get confirmed bugs from test history.",
            "parameters": {
                "protocol": {
                    "type": "string",
                    "description": "Optional: filter by protocol",
                },
                "model": {
                    "type": "string",
                    "description": "Optional: filter by model",
                },
            },
            "handler": memory_tools.test_history_get_bugs,
        },
    ]

    return tools
