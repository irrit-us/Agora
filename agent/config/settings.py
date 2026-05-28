"""
Configuration module - loads settings from root .env file
Supports Claude Agent SDK configuration
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


@dataclass
class ProtocolConfig:
    """Configuration for a protocol"""

    name: str
    path: str
    type: str  # "cft" or "bft"
    language: str
    fault_tolerance: str  # e.g., "(n-1)/2"
    description: str = ""
    test_pattern: str = "*_test.go"
    test_command: str = ""


class Settings(BaseSettings):
    """Application settings loaded from .env file"""

    # OpenRouter LLM
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )
    llm_model: str = Field(
        default="anthropic/claude-sonnet-4", description="LLM model to use"
    )

    # Extended Thinking
    max_thinking_tokens: int = Field(
        default=32000, description="Maximum tokens for Claude's extended thinking"
    )

    # Prompt Caching
    enable_prompt_caching: bool = Field(
        default=True, description="Enable OpenRouter prompt caching"
    )

    # Agent Settings
    max_reflection_retries: int = Field(
        default=5, description="Maximum retries for self-healing reflection loop"
    )
    max_turns: int = Field(
        default=10, description="Maximum conversation turns per agent call"
    )
    max_budget_usd: float = Field(
        default=10.0, description="Maximum budget per session in USD"
    )
    max_strategy_retries: int = Field(
        default=10,
        description="Maximum retries for generating unique attack strategies",
    )
    max_testgen_iterations: int = Field(
        default=1000,
        description="Maximum iterations for TestGen agent tool calling loop",
    )
    max_bug_exploitation_attempts: int = Field(
        default=5,
        description="Maximum attempts to exploit a discovered bug for finding similar vulnerabilities",
    )

    # Test Settings
    test_timeout: int = Field(
        default=300, description="Test execution timeout in seconds"
    )

    # Embedding
    use_embedding: bool = Field(
        default=False,
        description="Whether to use embedding for semantic search (costs extra API calls)",
    )
    embedding_model: str = Field(
        default="openai/text-embedding-3-small", description="Embedding model to use"
    )

    # Memory settings
    max_context_tokens: int = Field(
        default=100000, description="Maximum tokens for context"
    )
    embedding_top_k: int = Field(
        default=15, description="Number of similar items to retrieve"
    )
    short_term_retention_days: int = Field(
        default=7, description="Days to keep short-term memory before summarization"
    )

    # Protocols (loaded separately from YAML)
    protocols: dict[str, ProtocolConfig] = Field(default_factory=dict)

    class Config:
        env_file = Path(__file__).parent.parent.parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def load_protocols(config_path: Path | None = None) -> dict[str, ProtocolConfig]:
    """Load protocol configurations from YAML file"""
    if config_path is None:
        config_path = Path(__file__).parent / "protocols.yaml"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        data = yaml.safe_load(f)

    protocols = {}
    for name, config in data.get("protocols", {}).items():
        protocols[name] = ProtocolConfig(
            name=name,
            path=config.get("path", f"./{name}"),
            type=config.get("type", "cft"),
            language=config.get("language", "go"),
            fault_tolerance=config.get("fault_tolerance", "(n-1)/2"),
            description=config.get("description", ""),
            test_pattern=config.get("test_pattern", "*_test.go"),
            test_command=config.get(
                "test_command", "go test -v -run {test_name} ./..."
            ),
        )

    return protocols


def load_settings() -> Settings:
    """Load settings from environment and config files"""
    settings = Settings()
    settings.protocols = load_protocols()
    return settings


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create settings instance"""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
