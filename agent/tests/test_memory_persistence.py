from pathlib import Path

import pytest

from agent.mcp_servers.memory_server import create_memory_server
from agent.memory.repo_knowledge import HelperFunction, RepoKnowledge, RepoKnowledgeData


@pytest.mark.asyncio
async def test_repo_knowledge_persists(tmp_path: Path):
    repo = RepoKnowledge(base_path=tmp_path)
    data = RepoKnowledgeData(
        repo="demo/repo",
        language="go",
        helper_functions=[HelperFunction(name="h1", file="f.go", purpose="p")],
        file_hashes={"f.go": "abc"},
    )
    await repo.save(data)

    loaded = await repo.get("demo/repo")
    assert loaded is not None
    assert loaded.language == "go"
    assert loaded.helper_functions[0].name == "h1"

    # Update helpers merges without duplication
    await repo.update_helpers(
        "demo/repo",
        [
            HelperFunction(name="h1", file="f.go", purpose="p"),
            HelperFunction(name="h2", file="g.go", purpose="q"),
        ],
    )
    loaded2 = await repo.get("demo/repo")
    names = {h.name for h in loaded2.helper_functions}
    assert names == {"h1", "h2"}

    # needs_update returns True when hashes change
    assert await repo.needs_update("demo/repo", {"f.go": "changed"})


def test_create_memory_server_persists_paths(tmp_path: Path):
    server = create_memory_server(base_path=tmp_path, api_key=None)
    # All components should be initialized and their storage paths created
    assert server.pattern_memory is not None
    assert server.repo_knowledge is not None
    assert server.test_history is not None
    assert (tmp_path / "data" / "pattern_memory").exists()
    assert (tmp_path / "data" / "repo_knowledge").exists()
    assert (tmp_path / "data" / "test_history").exists()
