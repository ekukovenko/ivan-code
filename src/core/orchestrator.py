"""SDLC Orchestrator - manages the full development cycle.

Flow:
1. Issue created → Code Agent generates fix → PR created
2. PR created → CI runs → Reviewer Agent reviews
3. If changes requested → Code Agent fixes → back to step 2
4. If approved → ready for merge
"""

import logging
from dataclasses import dataclass

from src.core.config import get_settings
from src.github.client import GitHubClient
from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CycleResult:
    """Result of a development cycle."""

    success: bool
    pr_number: int | None
    iterations: int
    final_decision: str
    message: str


class SDLCOrchestrator:
    """Orchestrates the full SDLC cycle."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        code_agent: CodeAgent | None = None,
        reviewer_agent: ReviewerAgent | None = None,
    ):
        settings = get_settings()
        self.github = github_client or GitHubClient()
        self.code_agent = code_agent or CodeAgent(self.github)
        self.reviewer_agent = reviewer_agent or ReviewerAgent(self.github)
        self.max_iterations = settings.max_iterations

    def process_issue(self, issue_number: int) -> CycleResult:
        """Process an issue through the full SDLC cycle.

        Args:
            issue_number: GitHub issue number

        Returns:
            CycleResult with details of the cycle
        """
        logger.info(f"Starting SDLC cycle for issue #{issue_number}")

        # Step 1: Code Agent creates PR
        logger.info("Code Agent generating fix...")
        code_result = self.code_agent.process_issue(issue_number)

        if not code_result["success"]:
            return CycleResult(
                success=False,
                pr_number=None,
                iterations=0,
                final_decision="FAILED",
                message=f"Code Agent failed: {code_result['message']}",
            )

        pr_number = code_result["pr_number"]
        branch = code_result["branch"]
        logger.info(f"PR #{pr_number} created on branch {branch}")

        # Step 2-3: Review loop
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Review iteration {iteration}/{self.max_iterations}")

            # Wait for CI (in real scenario, this would be webhook-driven)
            # For now, we proceed immediately

            # Reviewer Agent reviews
            logger.info("Reviewer Agent analyzing PR...")
            review_result = self.reviewer_agent.review_pr(pr_number, issue_number)

            decision = review_result["decision"]
            logger.info(f"Review decision: {decision}")

            if decision == "APPROVE":
                return CycleResult(
                    success=True,
                    pr_number=pr_number,
                    iterations=iteration,
                    final_decision="APPROVE",
                    message="PR approved and ready for merge",
                )

            if decision == "REQUEST_CHANGES":
                if iteration >= self.max_iterations:
                    return CycleResult(
                        success=False,
                        pr_number=pr_number,
                        iterations=iteration,
                        final_decision="MAX_ITERATIONS",
                        message=f"Max iterations ({self.max_iterations}) reached",
                    )

                # Code Agent addresses feedback
                logger.info("Code Agent addressing review feedback...")
                fix_result = self.code_agent.apply_review_feedback(
                    pr_number=pr_number,
                    feedback=review_result["summary"],
                    branch=branch,
                )

                if not fix_result["success"]:
                    return CycleResult(
                        success=False,
                        pr_number=pr_number,
                        iterations=iteration,
                        final_decision="FIX_FAILED",
                        message=f"Code Agent failed to fix: {fix_result['message']}",
                    )

            # COMMENT decision - continue but don't count as blocking
            else:
                logger.info("Review has comments but no blocking issues")
                return CycleResult(
                    success=True,
                    pr_number=pr_number,
                    iterations=iteration,
                    final_decision="COMMENT",
                    message="PR has comments, may need human review",
                )

        return CycleResult(
            success=False,
            pr_number=pr_number,
            iterations=self.max_iterations,
            final_decision="MAX_ITERATIONS",
            message="Max iterations reached without approval",
        )

    def handle_pr_event(self, pr_number: int, action: str) -> dict:
        """Handle PR events (for webhook integration).

        Args:
            pr_number: PR number
            action: Event action (opened, synchronize, etc.)

        Returns:
            dict with handling result
        """
        if action in ("opened", "synchronize"):
            # Extract issue number from PR
            pr_data = self.github.get_pull_request(pr_number)
            issue_number = self._extract_issue_number(pr_data.body)

            # Run review
            review_result = self.reviewer_agent.review_pr(pr_number, issue_number)

            return {
                "action": "reviewed",
                "decision": review_result["decision"],
                "pr_number": pr_number,
            }

        return {"action": "ignored", "reason": f"Unknown action: {action}"}

    def _extract_issue_number(self, text: str) -> int | None:
        """Extract issue number from PR body."""
        import re

        # Look for patterns like "Closes #123" or "Fixes #123"
        match = re.search(r"(?:closes|fixes|resolves)\s*#(\d+)", text.lower())
        if match:
            return int(match.group(1))
        return None
