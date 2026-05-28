import pytest

from agent.memory.pattern_memory import BugPattern, PatternMemory


@pytest.mark.asyncio
async def test_pattern_memory_add_and_get(tmp_path):
    pm = PatternMemory(base_path=tmp_path)
    pattern = BugPattern(
        pattern_id="p1",
        protocol_type="cft",
        fault_type="network_partition",
        bug_category="liveness",
        trigger_condition="partition two nodes",
        description="liveness regression under partition",
        discovered_in_repo="demo/repo",
        test_template="go test ./...",
    )
    pid = await pm.add_pattern(pattern)
    assert pid

    patterns = await pm.get_patterns_for_protocol("cft")
    assert len(patterns) == 1
    got = patterns[0]
    assert got.fault_type == "network_partition"
    assert got.bug_category == "liveness"

    all_patterns = await pm.get_all_patterns()
    assert len(all_patterns) == 1

    # Files persisted under cft directory
    assert any((tmp_path / "cft").glob("*.json"))
