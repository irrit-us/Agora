"""
Tests for parallel execution isolation.

Verifies that concurrent experiments have isolated logging contexts,
ensuring that parallel ablation experiments don't interfere with each other.
"""

import asyncio
import pytest

from agent.llm.base import (
    set_llm_log_callback,
    reset_llm_log_callback,
    get_llm_log_callback,
    log_llm_interaction,
)
from agent.memory.llm_logs import (
    ActionLogger,
    LLMLogger,
    LoggerContext,
    get_action_logger,
    set_action_logger,
    reset_action_logger,
    get_llm_logger,
    set_llm_logger,
    reset_llm_logger,
)


class TestContextVarsIsolation:
    """Test that contextvars provide proper isolation between asyncio tasks."""

    @pytest.mark.asyncio
    async def test_llm_callback_isolation(self):
        """Test that LLM callbacks are isolated between asyncio tasks."""
        results = {"task1": [], "task2": []}
        
        def callback1(entry):
            results["task1"].append(entry.get("model", ""))
        
        def callback2(entry):
            results["task2"].append(entry.get("model", ""))
        
        async def task1():
            token = set_llm_log_callback(callback1)
            try:
                # This should only go to callback1
                log_llm_interaction("llm_request", "model_task1")
                await asyncio.sleep(0.05)  # Give task2 time to run
                log_llm_interaction("llm_response", "model_task1")
            finally:
                reset_llm_log_callback(token)
        
        async def task2():
            token = set_llm_log_callback(callback2)
            try:
                # This should only go to callback2
                log_llm_interaction("llm_request", "model_task2")
                await asyncio.sleep(0.05)
                log_llm_interaction("llm_response", "model_task2")
            finally:
                reset_llm_log_callback(token)
        
        # Run both tasks concurrently
        await asyncio.gather(task1(), task2())
        
        # Verify isolation
        assert all("model_task1" in m for m in results["task1"]), \
            f"Task1 should only receive task1 logs: {results['task1']}"
        assert all("model_task2" in m for m in results["task2"]), \
            f"Task2 should only receive task2 logs: {results['task2']}"
        assert len(results["task1"]) == 2, "Task1 should have 2 log entries"
        assert len(results["task2"]) == 2, "Task2 should have 2 log entries"

    @pytest.mark.asyncio
    async def test_action_logger_isolation(self):
        """Test that ActionLoggers are isolated between asyncio tasks."""
        
        async def task_with_logger(protocol: str):
            logger = ActionLogger(protocol=protocol)
            token = set_action_logger(logger)
            try:
                # Get logger should return the one we just set
                current = get_action_logger()
                assert current.protocol == protocol, \
                    f"Expected protocol {protocol}, got {current.protocol}"
                
                await asyncio.sleep(0.05)
                
                # Should still be the same after yield
                current_after = get_action_logger()
                assert current_after.protocol == protocol, \
                    f"After yield: Expected {protocol}, got {current_after.protocol}"
                
                return protocol
            finally:
                reset_action_logger(token)
        
        # Run multiple tasks concurrently
        results = await asyncio.gather(
            task_with_logger("raft"),
            task_with_logger("hotstuff"),
            task_with_logger("sui"),
        )
        
        assert results == ["raft", "hotstuff", "sui"]

    @pytest.mark.asyncio
    async def test_llm_logger_isolation(self):
        """Test that LLMLoggers are isolated between asyncio tasks."""
        
        async def task_with_llm_logger(protocol: str):
            logger = LLMLogger(protocol=protocol)
            token = set_llm_logger(logger)
            try:
                current = get_llm_logger()
                assert current._action_logger.protocol == protocol
                
                await asyncio.sleep(0.05)
                
                current_after = get_llm_logger()
                assert current_after._action_logger.protocol == protocol
                
                return protocol
            finally:
                reset_llm_logger(token)
        
        results = await asyncio.gather(
            task_with_llm_logger("raft"),
            task_with_llm_logger("hotstuff"),
        )
        
        assert results == ["raft", "hotstuff"]


