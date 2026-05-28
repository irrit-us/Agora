"""
Agent Factory - Creates Strategy and TestGen agents with their tools.

This module extracts agent creation logic from Orchestrator for cleaner
separation of concerns.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ..memory.repo_knowledge import HelperFunction
from ..prompts import STRATEGY_SYSTEM_PROMPT, get_testgen_system_prompt
from .tool_agent import Tool, ToolAgent, create_tool

if TYPE_CHECKING:
    from ..mcp_servers.memory_server import MemoryServer
    from .executor import Executor

logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
DEFAULT_STRATEGY_TIMEOUT = 120.0
DEFAULT_TESTGEN_TIMEOUT = 180.0

# Output truncation limits (in characters)
MAX_OUTPUT_LENGTH = 4000


class AgentFactory:
    """
    Factory for creating Strategy and TestGen agents with their tools.
    
    Extracts agent creation logic from Orchestrator for cleaner code organization.
    """
    
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        max_tokens: int,
        repo_root: Path,
        executor: "Executor",
        memory: "MemoryServer",
        protocol_name: str,
        protocol_type: str,
        protocol_language: str,
        log_callback: Callable[[dict], None] | None = None,
        metrics_callback: Callable[[dict], None] | None = None,
    ):
        """
        Initialize the AgentFactory.
        
        Args:
            model: LLM model name.
            api_key: API key.
            base_url: API base URL.
            max_tokens: Max output tokens.
            repo_root: Repository root path.
            executor: Command executor.
            memory: Memory server instance.
            protocol_name: Protocol name.
            protocol_type: Protocol type (cft/bft).
            protocol_language: Programming language.
            log_callback: Optional LLM logging callback.
            metrics_callback: Optional callback for per-API-call metrics recording.
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.repo_root = repo_root
        self.executor = executor
        self.memory = memory
        self.protocol_name = protocol_name
        self.protocol_type = protocol_type
        self.protocol_language = protocol_language
        self.log_callback = log_callback
        self.metrics_callback = metrics_callback
        
        # Pattern usage tracking callbacks (set by Orchestrator)
        self._mark_pattern_viewed: Callable[[str, str], None] | None = None
        self._is_pattern_used: Callable[[str, str], bool] | None = None
    
    def set_pattern_callbacks(
        self,
        mark_viewed: Callable[[str, str], None],
        is_used: Callable[[str, str], bool],
    ) -> None:
        """Set pattern usage tracking callbacks."""
        self._mark_pattern_viewed = mark_viewed
        self._is_pattern_used = is_used
    
    def create_strategy_agent(self) -> ToolAgent:
        """
        Create the Strategy Agent.

        Responsibilities:
        - Generate ORIGINAL attack strategies
        - Can query bug pattern details on demand
        - Independent context (doesn't see code)
        - Focus on creative vulnerability hypotheses
        """
        tools = self._build_strategy_tools()

        return ToolAgent(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            system_prompt=STRATEGY_SYSTEM_PROMPT,
            tools=tools,
            max_tokens=self.max_tokens,
            timeout=DEFAULT_STRATEGY_TIMEOUT,
            log_callback=self.log_callback,
            metrics_callback=self.metrics_callback,
        )

    def _build_strategy_tools(self) -> list[Tool]:
        """
        Build tools for the Strategy Agent.

        Currently only provides get_pattern_details for on-demand
        bug pattern information retrieval.
        """
        factory = self

        async def get_pattern_details(pattern_id: str) -> str:
            """
            Get detailed information about a specific bug pattern.

            Use this to learn more about a pattern before deciding whether to use it
            as inspiration for your attack scenario.

            Args:
                pattern_id: The exact pattern ID from the pattern list.

            Returns:
                Detailed pattern information including description, trigger conditions,
                and lessons learned. Also indicates if this pattern was already used.
            """
            protocol_name = factory.protocol_name
            protocol_type = factory.protocol_type

            # Try to find pattern in both CFT and BFT
            pattern = await factory.memory.pattern_memory.get_pattern(
                pattern_id, protocol_type
            )
            if not pattern and protocol_type == "bft":
                # BFT can also use CFT patterns
                pattern = await factory.memory.pattern_memory.get_pattern(
                    pattern_id, "cft"
                )

            if not pattern:
                return f"Pattern not found: {pattern_id}\n\nMake sure to use the exact pattern_id from the list."

            # Mark as viewed
            if factory._mark_pattern_viewed:
                factory._mark_pattern_viewed(protocol_name, pattern_id)

            # Check if already used
            is_used = False
            if factory._is_pattern_used:
                is_used = factory._is_pattern_used(protocol_name, pattern_id)

            # Build detailed response
            lines = [
                f"## Pattern Details: {pattern_id}",
                "",
            ]

            if is_used:
                lines.extend([
                    "⚠️ WARNING: This pattern was already used to generate a strategy for this repository.",
                    "If you use it again, you MUST create a SUBSTANTIALLY DIFFERENT attack vector.",
                    "",
                ])

            lines.extend([
                f"**Protocol Type**: {pattern.protocol_type.upper()}",
                f"**Bug Category**: {pattern.bug_category or 'N/A'}",
                f"**Fault Type**: {pattern.fault_type or 'N/A'}",
                "",
            ])

            if pattern.trigger_condition:
                lines.extend([
                    "**Trigger Condition**:",
                    pattern.trigger_condition,
                    "",
                ])

            if pattern.description:
                lines.extend([
                    "**Description**:",
                    pattern.description,
                    "",
                ])

            if pattern.discovered_in_repo:
                lines.append(f"**Discovered In**: {pattern.discovered_in_repo}")

            if pattern.tags:
                lines.append(f"**Tags**: {', '.join(pattern.tags)}")

            return "\n".join(lines)

        return [
            create_tool(
                get_pattern_details,
                name="get_pattern_details",
                description="Get detailed information about a specific bug pattern by its pattern_id",
            ),
        ]

    def create_testgen_agent(self) -> ToolAgent:
        """
        Create the TestGen Agent.

        Responsibilities:
        - Read and analyze repository code
        - Write test files
        - Execute tests and fix errors
        - Record learnings
        """
        testgen_prompt = get_testgen_system_prompt(self.protocol_language)
        tools = self._build_testgen_tools()

        return ToolAgent(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            system_prompt=testgen_prompt,
            tools=tools,
            max_tokens=self.max_tokens,
            timeout=DEFAULT_TESTGEN_TIMEOUT,
            log_callback=self.log_callback,
            metrics_callback=self.metrics_callback,
        )

    def _build_testgen_tools(self) -> list[Tool]:
        """
        Build tools for the TestGen Agent.

        Direct file access - no virtual path abstraction.
        """
        factory = self
        repo_root = self.repo_root

        async def read_file(path: str, start: int = 0, length: int = 4000) -> str:
            """
            Read file content from the repository.
            Path is relative to repository root.
            """
            try:
                start = int(start) if start is not None else 0
                length = int(length) if length is not None else 4000

                path_clean = path.lstrip("/")
                file_path = repo_root / path_clean

                if not file_path.exists():
                    return f"File not found: {path} (looked at: {file_path})"

                text = file_path.read_text(errors="replace")
                return text[start : start + length] if length else text
            except (OSError, IOError) as e:
                logger.error(f"[read_file] IO error reading {path}: {e}")
                return f"Read error: {e}"
            except UnicodeDecodeError as e:
                logger.error(f"[read_file] Encoding error reading {path}: {e}")
                return f"Encoding error: {e}"

        async def write_file(path: str, content: str) -> str:
            """
            Write content to a file in the repository.
            Path is relative to repository root.
            """
            if not isinstance(content, str):
                return (
                    f"Error: content must be a plain string, got {type(content).__name__}. "
                    "Pass the full file content as a single string, not a dict or list."
                )
            try:
                path_clean = path.lstrip("/")
                file_path = repo_root / path_clean

                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                return f"Written {len(content)} bytes to {file_path.relative_to(repo_root)}"
            except (OSError, IOError) as e:
                logger.error(f"[write_file] IO error writing {path}: {e}")
                return f"Write error: {e}"
            except PermissionError as e:
                logger.error(f"[write_file] Permission denied for {path}: {e}")
                return f"Permission error: {e}"

        async def run_command(command: str) -> str:
            """
            Execute a shell command in the repository.

            IMPORTANT: Each command runs in a fresh subprocess at repo_root.
            The 'cd' command does NOT persist between calls.

            Good: run_command("cd src && ls")      # Works, cd only affects this command
            Bad:  run_command("cd src") then run_command("ls")  # ls still runs at repo_root
            """
            result = await factory.executor.execute_command(command, cwd=repo_root)
            output = result.output or ""
            if result.error:
                output += f"\nError: {result.error}"
            return output[:MAX_OUTPUT_LENGTH] + ("...(truncated)" if len(output) > MAX_OUTPUT_LENGTH else "")

        async def repo_knowledge(compact: bool = True) -> str:
            """
            Get cached knowledge about the repository's test structure.

            Args:
                compact: If True (default), return LLM-optimized summary.
            """
            try:
                repo_name = factory.protocol_name.lower()

                if compact:
                    summary = await factory.memory.repo_knowledge.get_compact_summary(repo_name)
                    if summary:
                        return summary
                    return f"No repository knowledge cached for '{repo_name}'."
                else:
                    knowledge = await factory.memory.repo_knowledge.get(repo_name)
                    if knowledge:
                        return json.dumps(knowledge.model_dump(), indent=2, default=str)
                    return f"No repository knowledge cached for '{repo_name}'."
            except (OSError, IOError) as e:
                logger.error(f"[repo_knowledge] IO error: {e}")
                return f"Error reading repo knowledge: {e}"
            except json.JSONDecodeError as e:
                logger.error(f"[repo_knowledge] JSON decode error: {e}")
                return f"Error parsing repo knowledge: {e}"

        async def repo_knowledge_find_lessons(error_message: str) -> str:
            """
            Find lessons learned that might help fix an error.
            CALL THIS FIRST when encountering compilation or test errors.
            """
            try:
                repo_name = factory.protocol_name.lower()
                knowledge = await factory.memory.repo_knowledge.get(repo_name)
                if not knowledge:
                    return f"No repository knowledge found for '{repo_name}'."

                relevant = knowledge.find_relevant_lessons(error_message)
                if not relevant:
                    return "No relevant lessons found. This might be a new issue."

                result = []
                for lesson in relevant:
                    result.append(
                        f"**Issue**: {lesson.issue}\n**Solution**: {lesson.solution}"
                    )

                return (
                    f"Found {len(result)} relevant lessons:\n\n"
                    + "\n\n---\n\n".join(result)
                )
            except (OSError, IOError) as e:
                return f"Error reading lessons: {e}"
            except json.JSONDecodeError as e:
                return f"Error parsing lessons data: {e}"

        async def repo_knowledge_add_lesson(
            issue: str, solution: str, error_pattern: str = ""
        ) -> str:
            """
            Record a lesson learned after fixing an error.
            ALWAYS CALL THIS after successfully fixing a test issue.
            """
            try:
                repo_name = factory.protocol_name.lower()
                await factory.memory.repo_knowledge.add_lesson_learned(
                    repo=repo_name,
                    issue=issue,
                    solution=solution,
                    error_pattern=error_pattern if error_pattern else None,
                )
                return f"Successfully recorded lesson: {issue[:50]}..."
            except (OSError, IOError) as e:
                return f"Error saving lesson: {e}"
            except json.JSONDecodeError as e:
                return f"Error parsing knowledge file: {e}"

        async def repo_knowledge_add_helper(
            name: str,
            file: str,
            purpose: str,
            signature: str = "",
            usage_example: str = "",
            returns: str = "",
        ) -> str:
            """
            Add or update a helper function with detailed information.
            Call this when you discover a useful helper function.
            """
            try:
                repo_name = factory.protocol_name.lower()

                helper = HelperFunction(
                    name=name,
                    file=file,
                    purpose=purpose,
                    signature=signature if signature else None,
                    usage_example=usage_example if usage_example else None,
                    returns=returns if returns else None,
                )

                updated = await factory.memory.repo_knowledge.update_helper_details(
                    repo=repo_name,
                    helper_name=name,
                    signature=signature if signature else None,
                    usage_example=usage_example if usage_example else None,
                    returns=returns if returns else None,
                )

                if not updated:
                    await factory.memory.repo_knowledge.update_helpers(repo_name, [helper])

                return f"Successfully {'updated' if updated else 'added'} helper: {name}"
            except (OSError, IOError) as e:
                return f"Error saving helper: {e}"
            except json.JSONDecodeError as e:
                return f"Error parsing knowledge file: {e}"

        async def glob_files(pattern: str = "**/*") -> str:
            """List files matching a glob pattern in the repository."""
            try:
                files = [
                    str(p.relative_to(repo_root)) for p in repo_root.glob(pattern)
                ][:100]
                return "\n".join(files) if files else "(no files found)"
            except (OSError, IOError) as e:
                return f"Error accessing files: {e}"
            except ValueError as e:
                return f"Invalid glob pattern: {e}"

        return [
            create_tool(read_file, name="read_file", description="Read file content from the repository"),
            create_tool(write_file, name="write_file", description="Write content to a file in the repository"),
            create_tool(run_command, name="run_command", description="Execute a shell command in the repository"),
            create_tool(repo_knowledge, name="repo_knowledge", description="Get cached knowledge about the repository"),
            create_tool(repo_knowledge_find_lessons, name="repo_knowledge_find_lessons", description="Find lessons that might help fix an error"),
            create_tool(repo_knowledge_add_lesson, name="repo_knowledge_add_lesson", description="Record a lesson learned after fixing an error"),
            create_tool(repo_knowledge_add_helper, name="repo_knowledge_add_helper", description="Add or update a helper function"),
            create_tool(glob_files, name="glob_files", description="List files matching a glob pattern"),
        ]
