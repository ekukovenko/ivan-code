"""CLI interface for SDLC Agent."""

import argparse
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings
from src.core.orchestrator import SDLCOrchestrator
from src.github.client import GitHubClient
from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent


def main():
    parser = argparse.ArgumentParser(
        description="SDLC Agent - AI-powered development automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a single issue through full SDLC cycle
    sdlc-agent issue 42

    # Run Code Agent only (create PR without review)
    sdlc-agent code 42

    # Run Reviewer Agent only (review existing PR)
    sdlc-agent review 123 --issue 42

    # Start webhook server
    sdlc-agent server --port 8080
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Issue command - full SDLC cycle
    issue_parser = subparsers.add_parser("issue", help="Process issue through full SDLC")
    issue_parser.add_argument("number", type=int, help="Issue number")

    # Code command - Code Agent only
    code_parser = subparsers.add_parser("code", help="Generate code for issue (no review)")
    code_parser.add_argument("number", type=int, help="Issue number")

    # Review command - Reviewer Agent only
    review_parser = subparsers.add_parser("review", help="Review a pull request")
    review_parser.add_argument("pr_number", type=int, help="PR number")
    review_parser.add_argument("--issue", type=int, help="Related issue number")

    # Server command - webhook server
    server_parser = subparsers.add_parser("server", help="Start webhook server")
    server_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")

    # UI command - TUI interface
    ui_parser = subparsers.add_parser("ui", help="Start interactive TUI")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Validate configuration
    settings = get_settings()
    if not settings.llm_api_key:
        print("Error: LLM_API_KEY not set")
        print("Please set it in .env file or environment variable")
        sys.exit(1)

    if args.command != "server" and not settings.github_token:
        print("Error: GITHUB_TOKEN not set")
        print("Please set it in .env file or environment variable")
        sys.exit(1)

    # Execute command
    if args.command == "issue":
        run_issue(args.number)
    elif args.command == "code":
        run_code(args.number)
    elif args.command == "review":
        run_review(args.pr_number, args.issue)
    elif args.command == "server":
        run_server(args.host, args.port)
    elif args.command == "ui":
        run_ui()


def run_issue(issue_number: int):
    """Run full SDLC cycle for an issue."""
    print(f"\n{'='*50}")
    print(f"Processing Issue #{issue_number}")
    print(f"{'='*50}\n")

    orchestrator = SDLCOrchestrator()
    result = orchestrator.process_issue(issue_number)

    print(f"\n{'='*50}")
    print("SDLC Cycle Complete")
    print(f"{'='*50}")
    print(f"Success: {result.success}")
    print(f"PR Number: {result.pr_number}")
    print(f"Iterations: {result.iterations}")
    print(f"Final Decision: {result.final_decision}")
    print(f"Message: {result.message}")


def run_code(issue_number: int):
    """Run Code Agent only."""
    print(f"\n{'='*50}")
    print(f"Code Agent - Issue #{issue_number}")
    print(f"{'='*50}\n")

    agent = CodeAgent()
    result = agent.process_issue(issue_number)

    print(f"\n{'='*50}")
    print("Code Agent Complete")
    print(f"{'='*50}")
    print(f"Success: {result['success']}")
    print(f"PR Number: {result['pr_number']}")
    print(f"Branch: {result['branch']}")
    print(f"Message: {result['message']}")


def run_review(pr_number: int, issue_number: int | None):
    """Run Reviewer Agent only."""
    print(f"\n{'='*50}")
    print(f"Reviewer Agent - PR #{pr_number}")
    print(f"{'='*50}\n")

    agent = ReviewerAgent()
    result = agent.review_pr(pr_number, issue_number)

    print(f"\n{'='*50}")
    print("Review Complete")
    print(f"{'='*50}")
    print(f"Decision: {result['decision']}")
    print(f"Needs Changes: {result['needs_changes']}")
    print(f"\nSummary:\n{result['summary']}")


def run_server(host: str, port: int):
    """Start webhook server."""
    print(f"\n{'='*50}")
    print(f"Starting Webhook Server on {host}:{port}")
    print(f"{'='*50}\n")

    try:
        import uvicorn
        from src.webhook.server import app

        uvicorn.run(app, host=host, port=port)
    except ImportError:
        print("Error: uvicorn not installed")
        print("Install with: pip install uvicorn")
        sys.exit(1)


def run_ui():
    """Start TUI interface."""
    try:
        from src.ui.app import run_tui
        run_tui()
    except ImportError as e:
        print(f"Error: TUI dependencies not installed: {e}")
        print("Install with: pip install textual rich")
        sys.exit(1)


if __name__ == "__main__":
    main()
