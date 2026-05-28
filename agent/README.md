# Consensus Bug Hunter Agent

A multi-agent system for automatically discovering bugs in distributed consensus protocol implementations.

## Architecture

```
agent/
├── core/                   # Core agent framework
│   ├── orchestrator.py     # Main workflow controller (~800 lines)
│   ├── agent_factory.py    # Creates agents with their tools
│   ├── pattern_tracker.py  # Tracks bug pattern usage per protocol
│   ├── tool_agent.py       # Self-built tool-calling agent
│   ├── executor.py         # Code and command executor
│   ├── prompt_builder.py   # Centralized prompt construction
│   ├── result_parser.py    # LLM response parsing logic
│   ├── report_generator.py # Bug report generation
│   ├── strategies.py       # Strategy interfaces & data types
│   └── strategy_impl.py    # Strategy implementations (default, random, exploitation)
├── ablation/               # Ablation experiment framework
│   ├── base.py             # Base experiment class
│   ├── runner.py           # CLI runner for experiments
│   └── experiments/        # 7 experiment implementations
├── llm/                    # LLM API clients
│   ├── base.py             # Common logging utilities
│   ├── openrouter.py       # OpenRouter API client
│   └── deepseek.py         # DeepSeek Reasoner client
├── memory/               # Persistent memory modules
│   ├── pattern_memory.py # Bug pattern storage (CFT/BFT)
│   ├── repo_knowledge.py # Repository test structure cache
│   ├── test_history.py   # Test execution records
│   └── llm_logs.py       # Action logging
├── prompts/              # System prompts for agents
│   ├── strategy.py       # Strategy Agent prompts
│   ├── testgen.py        # TestGen Agent prompts
│   └── constraints.py    # Protocol type constraints
├── tools/                # Tool implementations
│   └── test_runner.py    # Multi-language test runner
├── config/               # Configuration
│   ├── settings.py       # Application settings
│   └── protocols.yaml    # Protocol definitions
├── data/                 # Persistent data storage
│   ├── pattern_memory/   # Known bug patterns
│   ├── repo_knowledge/   # Cached repository knowledge
│   └── test_history/     # Test execution history
├── scripts/              # Utility scripts
│   ├── cleanup_memory.py
│   ├── generate_repo_context.py
│   └── upgrade_repo_knowledge.py
└── tests/                # Test suite
```

## Multi-Agent Workflow

1. **Strategy Agent**: Generates creative attack scenarios based on protocol type (CFT/BFT)
2. **TestGen Agent**: Implements test code, executes tests, and records results
3. **Orchestrator**: Coordinates agents, manages iterations, and records bugs

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your OpenRouter API key
```

## Usage

```bash
# List available protocols
python -m agent --list

# Run bug hunting for a specific protocol
python -m agent --repo raft -i 10

# Run indefinitely until interrupted
python -m agent --repo raft --forever

# Run for all protocols in parallel
python -m agent --all --parallel 4

# View statistics
python -m agent --stats
```

## Configuration

### Environment Variables (.env)

```ini
OPENROUTER_API_KEY=your_api_key_here
LLM_MODEL=anthropic/claude-sonnet-4
MAX_THINKING_TOKENS=32000
```

### Protocol Configuration (config/protocols.yaml)

```yaml
protocols:
  raft:
    path: ./raft
    type: cft
    language: go
    fault_tolerance: "(n-1)/2"
```

## Memory System

### Pattern Memory
Stores reusable bug patterns that can be tested across different protocol implementations:
- CFT patterns: Crash fault tolerant protocol bugs
- BFT patterns: Byzantine fault tolerant protocol bugs

### Repository Knowledge
Caches learned information about each repository:
- Test structure and conventions
- Helper function signatures and usage
- Lessons learned from previous errors

### Test History
Records all test executions and discovered bugs:
- Test execution results
- Validated bug reports
- Statistics and metrics

## Supported Languages

- **Go**: `go test`
- **Rust**: `cargo test`
- **Java**: Maven (`mvn test`) and Gradle (`gradle test`)

## Key Components

### ToolAgent (`core/tool_agent.py`)

A self-built tool-calling agent that:
- Supports OpenRouter and DeepSeek API
- Handles multi-turn tool calling loops
- Provides automatic JSON Schema generation via `@tool` decorator

```python
from agent.core import tool, create_tool

@tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file from disk.
    
    Args:
        path: The file path to read
        encoding: File encoding
    """
    ...
```

### Orchestrator (`core/orchestrator.py`)

Main workflow controller that:
- Coordinates Strategy and TestGen agents
- Manages iteration loops with retry logic
- Records bugs and updates memory
- Uses pluggable components for clean separation of concerns

### AgentFactory (`core/agent_factory.py`)

Factory for creating Strategy and TestGen agents:
- Builds agent tools with proper closures
- Configures LLM parameters and callbacks
- Enables customization for ablation experiments

### PatternTracker (`core/pattern_tracker.py`)

Tracks bug pattern usage per protocol:
- Records viewed and used patterns
- Generates lightweight pattern context for prompts
- Persists usage data to JSON files

### Executor (`core/executor.py`)

Robust code executor with:
- Timeout handling and process cleanup
- Working directory enforcement
- Detailed error reporting

### PromptBuilder (`core/prompt_builder.py`)

Centralized prompt construction that:
- Builds strategy prompts with protocol context
- Constructs testgen prompts with scenario details
- Handles similarity check and exploitation prompts
- Provides clean separation of prompt logic from orchestration

### ResultParser (`core/result_parser.py`)

LLM response parsing utilities:
- Parses attack scenarios from strategy agent responses
- Extracts test results and code from testgen responses
- Provides regex-based field and list extraction
- Centralizes all parsing logic for maintainability

### ReportGenerator (`core/report_generator.py`)

Bug report generation and pattern extraction:
- Generates detailed markdown bug reports
- Extracts reusable bug patterns from confirmed bugs
- Manages LLM calls for report generation

### Strategy Interfaces (`core/strategies.py`)

Abstract interfaces for strategy generation:
- `StrategyGenerator`: Interface for attack scenario generation
- `ExploitationHandler`: Interface for bug exploitation
- `StrategyContext`, `AttackScenario`, `TestResult`: Data classes
- Enables dependency injection for ablation experiments

### Strategy Implementations (`core/strategy_impl.py`)

Concrete strategy implementations:
- `DefaultStrategyGenerator`: Full LLM-based strategy generation
- `DefaultExploitationHandler`: LLM-based bug exploitation for finding related vulnerabilities

## Development

```bash
# Run tests
pytest agent/tests/

# Validate API connectivity
python agent/validate_api.py
```

## License

See the project root for license information.
