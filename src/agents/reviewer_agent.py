"""Reviewer Agent - analyzes PRs and provides code review.

IMPORTANT: This agent is ISOLATED from Code Agent.
It acts as an independent, critical reviewer.
"""

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.core.config import get_settings
from src.github.client import GitHubClient
from src.tools.review_tools import create_review_tools


REVIEWER_AGENT_PROMPT = """You are a STRICT and THOROUGH code reviewer. Your job is to critically analyze pull requests and ensure code quality.

YOU ARE INDEPENDENT FROM THE CODE AUTHOR. Do NOT automatically approve code.

## Review Checklist:
1. **Requirements Match**: Does the code actually solve the issue?
2. **Code Quality**: Is the code clean, readable, and maintainable?
3. **Bugs**: Are there any logical errors or edge cases?
4. **Security**: Are there any security vulnerabilities (injection, XSS, etc.)?
5. **Tests**: Are there adequate tests for the changes?
6. **Performance**: Are there any performance concerns?
7. **Style**: Does the code follow project conventions?

## CI Status:
- If CI is FAILING, you MUST request changes
- Do NOT approve if tests are failing

## Decision Guidelines:
- APPROVE: Only if ALL checks pass and code is correct
- REQUEST_CHANGES: If there are bugs, missing tests, CI failures, or security issues
- COMMENT: If you have suggestions but no blocking issues

Be specific in your feedback. Point to exact files and lines when possible.

WORKFLOW:
1. Get the PR diff and understand what changed
2. Check CI status
3. Read the original issue requirements
4. Read changed files in full context
5. Make your decision and submit review

Respond in English.
"""


class ReviewerAgent:
    """Agent that reviews PRs independently from Code Agent."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        model: str | None = None,
    ):
        settings = get_settings()
        self.github = github_client or GitHubClient()
        self.model = model or settings.default_model
        self.api_key = settings.llm_api_key

    def review_pr(self, pr_number: int, issue_number: int | None = None) -> dict:
        """Review a pull request.

        Args:
            pr_number: PR number to review
            issue_number: Related issue number (optional)

        Returns:
            dict with keys: decision, summary, needs_changes
        """
        # Create tools with PR context
        tools = create_review_tools(self.github, pr_number)

        # Create agent
        agent = Agent(
            model=OpenRouter(id=self.model, api_key=self.api_key),
            tools=tools,
            instructions=REVIEWER_AGENT_PROMPT,
            markdown=True,
        )

        # Build prompt
        prompt = self._build_prompt(pr_number, issue_number)

        try:
            response = agent.run(prompt)

            # Parse decision from response
            decision = self._parse_decision(response.content)

            return {
                "decision": decision,
                "summary": response.content,
                "needs_changes": decision == "REQUEST_CHANGES",
            }
        except Exception as e:
            return {
                "decision": "COMMENT",
                "summary": f"Review failed: {str(e)}",
                "needs_changes": True,
            }

    def _build_prompt(self, pr_number: int, issue_number: int | None) -> str:
        """Build review prompt."""
        issue_part = ""
        if issue_number:
            issue_part = f"\nThe PR is related to Issue #{issue_number}. Use get_issue_requirements to check if the implementation matches."

        return f"""Please review Pull Request #{pr_number}.
{issue_part}

Follow this process:
1. Get the PR diff to see what changed
2. Check CI status - if failing, that's a blocker
3. Read the full content of changed files for context
4. {"Get the issue requirements and verify the implementation" if issue_number else "Understand the intent of the changes"}
5. Submit your review with a clear decision

Be thorough but fair. Your review should help improve code quality.
"""

    def _parse_decision(self, response: str) -> str:
        """Parse decision from agent response."""
        response_upper = response.upper()
        if "REQUEST_CHANGES" in response_upper or "REQUEST CHANGES" in response_upper:
            return "REQUEST_CHANGES"
        elif "APPROVE" in response_upper and "NOT APPROVE" not in response_upper:
            return "APPROVE"
        return "COMMENT"
