"""Tools for Reviewer Agent - PR analysis and review."""

from agno.tools import tool

from src.github.client import GitHubClient
from src.tools.code_tools import check_security_issues


def create_review_tools(github_client: GitHubClient, pr_number: int, review_state: dict | None = None):
    """Create tools for Reviewer Agent with PR context.

    Args:
        github_client: GitHub API client
        pr_number: PR number to review
        review_state: Dict to track submit_review calls. Updated with
                      {"submitted": True, "decision": "..."} when tool is called.
    """

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

    # Capture pr_number from closure before defining tool
    _pr_number = pr_number

    @tool
    def get_ci_status(pr_number: int | None = None) -> str:
        """Get CI/CD status for the current PR.

        Args:
            pr_number: Optional, ignored (uses PR from context)
        """
        try:
            # Always use closure value, ignore parameter
            status = github_client.get_pr_ci_status(_pr_number)
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
                # Track successful submission
                if review_state is not None:
                    review_state["submitted"] = True
                    review_state["decision"] = decision.upper()
                return f"Review submitted: {decision}"
            except Exception as e:
                # GitHub doesn't allow approving/requesting changes on own PRs - fallback to COMMENT
                if event in ("APPROVE", "REQUEST_CHANGES"):
                    status_emoji = "✅" if event == "APPROVE" else "❌"
                    marked_summary = f"👀 **Reviewer Agent** {status_emoji} {event}\n\n{summary}\n\n---\n*Статус: {event} (отправлено как COMMENT из-за ограничений GitHub)*"
                    github_client.create_pr_review(
                        pr_number=pr_number,
                        body=marked_summary,
                        event="COMMENT",
                        comments=inline_comments if inline_comments else None,
                    )
                    # Track successful submission via COMMENT fallback
                    if review_state is not None:
                        review_state["submitted"] = True
                        review_state["decision"] = event
                    return f"Review submitted: {event} (as COMMENT due to GitHub limitation)"
                raise
        except Exception as e:
            return f"Error submitting review: {e}"

    @tool
    def security_check_pr() -> str:
        """Проверить изменённые файлы PR на уязвимости безопасности.

        Проверяет ТОЛЬКО файлы, изменённые в PR:
        - Hardcoded secrets (пароли, API ключи)
        - SQL/Command injection
        - Path traversal
        - Unsafe deserialization
        - Weak crypto
        """
        try:
            pr_data = github_client.get_pull_request(pr_number)
            pr = github_client.repo.get_pull(pr_number)

            scannable_ext = ('.py', '.js', '.ts', '.java', '.go', '.kt')
            files_to_check = [f for f in pr_data.files_changed if f.endswith(scannable_ext)]

            if not files_to_check:
                return "INFO: Нет файлов для проверки безопасности в этом PR"

            all_issues = []
            for path in files_to_check:
                content = github_client.get_file_content(path, ref=pr.head.ref)
                if content is None:
                    continue

                issues = check_security_issues(content, path)
                if issues:
                    all_issues.append((path, issues))

            if not all_issues:
                return f"SECURITY OK: Проверено {len(files_to_check)} файлов — уязвимостей не найдено"

            result = [f"SECURITY: Найдены проблемы в {len(all_issues)} файлах:\n"]
            for path, issues in all_issues:
                result.append(f"\n{path}:")
                for issue in issues:
                    result.append(f"  [{issue['severity']}] Line {issue['line']}: {issue['description']}")

            return "\n".join(result)
        except Exception as e:
            return f"Error: {e}"

    return [
        get_pr_diff,
        get_pr_files,
        get_ci_status,
        read_file,
        get_issue_requirements,
        security_check_pr,
        submit_review,
    ]
