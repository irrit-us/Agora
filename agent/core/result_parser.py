"""
Result Parser - Centralized parsing for agent responses.

This module consolidates all parsing logic (regex patterns, field extraction)
that was previously scattered throughout the Orchestrator class.
"""

import logging
import re

from .strategies import AttackScenario, TestResult

logger = logging.getLogger(__name__)


# =============================================================================
# Compiled Regex Patterns
# =============================================================================

# Attack scenario patterns
THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)
ATTACK_SCENARIO_PATTERN = re.compile(
    r"<attack_scenario>(.*?)</attack_scenario>", re.DOTALL
)

# Test result patterns
TEST_RESULT_PATTERN = re.compile(
    r"<test_result>(.*?)</test_result>", re.DOTALL
)

# Similarity check patterns
SIMILAR_TEST_PATTERN = re.compile(
    r"<similar_test_found>(.*?)</similar_test_found>",
    re.DOTALL | re.IGNORECASE,
)

# Bug report patterns
BUG_REPORT_PATTERN = re.compile(
    r"<bug_report>(.*?)</bug_report>", re.DOTALL
)
BUG_PATTERN_PATTERN = re.compile(
    r"<bug_pattern>(.*?)</bug_pattern>", re.DOTALL
)

# Code extraction patterns
TEST_CODE_PATTERN = re.compile(
    r"<test_code[^>]*>(.*?)</test_code>", re.DOTALL
)
CODE_BLOCK_PATTERN = re.compile(
    r"```(?:\w+)?\n(.*?)```", re.DOTALL
)

# Test name patterns (language-specific)
GO_TEST_NAME_PATTERN = re.compile(r"func\s+(Test\w+)")
RUST_TEST_NAME_PATTERN = re.compile(r"#\[test\]\s*(?:async\s+)?fn\s+(\w+)")

# Boost.Test (Bitcoin Core): BOOST_AUTO_TEST_CASE(name) / BOOST_FIXTURE_TEST_CASE(name, Fixture)
CPP_BOOST_TEST_CASE_PATTERN = re.compile(
    r"BOOST_(?:AUTO|FIXTURE)_TEST_CASE\(\s*([a-zA-Z0-9_]+)",
    re.MULTILINE,
)

# Pattern ID extraction
PATTERN_ID_PATTERN = re.compile(
    r"pattern_memory\s*::?\s*(.+)", re.IGNORECASE
)


