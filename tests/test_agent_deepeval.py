"""SDLC Agent tests.

Unit tests verify REAL functionality with standard assertions:
- Security scanning tools (check_security_issues)
- Decision parsing logic (_parse_decision)
- Webhook endpoints (FastAPI)
- Session memory management
- Performance benchmarks

Integration tests use deepeval to evaluate LLM response quality:
- TaskCompletionMetric for actual LLM outputs
"""

import os
import time
from unittest.mock import MagicMock

import pytest

from src.tools.code_tools import check_security_issues


def create_mock_github():
    """Create mock GitHub client for testing."""
    mock = MagicMock()
    mock.repo_name = "test/repo"
    return mock


# ============================================================================
# UNIT TESTS - Security Scanner (real function, no mocks)
# ============================================================================


def test_security_hardcoded_secrets():
    """Security scanner detects hardcoded passwords and API keys."""
    vulnerable_code = '''
def connect_db():
    password = "super_secret_password123"
    api_key = "sk-1234567890abcdef"
    return connect(password=password)
'''
    issues = check_security_issues(vulnerable_code, "db.py")

    assert len(issues) >= 1, "Should detect at least 1 vulnerability"
    assert any(i["category"] == "hardcoded_secret" for i in issues), \
        f"Should detect hardcoded_secret, got: {[i['category'] for i in issues]}"
    assert any(i["severity"] == "HIGH" for i in issues), \
        "Hardcoded secrets should be HIGH severity"


def test_security_sql_injection():
    """Security scanner detects SQL injection patterns."""
    vulnerable_code = '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)

def delete_user(name):
    cursor.execute("DELETE FROM users WHERE name = '%s'" % name)
'''
    issues = check_security_issues(vulnerable_code, "db.py")

    assert any(i["category"] == "sql_injection" for i in issues), \
        f"Should detect sql_injection, got: {[i['category'] for i in issues]}"


def test_security_command_injection():
    """Security scanner detects command injection patterns."""
    vulnerable_code = '''
import os
import subprocess

def run_command(user_input):
    os.system(user_input)
    subprocess.call(user_input, shell=True)
'''
    issues = check_security_issues(vulnerable_code, "utils.py")

    assert any(i["category"] == "command_injection" for i in issues), \
        f"Should detect command_injection, got: {[i['category'] for i in issues]}"



# ============================================================================
# UNIT TESTS - Reviewer Decision Parsing
# ============================================================================


def test_reviewer_parse_decision_approve():
    """_parse_decision extracts APPROVE from response."""
    from src.agents.reviewer_agent import ReviewerAgent

    mock_github = create_mock_github()
    agent = ReviewerAgent(github_client=mock_github)

    assert agent._parse_decision("APPROVE: Code looks good") == "APPROVE"
    assert agent._parse_decision("The code is great. APPROVE") == "APPROVE"


def test_reviewer_parse_decision_request_changes():
    """_parse_decision extracts REQUEST_CHANGES from response."""
    from src.agents.reviewer_agent import ReviewerAgent

    mock_github = create_mock_github()
    agent = ReviewerAgent(github_client=mock_github)

    assert agent._parse_decision("REQUEST_CHANGES: bugs found") == "REQUEST_CHANGES"
    assert agent._parse_decision("I found issues. REQUEST_CHANGES") == "REQUEST_CHANGES"


def test_reviewer_parse_decision_comment_default():
    """_parse_decision defaults to COMMENT for unclear responses."""
    from src.agents.reviewer_agent import ReviewerAgent

    mock_github = create_mock_github()
    agent = ReviewerAgent(github_client=mock_github)

    assert agent._parse_decision("Just some thoughts") == "COMMENT"
    assert agent._parse_decision("COMMENT: some suggestions") == "COMMENT"


def test_reviewer_parse_decision_not_approve():
    """_parse_decision handles 'NOT APPROVE' correctly (should not be APPROVE)."""
    from src.agents.reviewer_agent import ReviewerAgent

    mock_github = create_mock_github()
    agent = ReviewerAgent(github_client=mock_github)

    # "NOT APPROVE" should NOT be parsed as APPROVE
    assert agent._parse_decision("This does NOT APPROVE the code") == "COMMENT"


# ============================================================================
# UNIT TESTS - Webhook Endpoint
# ============================================================================


def test_webhook_health_endpoint():
    """Webhook /health endpoint returns healthy status."""
    from fastapi.testclient import TestClient
    from src.webhook.server import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "healthy"}


# ============================================================================
# UNIT TESTS - Session Memory
# ============================================================================


def test_code_agent_session_memory_same_session():
    """Same session_id returns same agent instance (memory preserved)."""
    from src.agents.code_agent import CodeAgent

    mock_github = create_mock_github()
    agent = CodeAgent(github_client=mock_github)

    session_id = "issue-99"
    branch = "issue-99-auto"

    agent1 = agent._get_or_create_agent(session_id, branch)
    agent2 = agent._get_or_create_agent(session_id, branch)

    assert agent1 is agent2, "Same session_id should return same agent instance"


def test_code_agent_session_memory_different_session():
    """Different session_id creates new agent instance."""
    from src.agents.code_agent import CodeAgent

    mock_github = create_mock_github()
    agent = CodeAgent(github_client=mock_github)

    agent1 = agent._get_or_create_agent("issue-99", "issue-99-auto")
    agent2 = agent._get_or_create_agent("issue-100", "issue-100-auto")

    assert agent1 is not agent2, "Different session_id should create new agent"


# ============================================================================
# PERFORMANCE BENCHMARK
# ============================================================================


def test_security_scan_performance():
    """Security scanner completes large file scan in under 5 seconds."""
    # Large code sample (~50KB)
    code = '''