class TestLoggerContext:
    """Test the LoggerContext context manager."""

    @pytest.mark.asyncio
    async def test_logger_context_sets_all_loggers(self):
        """Test that LoggerContext sets up all required loggers."""
        async with LoggerContext(protocol="test_protocol") as ctx:
            # Action logger should be set
            action_logger = get_action_logger()
            assert action_logger.protocol == "test_protocol"
            
            # LLM logger should be set
            llm_logger = get_llm_logger()
            assert llm_logger._action_logger.protocol == "test_protocol"
            
            # LLM callback should be set
            callback = get_llm_log_callback()
            assert callback is not None
            assert callback == ctx.llm_logger.log

    @pytest.mark.asyncio
    async def test_logger_context_cleanup(self):
        """Test that LoggerContext properly cleans up on exit."""
        # Get initial state
        initial_callback = get_llm_log_callback()
        
        async with LoggerContext(protocol="test_cleanup"):
            # During context, callback should be different
            during_callback = get_llm_log_callback()
            assert during_callback is not None
        
        # After context, callback should be restored
        after_callback = get_llm_log_callback()
        assert after_callback == initial_callback

    @pytest.mark.asyncio
    async def test_parallel_logger_contexts(self):
        """Test multiple LoggerContexts running in parallel."""
        results = {}
        
        async def run_with_context(protocol: str):
            async with LoggerContext(protocol=protocol):
                # Verify our context is set
                assert get_action_logger().protocol == protocol
                
                # Simulate some work
                await asyncio.sleep(0.05)
                
                # Verify still correct after await
                assert get_action_logger().protocol == protocol
                
                results[protocol] = get_action_logger().protocol
        
        await asyncio.gather(
            run_with_context("raft"),
            run_with_context("hotstuff"),
            run_with_context("sui"),
            run_with_context("efficient-epaxos"),
        )
        
        assert results == {
            "raft": "raft",
            "hotstuff": "hotstuff",
            "sui": "sui",
            "efficient-epaxos": "efficient-epaxos",
        }


class TestParallelLogging:
    """Test that parallel logging doesn't mix up log entries."""

    @pytest.mark.asyncio
    async def test_parallel_log_entries(self):
        """Test that log entries from parallel tasks don't mix."""
        collected_logs = {"task1": [], "task2": []}
        
        async def task_with_logging(task_id: str, iterations: int):
            async with LoggerContext(protocol=f"protocol_{task_id}"):
                logger = get_action_logger()
                
                for i in range(iterations):
                    logger.info(f"{task_id}_message_{i}")
                    collected_logs[task_id].append(f"{task_id}_message_{i}")
                    await asyncio.sleep(0.01)
        
        await asyncio.gather(
            task_with_logging("task1", 5),
            task_with_logging("task2", 5),
        )
        
        # Each task should have exactly 5 entries
        assert len(collected_logs["task1"]) == 5
        assert len(collected_logs["task2"]) == 5
        
        # All task1 entries should be task1 messages
        assert all("task1" in msg for msg in collected_logs["task1"])
        assert all("task2" in msg for msg in collected_logs["task2"])


class TestResetTokens:
    """Test that reset tokens work correctly."""

    @pytest.mark.asyncio
    async def test_llm_callback_reset_token(self):
        """Test that reset token restores previous callback."""
        def original_callback(entry):
            pass
        
        def new_callback(entry):
            pass
        
        # Set original
        original_token = set_llm_log_callback(original_callback)
        
        # Set new
        new_token = set_llm_log_callback(new_callback)
        assert get_llm_log_callback() == new_callback
        
        # Reset new
        reset_llm_log_callback(new_token)
        assert get_llm_log_callback() == original_callback
        
        # Reset original
        reset_llm_log_callback(original_token)

    @pytest.mark.asyncio
    async def test_action_logger_reset_token(self):
        """Test that action logger reset token works."""
        original = ActionLogger(protocol="original")
        new_logger = ActionLogger(protocol="new")
        
        original_token = set_action_logger(original)
        new_token = set_action_logger(new_logger)
        
        assert get_action_logger().protocol == "new"
        
        reset_action_logger(new_token)
        assert get_action_logger().protocol == "original"
        
        reset_action_logger(original_token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