class ResultParser:
    """
    Centralized parser for all agent response formats.
    
    Provides clean, testable methods for extracting structured data
    from LLM responses.
    """
    
    @staticmethod
    def parse_attack_scenario(response: str) -> AttackScenario | None:
        """
        Parse attack scenario from Strategy Agent response.
        
        Args:
            response: Raw response text.
            
        Returns:
            Parsed AttackScenario or None if parsing failed.
        """
        logger.debug(f"[PARSE] Parsing attack scenario from response (len={len(response)})")
        
        # Extract thinking
        thinking_match = THINKING_PATTERN.search(response)
        thinking = thinking_match.group(1).strip() if thinking_match else ""
        
        # Extract scenario block
        scenario_match = ATTACK_SCENARIO_PATTERN.search(response)
        if not scenario_match:
            logger.warning(f"[PARSE] No <attack_scenario> block found in response")
            logger.debug(f"[PARSE] Response preview: {response[:500]}...")
            return None
        
        scenario_text = scenario_match.group(1)
        logger.debug(f"[PARSE] Found scenario block (len={len(scenario_text)})")
        
        # Parse fields
        name = ResultParser._extract_field(scenario_text, "Name") or "UnnamedScenario"
        target = (
            ResultParser._extract_field(scenario_text, "Target Component")
            or ResultParser._extract_field(scenario_text, "Target")
            or ""
        )
        hypothesis = (
            ResultParser._extract_field(scenario_text, "Vulnerability Hypothesis")
            or ResultParser._extract_field(scenario_text, "Vulnerability")
            or ""
        )
        category = (
            ResultParser._extract_field(scenario_text, "Attack Category")
            or ResultParser._extract_field(scenario_text, "Category")
            or "safety"
        )
        inspiration = (
            ResultParser._extract_field(scenario_text, "Inspiration Source") or "original"
        )
        
        preconditions = ResultParser._extract_list(scenario_text, "Preconditions") or []
        steps = (
            ResultParser._extract_list(scenario_text, "Attack Steps")
            or ResultParser._extract_list(scenario_text, "Steps")
            or []
        )
        assertions = ResultParser._extract_list(scenario_text, "Assertions") or []
        
        expected_bug = ResultParser._extract_field(scenario_text, "Expected Bug Behavior") or ""
        correct = ResultParser._extract_field(scenario_text, "Correct Behavior") or ""
        
        # Log parsed fields for debugging
        logger.info(f"[PARSE] Parsed scenario: name={name}, target={target}, category={category}")
        logger.debug(f"[PARSE] Parsed details: preconditions={len(preconditions)}, steps={len(steps)}, assertions={len(assertions)}")
        
        if not name or name == "UnnamedScenario":
            logger.warning(f"[PARSE] Scenario has no name!")
        if not target:
            logger.warning(f"[PARSE] Scenario has no target component!")
        if not hypothesis:
            logger.warning(f"[PARSE] Scenario has no vulnerability hypothesis!")
        if not steps:
            logger.warning(f"[PARSE] Scenario has no attack steps!")
        
        return AttackScenario(
            name=name,
            target_component=target,
            vulnerability_hypothesis=hypothesis,
            attack_category=category.lower(),
            preconditions=preconditions,
            steps=steps,
            expected_bug_behavior=expected_bug,
            correct_behavior=correct,
            assertions=assertions,
            thinking_chain=thinking,
            inspiration_source=inspiration,
        )
    
    @staticmethod
    def parse_test_result(response: str) -> TestResult | None:
        """
        Parse test result from TestGen Agent response.
        
        Args:
            response: Raw response text.
            
        Returns:
            Parsed TestResult or None if no result block found.
        """
        result_match = TEST_RESULT_PATTERN.search(response)
        if not result_match:
            return None
        
        result_text = result_match.group(1)
        
        test_file = ResultParser._extract_field(result_text, "Test File") or ""
        test_name = ResultParser._extract_field(result_text, "Test Name") or ""
        result_str = ResultParser._extract_field(result_text, "Result") or "UNKNOWN"
        output = ResultParser._extract_field(result_text, "Output") or ""
        
        passed = result_str.upper() == "PASS"
        
        # Extract test code from response
        test_code = ResultParser._extract_code_from_response(response) or ""
        
        return TestResult(
            success=passed,
            test_code=test_code,
            test_file=test_file,
            test_output=output,
            result=result_str.upper(),
            passed=passed,
        )
    
    @staticmethod
    def parse_similar_test_info(response: str) -> tuple[str | None, str | None]:
        """
        Parse similar test information from similarity check response.
        
        Args:
            response: TestGen Agent response.
            
        Returns:
            Tuple of (test_file, test_function_name).
        """
        similar_match = SIMILAR_TEST_PATTERN.search(response)
        if not similar_match:
            return None, None
        
        block = similar_match.group(1)
        
        # Extract test file path
        test_file = None
        test_match = re.search(r"Existing\s+Test:\s*([^\n]+)", block, re.IGNORECASE)
        if test_match:
            test_file = test_match.group(1).strip().strip("`[]")
        
        # Extract test function name
        test_function = None
        func_match = re.search(r"Test\s+Function:\s*([^\n]+)", block, re.IGNORECASE)
        if func_match:
            test_function = func_match.group(1).strip().strip("`[]")
        
        return test_file, test_function
    
    @staticmethod
    def has_similar_test(response: str) -> bool:
        """Check if response indicates a similar test was found."""
        return "<similar_test_found>" in response.lower()
    
    @staticmethod
    def has_confirmed_bug(response: str) -> bool:
        """Check if response indicates a confirmed bug."""
        return "<confirmed_bug>" in response.lower()
    
    @staticmethod
    def extract_confirmed_bug_description(response: str) -> str | None:
        """
        Extract bug description from confirmed_bug tag.
        
        Args:
            response: Response text containing <confirmed_bug> tag.
            
        Returns:
            Bug description or None.
        """
        match = re.search(
            r"<confirmed_bug>\s*(.+?)\s*</confirmed_bug>",
            response,
            re.IGNORECASE | re.DOTALL
        )
        return match.group(1).strip() if match else None
    
    @staticmethod
    def parse_bug_report(response: str) -> str:
        """
        Extract bug report from Orchestrator response.
        
        Args:
            response: Orchestrator LLM response.
            
        Returns:
            Bug report text or empty string.
        """
        match = BUG_REPORT_PATTERN.search(response)
        return match.group(1).strip() if match else ""
    
    @staticmethod
    def parse_bug_pattern_fields(response: str) -> dict[str, str]:
        """
        Extract bug pattern fields from Orchestrator response.
        
        Args:
            response: Orchestrator LLM response.
            
        Returns:
            Dict with pattern fields.
        """
        match = BUG_PATTERN_PATTERN.search(response)
        if not match:
            return {}
        
        pattern_text = match.group(1).strip()
        
        return {
            "pattern_name": ResultParser._extract_field(pattern_text, "Pattern Name") or "",
            "bug_category": ResultParser._extract_field(pattern_text, "Bug Category") or "",
            "fault_type": ResultParser._extract_field(pattern_text, "Fault Type") or "",
            "trigger_condition": ResultParser._extract_field(pattern_text, "Trigger Condition") or "",
            "description": ResultParser._extract_field(pattern_text, "Description") or "",
            "test_template": ResultParser._extract_field(pattern_text, "Test Template") or "",
        }
    
    @staticmethod
    def extract_pattern_id(inspiration_source: str) -> str | None:
        """
        Extract pattern_id from inspiration source field.
        
        Args:
            inspiration_source: The inspiration source string.
            
        Returns:
            Pattern ID or None.
        """
        if not inspiration_source:
            return None
        
        source = inspiration_source.strip()
        if not source or source.lower() == "original":
            return None
        
        match = PATTERN_ID_PATTERN.search(source)
        if not match:
            return None
        
        pattern_id = match.group(1).strip().strip('"').strip("'")
        return pattern_id or None
    
    @staticmethod
    def extract_test_name(code: str, language: str = "go") -> str:
        """
        Extract test function name from test code.
        
        Args:
            code: Test code.
            language: Programming language.
            
        Returns:
            Test function name or default "Test".
        """
        if language.lower() == "go":
            match = GO_TEST_NAME_PATTERN.search(code)
            if match:
                return match.group(1)
        elif language.lower() == "rust":
            match = RUST_TEST_NAME_PATTERN.search(code)
            if match:
                return match.group(1)
        elif language.lower() in ("cpp", "c++"):
            match = CPP_BOOST_TEST_CASE_PATTERN.search(code)
            if match:
                return match.group(1)

        return "Test"
    
    @staticmethod
    def _extract_field(text: str, field_name: str) -> str | None:
        """
        Extract a field value from text.
        
        Args:
            text: Text to search in.
            field_name: Field name to look for.
            
        Returns:
            Field value or None.
        """
        pattern = rf"{field_name}[:\s]*(.+?)(?:\n|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    @staticmethod
    def _extract_list(text: str, list_name: str) -> list[str]:
        """
        Extract a list from text.
        
        Args:
            text: Text to search in.
            list_name: List header name.
            
        Returns:
            List of items.
        """
        pattern = rf"{list_name}[:]?\s*\n((?:\s*(?:[-*]|\d+[.)]+)\s*.+\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return []
        
        list_text = match.group(1)
        items = re.findall(r"(?:[-*]|\d+[.)]+)\s*(.+?)(?:\n|$)", list_text)
        return [item.strip() for item in items]
    
    @staticmethod
    def _extract_code_from_response(response: str) -> str | None:
        """
        Extract code from response (test_code tags or code blocks).
        
        Args:
            response: Response text.
            
        Returns:
            Code string or None.
        """
        # Try test_code tags first
        match = TEST_CODE_PATTERN.search(response)
        if match:
            return match.group(1).strip()
        
        # Fall back to markdown code blocks
        match = CODE_BLOCK_PATTERN.search(response)
        if match:
            return match.group(1).strip()
        
        return None
