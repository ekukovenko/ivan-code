"""CLI interface for SDLC Agent."""

import argparse
import sys
import os
import logging

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings
from src.core.orchestrator import SDLCOrchestrator
from src.github.client import GitHubClient
from src.agents.code_agent import CodeAgent
from src.agents.reviewer_agent import ReviewerAgent

# Configure logging to be less verbose by default
logging.basicConfig(level=logging.WARNING, format='%(message)s')


def handle_error(e: Exception, context: str = "") -> None:
    """Handle errors with user-friendly messages."""
    error_type = type(e).__name__

    # GitHub errors
    if "UnknownObjectException" in error_type or "404" in str(e):
        print(f"\n❌ Error: {context} not found")
        print("   Check that the issue/PR number exists and you have access to the repository")
        sys.exit(1)

    if "BadCredentialsException" in error_type or "401" in str(e):
        print("\n❌ Error: Invalid GitHub token")
        print("   Check your GITHUB_TOKEN in .env file")
        sys.exit(1)

    if "403" in str(e) and "rate limit" in str(e).lower():
        print("\n❌ Error: GitHub API rate limit exceeded")
        print("   Wait a few minutes and try again")
        sys.exit(1)

    if "403" in str(e):
        print("\n❌ Error: Access denied")
        print("   Check that your GITHUB_TOKEN has the required permissions")
        sys.exit(1)

    # LLM errors
    if "api" in str(e).lower() and ("key" in str(e).lower() or "auth" in str(e).lower()):
        print("\n❌ Error: LLM API authentication failed")
        print("   Check your LLM_API_KEY in .env file")
        sys.exit(1)

    if "timeout" in str(e).lower() or "connection" in str(e).lower():
        print("\n❌ Error: Connection timeout")
        print("   Check your internet connection and try again")
        sys.exit(1)

    # Generic error
    print(f"\n❌ Error: {e}")
    if os.getenv("DEBUG"):
        import traceback
        traceback.print_exc()
    else:
        print("   Set DEBUG=1 for full traceback")
    sys.exit(1)


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

    try:
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
    except Exception as e:
        handle_error(e, f"Issue #{issue_number}")


def run_code(issue_number: int):
    """Run Code Agent only."""
    print(f"\n{'='*50}")
    print(f"Code Agent - Issue #{issue_number}")
    print(f"{'='*50}\n")

    try:
        agent = CodeAgent()
        result = agent.process_issue(issue_number)

        print(f"\n{'='*50}")
        print("Code Agent Complete")
        print(f"{'='*50}")
        print(f"Success: {result['success']}")
        print(f"PR Number: {result['pr_number']}")
        print(f"Branch: {result['branch']}")
        print(f"Message: {result['message']}")
    except Exception as e:
        handle_error(e, f"Issue #{issue_number}")


def run_review(pr_number: int, issue_number: int | None):
    """Run Reviewer Agent only."""
    print(f"\n{'='*50}")
    print(f"Reviewer Agent - PR #{pr_number}")
    print(f"{'='*50}\n")

    try:
        agent = ReviewerAgent()
        result = agent.review_pr(pr_number, issue_number)

        print(f"\n{'='*50}")
        print("Review Complete")
        print(f"{'='*50}")
        print(f"Decision: {result['decision']}")
        print(f"Needs Changes: {result['needs_changes']}")
        print(f"\nSummary:\n{result['summary']}")
    except Exception as e:
        handle_error(e, f"PR #{pr_number}")


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
