"""
Report Generator - Bug report and pattern generation.

This module handles all bug report generation logic, including
LLM-based analysis and pattern extraction.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from ..memory.pattern_memory import BugPattern
from ..prompts import ORCHESTRATOR_SYSTEM_PROMPT, get_orchestrator_prompt
from ..utils.token_usage import TokenUsage
from .result_parser import ResultParser
from .strategies import AttackScenario, TestResult

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates bug reports and extracts patterns from confirmed bugs.
    
    Uses direct LLM calls (stateless) to analyze bugs and generate
    comprehensive reports with root cause analysis.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "anthropic/claude-sonnet-4",
        timeout: float = 120.0,
    ):
        """
        Initialize the report generator.
        
        Args:
            api_key: API key for LLM service.
            base_url: API base URL.
            model: Model to use for report generation.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None
        
        # Token usage tracking
        self.token_usage = TokenUsage()
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            )
            transport = httpx.AsyncHTTPTransport(retries=2)
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=30.0),
                limits=limits,
                transport=transport,
            )
        return self._http_client
    
    async def generate_bug_report(
        self,
        scenario: AttackScenario,
        result: TestResult,
        protocol_name: str,
        protocol_type: str,
        bug_token_usage: TokenUsage,
    ) -> tuple[str, BugPattern | None]:
        """
        Generate a comprehensive bug report and extract pattern.
        
        Args:
            scenario: Attack scenario that triggered the bug.
            result: Test result with execution details.
            protocol_name: Name of the protocol.
            protocol_type: Type (cft/bft).
            bug_token_usage: Token usage for discovering this bug.
            
        Returns:
            Tuple of (bug_report_text, BugPattern or None).
        """
        # Build prompt using prompts module
        prompt = get_orchestrator_prompt(
            protocol_name=protocol_name,
            protocol_type=protocol_type,
            scenario_name=scenario.name,
            target_component=scenario.target_component,
            attack_category=scenario.attack_category,
            vulnerability_hypothesis=scenario.vulnerability_hypothesis,
            preconditions=scenario.preconditions,
            attack_steps=scenario.steps,
            expected_bug_behavior=scenario.expected_bug_behavior,
            correct_behavior=scenario.correct_behavior,
            test_file=result.test_file,
            test_output=result.test_output or "",
            prompt_tokens=bug_token_usage.prompt_tokens,
            completion_tokens=bug_token_usage.completion_tokens,
            total_tokens=bug_token_usage.total_tokens,
            api_cost=bug_token_usage.cost,
        )
        
        try:
            content, usage = await self._call_llm(prompt, ORCHESTRATOR_SYSTEM_PROMPT)
            
            # Track token usage
            report_usage = TokenUsage()
            report_usage.add(usage)
            self.token_usage += report_usage
            
            # Parse bug report
            bug_report = ResultParser.parse_bug_report(content)
            
            # Add discovery statistics
            bug_report += f"""

---
## Discovery Statistics
- Total Tokens Used: {bug_token_usage.total_tokens:,}
- API Cost: ${bug_token_usage.cost:.4f}
- Discovery Date: {datetime.now().isoformat()}
"""
            
            # Parse and create bug pattern
            bug_pattern = self._create_bug_pattern(
                content,
                scenario,
                protocol_name,
                protocol_type,
                bug_token_usage,
            )
            
            return bug_report, bug_pattern
            
        except Exception as e:
            logger.error(f"Failed to generate bug report: {e}")
            
            # Return basic report without LLM
            basic_report = f"""## Bug Report: {scenario.name}

**Protocol**: {protocol_name}
**Vulnerability**: {scenario.vulnerability_hypothesis}
**Test File**: {result.test_file}

### Discovery Statistics
- Total Tokens Used: {bug_token_usage.total_tokens:,}
- API Cost: ${bug_token_usage.cost:.4f}
- Discovery Date: {datetime.now().isoformat()}

*Note: LLM-based analysis failed, this is a basic report.*
"""
            return basic_report, None
    
    def _create_bug_pattern(
        self,
        response: str,
        scenario: AttackScenario,
        protocol_name: str,
        protocol_type: str,
        bug_token_usage: TokenUsage,
    ) -> BugPattern | None:
        """
        Create BugPattern from LLM response.
        
        Args:
            response: LLM response containing pattern info.
            scenario: Original attack scenario.
            protocol_name: Protocol name.
            protocol_type: Protocol type.
            bug_token_usage: Token usage for discovery.
            
        Returns:
            BugPattern or None if parsing failed.
        """
        fields = ResultParser.parse_bug_pattern_fields(response)
        if not fields:
            return None
        
        return BugPattern(
            pattern_id=fields.get("pattern_name") or scenario.name,
            protocol_type=protocol_type,
            description=fields.get("description") or "",
            bug_category=fields.get("bug_category", "").lower() or None,
            fault_type=fields.get("fault_type") or None,
            trigger_condition=fields.get("trigger_condition") or None,
            test_template=fields.get("test_template") or None,
            discovered_in_repo=protocol_name,
            discovery_date=datetime.now().isoformat(),
            discovery_process="auto-discovered by Orchestrator Agent",
            context={
                "tokens_used": bug_token_usage.total_tokens,
                "api_cost": bug_token_usage.cost,
            },
        )
    
    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """
        Make stateless LLM call.
        
        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            
        Returns:
            Tuple of (content, usage_dict).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        request_body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
        }
        
        client = await self._get_http_client()
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=request_body,
        )
        resp.raise_for_status()
        data = resp.json()
        
        choices = data.get("choices") or []
        if not choices:
            return "", {}
        
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage", {})
        
        return content, usage
    
    def get_token_usage(self) -> dict[str, Any]:
        """Get cumulative token usage."""
        return self.token_usage.to_dict()
