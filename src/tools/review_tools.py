"""Tools for Reviewer Agent - PR analysis and review."""

from agno.tools import tool

from src.github.client import GitHubClient


def create_review_tools(github_client: GitHubClient, pr_number: int):
    """Create tools for Reviewer Agent with PR context."""

    @tool
    def get_pr_diff() -> str:
        """Get the full diff of the pull request."""
        try:
            pr_data = github_client.get_pull_request(pr_number)
            return pr_data.diff
        except Exception as e:
            return f"Error getting diff: {e}"

    @tool
    def get_pr_files() -> str:
        """Get list of files changed in the PR."""
        try:
            pr_data = github_client.get_pull_request(pr_number)
            return "\n".join(pr_data.files_changed)
        except Exception as e:
            return f"Error getting files: {e}"

    @tool
    def get_ci_status() -> str:
        """Get CI/CD status for the PR."""
        try:
            status = github_client.get_pr_ci_status(pr_number)
            result = [f"Overall status: {status.status}\n\nChecks:"]
            for check in status.checks:
                result.append(f"  - {check['name']}: {check['state']}")
                if check.get("description"):
                    result.append(f"    {check['description']}")
            return "\n".join(result)
        except Exception as e:
            return f"Error getting CI status: {e}"

    @tool
    def read_file(path: str) -> str:
        """Read file content from the PR branch.

        Args:
            path: Path to the file
        """
        try:
            pr_data = github_client.get_pull_request(pr_number)
            pr = github_client.repo.get_pull(pr_number)
            content = github_client.get_file_content(path, ref=pr.head.ref)
            if content is None:
                return f"Error: File '{path}' not found"
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    @tool
    def get_issue_requirements(issue_number: int) -> str:
        """Get the original issue requirements.

        Args:
            issue_number: Issue number to get requirements from
        """
        try:
            issue = github_client.get_issue(issue_number)
            return f"Title: {issue.title}\n\nDescription:\n{issue.body}"
        except Exception as e:
            return f"Error getting issue: {e}"

    @tool
    def submit_review(
        decision: str,
        summary: str,
        comments: str = "",
    ) -> str:
        """ОБЯЗАТЕЛЬНО вызови этот tool в конце ревью для отправки результата на GitHub.

        Без вызова этого tool ревью НЕ будет опубликовано!

        Args:
            decision: Решение - одно из: APPROVE | REQUEST_CHANGES | COMMENT
            summary: Краткое резюме ревью на русском языке
            comments: Опционально - inline комментарии (формат: file:line:comment, по одному на строку)
        """
        try:
            # Parse inline comments
            inline_comments = []
            if comments:
                for line in comments.strip().split("\n"):
                    if ":" in line:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            inline_comments.append(
                                {
                                    "path": parts[0],
                                    "position": int(parts[1]),
                                    "body": parts[2],
                                }
                            )

            # Add Reviewer Agent marker to the summary
            marked_summary = f"👀 **Reviewer Agent**\n\n{summary}"
            event = decision.upper()

            try:
                github_client.create_pr_review(
                    pr_number=pr_number,
                    body=marked_summary,
                    event=event,
                    comments=inline_comments if inline_comments else None,
                )
                return f"Review submitted: {decision}"
            except Exception as e:
                # GitHub doesn't allow approving own PRs - fallback to COMMENT
                if "approve your own" in str(e).lower() and event == "APPROVE":
                    marked_summary = f"👀 **Reviewer Agent** ✅ APPROVED\n\n{summary}\n\n---\n*Статус: APPROVE (отправлено как COMMENT из-за ограничений GitHub)*"
                    github_client.create_pr_review(
                        pr_number=pr_number,
                        body=marked_summary,
                        event="COMMENT",
                        comments=inline_comments if inline_comments else None,
                    )
                    return f"Review submitted: APPROVE (as COMMENT due to GitHub limitation)"
                raise
        except Exception as e:
            return f"Error submitting review: {e}"

    return [
        get_pr_diff,
        get_pr_files,
        get_ci_status,
        read_file,
        get_issue_requirements,
        submit_review,
    ]
