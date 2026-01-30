"""GitHub API client for SDLC Agent."""

from github import Github, GithubException
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository
from pydantic import BaseModel

from src.core.config import get_settings


class IssueData(BaseModel):
    """Parsed issue data."""

    number: int
    title: str
    body: str
    labels: list[str]
    state: str


class PRData(BaseModel):
    """Parsed PR data."""

    number: int
    title: str
    body: str
    diff: str
    files_changed: list[str]
    state: str
    mergeable: bool | None


class CIStatus(BaseModel):
    """CI/CD status."""

    status: str  # pending | success | failure
    checks: list[dict]


class GitHubClient:
    """GitHub API wrapper for agent operations."""

    def __init__(self, token: str | None = None, repo: str | None = None):
        settings = get_settings()
        self.token = token or settings.github_token
        self.repo_name = repo or settings.github_repo

        self._github = Github(self.token)
        self._repo: Repository | None = None

    @property
    def repo(self) -> Repository:
        """Get repository object."""
        if self._repo is None:
            self._repo = self._github.get_repo(self.repo_name)
        return self._repo

    def get_issue(self, issue_number: int) -> IssueData:
        """Get issue by number."""
        issue = self.repo.get_issue(issue_number)
        return IssueData(
            number=issue.number,
            title=issue.title,
            body=issue.body or "",
            labels=[label.name for label in issue.labels],
            state=issue.state,
        )

    def get_open_issues(self) -> list[IssueData]:
        """Get all open issues."""
        issues = self.repo.get_issues(state="open")
        return [
            IssueData(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                labels=[label.name for label in issue.labels],
                state=issue.state,
            )
            for issue in issues
            if not issue.pull_request  # Exclude PRs
        ]

    def create_branch(self, branch_name: str, base: str = "main") -> str:
        """Create a new branch from base."""
        base_ref = self.repo.get_git_ref(f"heads/{base}")
        base_sha = base_ref.object.sha

        try:
            self.repo.create_git_ref(f"refs/heads/{branch_name}", base_sha)
        except GithubException as e:
            if e.status == 422:  # Branch already exists
                pass
            else:
                raise

        return branch_name

    def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> None:
        """Create or update a file in the repository."""
        try:
            # Try to get existing file
            existing = self.repo.get_contents(path, ref=branch)
            self.repo.update_file(
                path=path,
                message=message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
        except GithubException as e:
            if e.status == 404:
                # File doesn't exist, create it
                self.repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch,
                )
            else:
                raise

    def delete_file(self, path: str, message: str, branch: str) -> None:
        """Delete a file from the repository."""
        try:
            existing = self.repo.get_contents(path, ref=branch)
            self.repo.delete_file(
                path=path,
                message=message,
                sha=existing.sha,
                branch=branch,
            )
        except GithubException as e:
            if e.status != 404:
                raise

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> int:
        """Create a pull request."""
        pr = self.repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
        )
        return pr.number

    def get_pull_request(self, pr_number: int) -> PRData:
        """Get PR data including diff."""
        pr = self.repo.get_pull(pr_number)

        # Get diff
        files_changed = [f.filename for f in pr.get_files()]
        diff_parts = []
        for f in pr.get_files():
            diff_parts.append(f"--- {f.filename}\n{f.patch or ''}")

        return PRData(
            number=pr.number,
            title=pr.title,
            body=pr.body or "",
            diff="\n\n".join(diff_parts),
            files_changed=files_changed,
            state=pr.state,
            mergeable=pr.mergeable,
        )

    def get_pr_ci_status(self, pr_number: int) -> CIStatus:
        """Get CI status for a PR."""
        pr = self.repo.get_pull(pr_number)
        commit = self.repo.get_commit(pr.head.sha)

        checks = []
        combined_status = commit.get_combined_status()

        for status in combined_status.statuses:
            checks.append(
                {
                    "name": status.context,
                    "state": status.state,
                    "description": status.description,
                }
            )

        # Also check GitHub Actions check runs
        check_runs = commit.get_check_runs()
        for run in check_runs:
            description = ""
            if run.output and hasattr(run.output, "summary"):
                description = run.output.summary or ""
            checks.append(
                {
                    "name": run.name,
                    "state": run.conclusion or run.status,
                    "description": description,
                }
            )

        # Determine overall status
        if not checks:
            overall = "pending"
        elif any(c["state"] in ("failure", "error") for c in checks):
            overall = "failure"
        elif any(c["state"] in ("pending", "in_progress", "queued") for c in checks):
            overall = "pending"
        else:
            overall = "success"

        return CIStatus(status=overall, checks=checks)

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        """Add a comment to a PR."""
        pr = self.repo.get_pull(pr_number)
        pr.create_issue_comment(body)

    def create_pr_review(
        self,
        pr_number: int,
        body: str,
        event: str = "COMMENT",  # APPROVE | REQUEST_CHANGES | COMMENT
        comments: list[dict] | None = None,
    ) -> None:
        """Create a PR review."""
        pr = self.repo.get_pull(pr_number)
        pr.create_review(
            body=body,
            event=event,
            comments=comments or [],
        )

    def add_issue_comment(self, issue_number: int, body: str) -> None:
        """Add a comment to an issue."""
        issue = self.repo.get_issue(issue_number)
        issue.create_comment(body)

    def close_issue(self, issue_number: int) -> None:
        """Close an issue."""
        issue = self.repo.get_issue(issue_number)
        issue.edit(state="closed")

    def get_file_content(self, path: str, ref: str = "main") -> str | None:
        """Get file content from repository."""
        try:
            content = self.repo.get_contents(path, ref=ref)
            if isinstance(content, list):
                return None  # It's a directory
            return content.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def list_files(self, path: str = "", ref: str = "main") -> list[str]:
        """List files in a directory."""
        try:
            contents = self.repo.get_contents(path, ref=ref)
            if not isinstance(contents, list):
                contents = [contents]

            files = []
            for content in contents:
                if content.type == "file":
                    files.append(content.path)
                elif content.type == "dir":
                    files.extend(self.list_files(content.path, ref))

            return files
        except GithubException as e:
            if e.status == 404:
                return []
            raise