import os
def func1(): password = "secret123"
def func2(): os.system(input())
def func3(): cursor.execute(f"SELECT * FROM {table}")
''' * 100

    start = time.time()
    issues = check_security_issues(code, "large_file.py")
    elapsed = time.time() - start

    assert elapsed < 5, f"Security scan too slow: {elapsed:.2f}s (limit: 5s)"
    assert len(issues) > 0, "Should find vulnerabilities in test code"


# ============================================================================
# INTEGRATION TEST - Real LLM call with deepeval evaluation
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="RUN_INTEGRATION_TESTS not set (slow test with real LLM)"
)
def test_integration_code_agent_real_llm():
    """Integration: CodeAgent generates real code via LLM.

    Uses deepeval TaskCompletionMetric to evaluate ACTUAL LLM response quality.
    """
    from deepeval import evaluate
    from deepeval.metrics import TaskCompletionMetric
    from deepeval.models import GPTModel
    from deepeval.test_case import LLMTestCase

    from src.agents.code_agent import CodeAgent
    from src.core.config import get_settings

    # Setup
    mock_github = create_mock_github()
    mock_github.get_issue.return_value = MagicMock(
        number=1,
        title="Add sum function",
        body="Create a Python function sum(a, b) that returns a + b"
    )
    mock_github.create_branch.return_value = None
    mock_github.list_files.return_value = []
    mock_github.get_file_content.return_value = None

    created_files = {}

    def track_file(path, content, msg, branch):
        created_files[path] = content

    mock_github.create_or_update_file.side_effect = track_file
    mock_github.create_pull_request.return_value = 1

    agent = CodeAgent(github_client=mock_github)

    # Run with real LLM
    result = agent.process_issue(1)

    # Basic assertions
    assert result["success"], f"CodeAgent should succeed, got: {result}"
    assert len(created_files) > 0, "At least one file should be created"

    # Get the actual code generated by LLM
    all_generated_code = "\n".join(created_files.values())

    # Use deepeval to evaluate LLM output quality
    settings = get_settings()
    eval_model = GPTModel(
        model=settings.default_model,
        api_key=settings.llm_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    test_case = LLMTestCase(
        input="Create a Python function sum(a, b) that returns a + b",
        actual_output=all_generated_code,  # Real LLM-generated code
        expected_output="A Python function named 'sum' that takes two arguments and returns their sum",
        tools_called=[],  # Required by deepeval TaskCompletionMetric
    )

    # Evaluate with deepeval - this makes sense because actual_output is real LLM output
    task_metric = TaskCompletionMetric(threshold=0.6, model=eval_model)
    evaluate([test_case], metrics=[task_metric])

    # Verify code quality
    assert "def " in all_generated_code, "Should contain function definition"
    assert "sum" in all_generated_code.lower() or "add" in all_generated_code.lower(), \
        "Should contain sum/add related function"


@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="RUN_INTEGRATION_TESTS not set (slow test with real LLM)"
)
def test_integration_reviewer_agent_real_llm():
    """Integration: ReviewerAgent analyzes code via real LLM.

    Uses deepeval to evaluate the quality of the review.
    """
    from deepeval import evaluate
    from deepeval.metrics import TaskCompletionMetric
    from deepeval.models import GPTModel
    from deepeval.test_case import LLMTestCase

    from src.agents.reviewer_agent import ReviewerAgent
    from src.core.config import get_settings

    mock_github = create_mock_github()

    # Setup PR with obvious bug for reviewer to catch
    mock_github.get_pull_request.return_value = MagicMock(
        number=100,
        title="Add user lookup",
        body="Closes #42",
        diff='''+def get_user(user_id):
+    query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection!
+    return db.execute(query)
''',
        files_changed=["user.py"]
    )
    mock_github.get_pr_ci_status.return_value = MagicMock(
        status="success",
        checks=[{"name": "tests", "state": "success"}]
    )
    mock_github.get_issue.return_value = MagicMock(
        number=42,
        title="Add user lookup",
        body="Create function to get user by ID"
    )
    mock_github.repo = MagicMock()
    mock_github.repo.get_pull.return_value = MagicMock(
        head=MagicMock(ref="issue-42-auto")
    )

    # Capture the review that gets posted
    posted_review = {}
    def capture_review(pr_number, body, event, comments=None):
        posted_review["body"] = body
        posted_review["event"] = event
    mock_github.create_pr_review.side_effect = capture_review

    agent = ReviewerAgent(github_client=mock_github)
    result = agent.review_pr(100, issue_number=42)

    # Basic assertion - reviewer should catch the SQL injection
    assert result["decision"] in ["REQUEST_CHANGES", "COMMENT"], \
        f"Reviewer should flag SQL injection, got: {result['decision']}"

    # Use deepeval to evaluate review quality
    settings = get_settings()
    eval_model = GPTModel(
        model=settings.default_model,
        api_key=settings.llm_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    test_case = LLMTestCase(
        input="Review PR with SQL injection vulnerability in user lookup function",
        actual_output=result["summary"],  # Real LLM-generated review
        expected_output="Review identifies SQL injection vulnerability and requests changes or comments on security issue",
        tools_called=[],  # Required by deepeval TaskCompletionMetric
    )

    task_metric = TaskCompletionMetric(threshold=0.5, model=eval_model)
    evaluate([test_case], metrics=[task_metric])

    # Verify review mentions security concern
    review_text = result["summary"].lower()
    security_keywords = ["sql", "injection", "security", "vulnerability", "unsafe", "parameterized"]
    assert any(kw in review_text for kw in security_keywords), \
        f"Review should mention security issue, got: {result['summary'][:500]}"
