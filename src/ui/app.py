"""Textual TUI for SDLC Agent."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    Log,
    Label,
    LoadingIndicator,
    Rule,
)
from textual.binding import Binding
from textual import on, work
from textual.worker import Worker, WorkerState

from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

from src.core.config import get_settings
from src.core.orchestrator import SDLCOrchestrator, CycleResult
from src.github.client import GitHubClient


class StatusPanel(Static):
    """Panel showing current status."""

    DEFAULT_CSS = """
    StatusPanel {
        height: 3;
        padding: 0 1;
        background: $surface;
        border: solid $primary;
    }
    """

    def __init__(self):
        super().__init__()
        self.status = "Ready"
        self.iteration = 0
        self.max_iterations = 5

    def update_status(self, status: str, iteration: int = 0):
        self.status = status
        self.iteration = iteration
        self.refresh()

    def render(self):
        if self.iteration > 0:
            return f"Status: {self.status}  |  Iteration: {self.iteration}/{self.max_iterations}"
        return f"Status: {self.status}"


class AgentPanel(Static):
    """Panel for agent output."""

    DEFAULT_CSS = """
    AgentPanel {
        height: 100%;
        padding: 1;
        background: $surface;
        border: solid $secondary;
    }
    AgentPanel .title {
        text-style: bold;
        color: $text;
    }
    """

    def __init__(self, title: str, agent_type: str):
        super().__init__()
        self.title_text = title
        self.agent_type = agent_type
        self.content = ""

    def update_content(self, content: str):
        self.content = content
        self.refresh()

    def append_content(self, content: str):
        self.content += content
        self.refresh()

    def clear(self):
        self.content = ""
        self.refresh()

    def render(self):
        color = "cyan" if self.agent_type == "code" else "magenta"
        return Panel(
            self.content or "Waiting...",
            title=f"[bold {color}]{self.title_text}[/]",
            border_style=color,
        )


class SDLCAgentApp(App):
    """SDLC Agent TUI Application."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto auto;
    }

    #main-container {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
        height: 100%;
        padding: 1;
    }

    #left-panel {
        height: 100%;
        margin-right: 1;
    }

    #right-panel {
        height: 100%;
    }

    #input-container {
        height: auto;
        padding: 1;
        background: $surface;
    }

    #input-row {
        height: auto;
    }

    Input {
        width: 1fr;
        margin-right: 1;
    }

    Button {
        width: auto;
        min-width: 16;
    }

    #log-container {
        height: 10;
        padding: 0 1;
        background: $surface-darken-1;
        border: solid $primary-darken-2;
    }

    Log {
        height: 100%;
    }

    LoadingIndicator {
        height: 1;
    }

    .agent-container {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_logs", "Clear Logs"),
        Binding("escape", "cancel", "Cancel"),
    ]

    TITLE = "SDLC Agent"
    SUB_TITLE = "AI-Powered Development Automation"

    def __init__(self):
        super().__init__()
        self.orchestrator: SDLCOrchestrator | None = None
        self.current_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        yield Container(
            Vertical(
                StatusPanel(),
                AgentPanel("Code Agent", "code"),
                id="left-panel",
                classes="agent-container",
            ),
            Vertical(
                Static(id="iteration-info"),
                AgentPanel("Reviewer Agent", "reviewer"),
                id="right-panel",
                classes="agent-container",
            ),
            id="main-container",
        )

        yield Container(
            Horizontal(
                Input(placeholder="Enter Issue number...", id="issue-input"),
                Button("Process Issue", id="process-btn", variant="primary"),
                Button("Review PR", id="review-btn", variant="default"),
                id="input-row",
            ),
            id="input-container",
        )

        yield Container(
            Log(id="log", highlight=True),
            id="log-container",
        )

        yield Footer()

    def on_mount(self):
        """Initialize on mount."""
        self.log_message("SDLC Agent initialized")
        self.log_message(f"Provider: {get_settings().llm_provider}")
        self.log_message(f"Model: {get_settings().default_model}")
        self.log_message(f"Repository: {get_settings().github_repo}")
        self.log_message("Enter Issue number and click 'Process Issue' to start")

    def log_message(self, message: str):
        """Add message to log."""
        log = self.query_one("#log", Log)
        log.write_line(message)

    def update_status(self, status: str, iteration: int = 0):
        """Update status panel."""
        panel = self.query_one(StatusPanel)
        panel.update_status(status, iteration)

    def get_code_panel(self) -> AgentPanel:
        """Get Code Agent panel."""
        return self.query("#left-panel AgentPanel").first()

    def get_reviewer_panel(self) -> AgentPanel:
        """Get Reviewer Agent panel."""
        return self.query("#right-panel AgentPanel").first()

    @on(Button.Pressed, "#process-btn")
    async def on_process_clicked(self):
        """Handle Process Issue button click."""
        input_widget = self.query_one("#issue-input", Input)
        issue_num = input_widget.value.strip()

        if not issue_num.isdigit():
            self.log_message("Error: Please enter a valid issue number")
            return

        issue_number = int(issue_num)
        self.log_message(f"Starting SDLC cycle for Issue #{issue_number}...")

        # Clear panels
        self.get_code_panel().clear()
        self.get_reviewer_panel().clear()

        # Start processing
        self.run_sdlc_cycle(issue_number)

    @on(Button.Pressed, "#review-btn")
    async def on_review_clicked(self):
        """Handle Review PR button click."""
        input_widget = self.query_one("#issue-input", Input)
        pr_num = input_widget.value.strip()

        if not pr_num.isdigit():
            self.log_message("Error: Please enter a valid PR number")
            return

        pr_number = int(pr_num)
        self.log_message(f"Starting review for PR #{pr_number}...")

        self.get_reviewer_panel().clear()
        self.run_review(pr_number)

    @work(exclusive=True, thread=True)
    def run_sdlc_cycle(self, issue_number: int):
        """Run SDLC cycle in background thread."""
        from src.agents.code_agent import CodeAgent
        from src.agents.reviewer_agent import ReviewerAgent

        try:
            self.call_from_thread(self.update_status, "Initializing...", 0)

            github = GitHubClient()
            code_agent = CodeAgent(github)
            reviewer_agent = ReviewerAgent(github)

            # Get issue info
            self.call_from_thread(self.update_status, "Fetching Issue...", 0)
            issue = github.get_issue(issue_number)
            self.call_from_thread(
                self.log_message, f"Issue: {issue.title}"
            )
            self.call_from_thread(
                self.get_code_panel().update_content,
                f"**Issue #{issue_number}:** {issue.title}\n\n{issue.body}\n\n---\n\nGenerating code...",
            )

            # Code Agent
            self.call_from_thread(self.update_status, "Code Agent working...", 1)
            code_result = code_agent.process_issue(issue_number)

            if not code_result["success"]:
                self.call_from_thread(
                    self.get_code_panel().update_content,
                    f"**Failed:** {code_result['message']}",
                )
                self.call_from_thread(self.update_status, "Failed", 0)
                return

            pr_number = code_result["pr_number"]
            branch = code_result["branch"]

            self.call_from_thread(
                self.get_code_panel().update_content,
                f"**PR #{pr_number} created**\n\nBranch: `{branch}`\n\n{code_result['message']}",
            )
            self.call_from_thread(self.log_message, f"PR #{pr_number} created on branch {branch}")

            # Review loop
            max_iterations = get_settings().max_iterations
            for iteration in range(1, max_iterations + 1):
                self.call_from_thread(
                    self.update_status, f"Reviewer Agent (iteration {iteration})...", iteration
                )
                self.call_from_thread(
                    self.get_reviewer_panel().update_content,
                    f"**Reviewing PR #{pr_number}**\n\nIteration {iteration}/{max_iterations}\n\nAnalyzing...",
                )

                review_result = reviewer_agent.review_pr(pr_number, issue_number)
                decision = review_result["decision"]

                self.call_from_thread(
                    self.get_reviewer_panel().update_content,
                    f"**Decision: {decision}**\n\n{review_result['summary'][:1000]}",
                )
                self.call_from_thread(self.log_message, f"Review decision: {decision}")

                if decision == "APPROVE":
                    self.call_from_thread(self.update_status, "Approved!", iteration)
                    self.call_from_thread(
                        self.log_message, f"PR #{pr_number} approved after {iteration} iteration(s)"
                    )
                    return

                if decision == "REQUEST_CHANGES" and iteration < max_iterations:
                    self.call_from_thread(
                        self.update_status, f"Code Agent fixing (iteration {iteration})...", iteration
                    )
                    self.call_from_thread(
                        self.get_code_panel().append_content,
                        f"\n\n---\n\n**Iteration {iteration + 1}:** Addressing feedback...",
                    )

                    fix_result = code_agent.apply_review_feedback(
                        pr_number, review_result["summary"], branch
                    )

                    if not fix_result["success"]:
                        self.call_from_thread(self.update_status, "Fix failed", iteration)
                        return

                    self.call_from_thread(
                        self.get_code_panel().append_content,
                        f"\n\nChanges applied: {fix_result['message']}",
                    )

            self.call_from_thread(self.update_status, "Max iterations reached", max_iterations)
            self.call_from_thread(
                self.log_message, f"Max iterations ({max_iterations}) reached"
            )

        except Exception as e:
            self.call_from_thread(self.log_message, f"Error: {str(e)}")
            self.call_from_thread(self.update_status, "Error", 0)

    @work(exclusive=True, thread=True)
    def run_review(self, pr_number: int):
        """Run review only in background thread."""
        from src.agents.reviewer_agent import ReviewerAgent

        try:
            self.call_from_thread(self.update_status, "Reviewing...", 0)

            github = GitHubClient()
            reviewer = ReviewerAgent(github)

            self.call_from_thread(
                self.get_reviewer_panel().update_content,
                f"**Reviewing PR #{pr_number}**\n\nAnalyzing diff and CI status...",
            )

            result = reviewer.review_pr(pr_number)

            self.call_from_thread(
                self.get_reviewer_panel().update_content,
                f"**Decision: {result['decision']}**\n\n{result['summary']}",
            )
            self.call_from_thread(self.update_status, f"Review: {result['decision']}", 0)
            self.call_from_thread(self.log_message, f"Review completed: {result['decision']}")

        except Exception as e:
            self.call_from_thread(self.log_message, f"Error: {str(e)}")
            self.call_from_thread(self.update_status, "Error", 0)

    def action_clear_logs(self):
        """Clear log panel."""
        log = self.query_one("#log", Log)
        log.clear()

    def action_cancel(self):
        """Cancel current operation."""
        if self.current_worker and self.current_worker.state == WorkerState.RUNNING:
            self.current_worker.cancel()
            self.log_message("Operation cancelled")
            self.update_status("Cancelled", 0)


def run_tui():
    """Run the TUI application."""
    app = SDLCAgentApp()
    app.run()
