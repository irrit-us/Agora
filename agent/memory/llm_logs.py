"""
Agent Action Logger - Records agent planning and actions.

A concise logging system focused on:
- LLM thinking/planning process
- Tool calls (especially file operations)
- Key decision points

Does not record:
- Full prompts/messages
- Redundant metadata

Uses contextvars for thread-safe, asyncio-safe logger isolation, enabling
parallel execution of experiments with independent logging contexts.
"""

import contextvars
import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ActionLog(BaseModel):
    """Single action log entry."""

    time: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    action: (
        str  # thinking, tool_call, file_read, file_write, file_create, command, error
    )
    content: str  # Brief description
    detail: str | None = None  # Detailed info (e.g., reasoning content)


class ActionLogger:
    """
    Action logger for tracking agent behavior.

    Output format:
    [13:05:30] [THINKING] Need to read protocol file first...
    [13:05:31] [READ] protocol/consensus.go
    [13:05:32] [CREATE] protocol/consensus_race_test.go
    [13:05:33] [EXECUTE] go test -v ./protocol/...
    """

    # Action type to prefix mapping
    ICONS = {
        "thinking": "[THINKING]",
        "tool_call": "[TOOL]",
        "file_read": "[READ]",
        "file_write": "[WRITE]",
        "file_create": "[CREATE]",
        "command": "[CMD]",
        "success": "[OK]",
        "error": "[ERROR]",
        "warning": "[WARN]",
        "info": "[INFO]",
    }

    def __init__(self, base_path: Path | None = None, protocol: str = ""):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "test_history"
        self.base_path = Path(base_path)
        self.protocol = protocol
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_iteration = 0
        self._current_agent = ""

        # In-memory buffer for recent actions
        self._actions: list[ActionLog] = []
        self._max_memory = 100

        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure log directories exist."""
        if self.protocol:
            log_dir = self.base_path / self.protocol / "action_logs"
            log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self) -> Path:
        """Get the log file for current session."""
        if not self.protocol:
            return self.base_path / "action_logs" / f"session_{self._session_id}.log"
        return (
            self.base_path
            / self.protocol
            / "action_logs"
            / f"session_{self._session_id}.log"
        )

    def set_context(self, protocol: str = "", iteration: int = 0, agent_type: str = ""):
        """Set the current context."""
        if protocol:
            self.protocol = protocol
            self._ensure_dirs()
        if iteration:
            self._current_iteration = iteration
        if agent_type:
            self._current_agent = agent_type

    def _format_line(self, action: ActionLog) -> str:
        """Format a single log line."""
        icon = self.ICONS.get(action.action, "•")
        line = f"[{action.time}] {icon} {action.content}"
        return line

    def _write(self, action: ActionLog):
        """Write log entry."""
        # Add to memory
        self._actions.append(action)
        if len(self._actions) > self._max_memory:
            self._actions = self._actions[-self._max_memory :]

        # Write to file
        if not self.protocol:
            return

        log_file = self._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                line = self._format_line(action)
                f.write(line + "\n")
                # Write full detail if present (no truncation)
                if action.detail:
                    f.write("---\n")
                    f.write(action.detail + "\n")
                    f.write("---\n")
        except OSError:
            pass  # Don't let logging I/O errors crash the main process

    # ============================================================
    # Public logging methods
    # ============================================================

    def thinking(self, summary: str, reasoning: str | None = None):
        """Log LLM thinking process."""
        action = ActionLog(
            action="thinking",
            content=summary,  # No truncation
            detail=reasoning,
        )
        self._write(action)

    def tool_call(self, tool_name: str, args: dict):
        """Log tool call - clearly marked as TOOL CALL."""
        # Format args as readable JSON
        try:
            args_str = json.dumps(args, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            args_str = str(args)

        # Extract key info based on tool type for the summary line
        if tool_name in ("read_file", "ReadFile"):
            path = args.get("path") or args.get("file_path", "")
            self._write(
                ActionLog(action="file_read", content=f"[TOOL CALL] read_file: {path}")
            )
        elif tool_name in ("write_file", "WriteFile"):
            path = args.get("path") or args.get("file_path", "")
            self._write(
                ActionLog(
                    action="file_write",
                    content=f"[TOOL CALL] write_file: {path}",
                    detail=f"Content:\n{args.get('content') or args.get('contents', '')}",
                )
            )
        elif tool_name in ("create_file", "CreateFile"):
            path = args.get("path") or args.get("file_path", "")
            self._write(
                ActionLog(
                    action="file_create",
                    content=f"[TOOL CALL] create_file: {path}",
                    detail=f"Content:\n{args.get('content') or args.get('contents', '')}",
                )
            )
        elif tool_name in ("run_command", "RunCommand", "execute", "shell"):
            cmd = args.get("command") or args.get("cmd", "")
            self._write(
                ActionLog(action="command", content=f"[TOOL CALL] run_command: {cmd}")
            )
        elif tool_name in ("glob_files", "GlobFiles", "list_files"):
            pattern = args.get("pattern") or args.get("glob", "")
            self._write(
                ActionLog(
                    action="tool_call", content=f"[TOOL CALL] glob_files: {pattern}"
                )
            )
        else:
            # Generic tool call - show full args
            self._write(
                ActionLog(
                    action="tool_call",
                    content=f"[TOOL CALL] {tool_name}",
                    detail=f"Args:\n{args_str}",
                )
            )

    def tool_result(
        self, tool_name: str, success: bool, result_summary: str | None = None
    ):
        """Log tool execution result."""
        if result_summary:
            action_type = "success" if success else "error"
            self._write(
                ActionLog(
                    action=action_type,
                    content=f"[TOOL RESULT] {tool_name}: {result_summary}",
                )
            )

    def error(self, message: str):
        """Log error message."""
        self._write(ActionLog(action="error", content=message))

    def warning(self, message: str):
        """Log warning message."""
        self._write(ActionLog(action="warning", content=message))

    def info(self, message: str):
        """Log general information."""
        self._write(ActionLog(action="info", content=message))

    def iteration_start(self, iteration: int):
        """Log iteration start."""
        self._current_iteration = iteration
        self._write(
            ActionLog(action="info", content=f"=== Iteration {iteration} Start ===")
        )

    def iteration_end(self, iteration: int, result: str):
        """Log iteration end."""
        self._write(
            ActionLog(
                action="info", content=f"=== Iteration {iteration} End: {result} ==="
            )
        )

    def get_recent_actions(self, limit: int = 20) -> list[ActionLog]:
        """Get recent action logs."""
        return self._actions[-limit:]


# ============================================================
# Context-aware instance management for parallel execution
# ============================================================

# Context variables for logger isolation - each asyncio task can have its own loggers
_action_logger_ctx: contextvars.ContextVar[ActionLogger | None] = contextvars.ContextVar(
    "_action_logger_ctx", default=None
)


def get_action_logger() -> ActionLogger:
    """
    Get action logger for current context.
    
    In parallel execution, each asyncio task has its own logger.
    Creates a default logger if none exists in current context.
    """
    logger = _action_logger_ctx.get()
    if logger is None:
        logger = ActionLogger()
        _action_logger_ctx.set(logger)
    return logger


def set_action_logger(logger: ActionLogger) -> contextvars.Token:
    """
    Set action logger for current context.
    
    Args:
        logger: The ActionLogger instance to set.
        
    Returns:
        Token that can be used to reset to previous value.
    """
    return _action_logger_ctx.set(logger)


def reset_action_logger(token: contextvars.Token) -> None:
    """
    Reset action logger to previous value.
    
    Args:
        token: Token returned by set_action_logger().
    """
    try:
        _action_logger_ctx.reset(token)
    except ValueError:
        # Token was already reset or context changed
        pass


def create_action_logger(
    protocol: str, base_path: Path | None = None
) -> tuple[ActionLogger, contextvars.Token]:
    """
    Create and set action logger for current context.
    
    Args:
        protocol: Protocol name for log organization.
        base_path: Base path for log files.
        
    Returns:
        Tuple of (logger, token) where token can be used for cleanup.
    """
    logger = ActionLogger(base_path=base_path, protocol=protocol)
    token = set_action_logger(logger)
    return logger, token


# ============================================================
# LLMLogger - Wrapper for backward compatibility
#
# These classes bridge the old LLM logging interface to the new
# ActionLogger system. They are used by orchestrator.py and will
# be maintained for API stability.
# ============================================================


class LLMLogEntry(BaseModel):
    """Log entry model for LLM interactions."""

    timestamp: str
    event_type: str
    model: str
    messages: list[dict] | None = None
    message_count: int | None = None
    response: str | None = None
    response_length: int | None = None
    duration_ms: int = 0
    tokens_used: int = 0
    error: str | None = None


class LLMLogger:
    """
    LLM interaction logger that bridges to ActionLogger.

    This class provides the logging interface used by ToolAgent callbacks.
    It filters and forwards relevant log entries to ActionLogger.
    """

    def __init__(self, base_path: Path | None = None, protocol: str = ""):
        self._action_logger = ActionLogger(base_path=base_path, protocol=protocol)
        self._pending_request: LLMLogEntry | None = None

    def set_context(self, protocol: str = "", iteration: int = 0, agent_type: str = ""):
        """Set logging context for correlation."""
        self._action_logger.set_context(
            protocol=protocol, iteration=iteration, agent_type=agent_type
        )

    def log(self, entry: dict):
        """
        Log an LLM interaction entry.

        Args:
            entry: Dict with event_type, model, response, etc.
        """
        try:
            log_entry = LLMLogEntry(**entry)

            if log_entry.event_type == "llm_request":
                self._pending_request = log_entry
            elif log_entry.event_type == "llm_response":
                # Only log if there's actual content
                if log_entry.response:
                    # Extract first meaningful line as summary
                    lines = [
                        l.strip() for l in log_entry.response.split("\n") if l.strip()
                    ]
                    if lines:
                        summary = lines[0][:100]
                        self._action_logger.thinking(f"LLM Response: {summary}")
                self._pending_request = None
        except Exception as e:
            # Log parsing errors at debug level, don't crash
            logging.getLogger(__name__).debug(f"LLMLogger.log error: {e}")


# Context variable for LLMLogger isolation
_llm_logger_ctx: contextvars.ContextVar[LLMLogger | None] = contextvars.ContextVar(
    "_llm_logger_ctx", default=None
)


def get_llm_logger() -> LLMLogger:
    """
    Get LLMLogger for current context.
    
    In parallel execution, each asyncio task has its own logger.
    Creates a default logger if none exists in current context.
    """
    logger = _llm_logger_ctx.get()
    if logger is None:
        logger = LLMLogger()
        _llm_logger_ctx.set(logger)
    return logger


def set_llm_logger(logger: LLMLogger) -> contextvars.Token:
    """
    Set LLMLogger for current context.
    
    Args:
        logger: The LLMLogger instance to set.
        
    Returns:
        Token that can be used to reset to previous value.
    """
    return _llm_logger_ctx.set(logger)


def reset_llm_logger(token: contextvars.Token) -> None:
    """
    Reset LLMLogger to previous value.
    
    Args:
        token: Token returned by set_llm_logger().
    """
    try:
        _llm_logger_ctx.reset(token)
    except ValueError:
        # Token was already reset or context changed
        pass


class LoggerContext:
    """
    Context manager for isolated logging in parallel execution.
    
    Usage:
        async with LoggerContext(protocol="raft") as ctx:
            # All logging in this context is isolated
            logger = get_action_logger()
            logger.info("This goes to raft-specific log")
    """
    
    def __init__(self, protocol: str, base_path: Path | None = None):
        self.protocol = protocol
        self.base_path = base_path
        self._action_token: contextvars.Token | None = None
        self._llm_token: contextvars.Token | None = None
        self._callback_token: contextvars.Token | None = None
        self.action_logger: ActionLogger | None = None
        self.llm_logger: LLMLogger | None = None
    
    def __enter__(self) -> "LoggerContext":
        from ..llm import set_llm_log_callback
        
        # Create isolated loggers
        self.action_logger = ActionLogger(base_path=self.base_path, protocol=self.protocol)
        self.llm_logger = LLMLogger(base_path=self.base_path, protocol=self.protocol)
        
        # Set context variables
        self._action_token = set_action_logger(self.action_logger)
        self._llm_token = set_llm_logger(self.llm_logger)
        self._callback_token = set_llm_log_callback(self.llm_logger.log)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        from ..llm import reset_llm_log_callback
        
        # Reset context variables
        if self._callback_token is not None:
            reset_llm_log_callback(self._callback_token)
        if self._llm_token is not None:
            reset_llm_logger(self._llm_token)
        if self._action_token is not None:
            reset_action_logger(self._action_token)
        
        return False
    
    async def __aenter__(self) -> "LoggerContext":
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def create_llm_logger(protocol: str, base_path: Path | None = None) -> LLMLogger:
    """
    Create and configure an LLMLogger for a protocol.

    This also sets up the ActionLogger and registers the LLM log callback
    in the current context.

    Note: In parallel execution, prefer using LoggerContext instead.

    Args:
        protocol: Protocol name for log organization.
        base_path: Base path for log files.

    Returns:
        Configured LLMLogger instance.
    """
    from ..llm import set_llm_log_callback

    llm_logger = LLMLogger(base_path=base_path, protocol=protocol)
    set_llm_logger(llm_logger)

    # Also create action logger
    create_action_logger(protocol=protocol, base_path=base_path)

    # Set up unified callback for current context
    set_llm_log_callback(llm_logger.log)

    return llm_logger
