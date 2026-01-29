"""Webhook server for GitHub events."""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.orchestrator import SDLCOrchestrator


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SDLC Agent Webhook",
    description="Webhook server for GitHub events",
    version="0.1.0",
)


class WebhookPayload(BaseModel):
    """Generic webhook payload."""

    action: str
    repository: dict
    sender: dict


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not secret:
        return True  # Skip verification if no secret configured

    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle GitHub webhook events."""
    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body, signature, settings.webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event_type = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    logger.info(f"Received event: {event_type}")

    # Handle different event types
    if event_type == "issues":
        return await handle_issue_event(payload, background_tasks)
    elif event_type == "pull_request":
        return await handle_pr_event(payload, background_tasks)
    elif event_type == "check_run":
        return await handle_check_event(payload, background_tasks)
    else:
        logger.info(f"Ignoring event type: {event_type}")
        return {"status": "ignored", "event": event_type}


async def handle_issue_event(payload: dict, background_tasks: BackgroundTasks):
    """Handle issue events."""
    action = payload.get("action")
    issue = payload.get("issue", {})
    issue_number = issue.get("number")

    logger.info(f"Issue event: {action} #{issue_number}")

    if action == "opened":
        # Check for trigger label or keyword
        labels = [l.get("name", "") for l in issue.get("labels", [])]
        title = issue.get("title", "").lower()
        body = issue.get("body", "").lower()

        # Trigger on specific label or keyword
        should_process = (
            "auto-fix" in labels
            or "ai-agent" in labels
            or "[bot]" in title
            or "/autofix" in body
        )

        if should_process:
            logger.info(f"Triggering SDLC cycle for issue #{issue_number}")
            background_tasks.add_task(process_issue_async, issue_number)
            return {"status": "processing", "issue": issue_number}

    return {"status": "ignored", "action": action}


async def handle_pr_event(payload: dict, background_tasks: BackgroundTasks):
    """Handle pull request events."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")

    logger.info(f"PR event: {action} #{pr_number}")

    if action in ("opened", "synchronize"):
        # Check if this is an auto-generated PR
        head_ref = pr.get("head", {}).get("ref", "")
        if head_ref.startswith("issue-") and "-auto" in head_ref:
            logger.info(f"Triggering review for PR #{pr_number}")
            background_tasks.add_task(review_pr_async, pr_number, pr.get("body", ""))
            return {"status": "reviewing", "pr": pr_number}

    return {"status": "ignored", "action": action}


async def handle_check_event(payload: dict, background_tasks: BackgroundTasks):
    """Handle check run events (CI completion)."""
    action = payload.get("action")
    check_run = payload.get("check_run", {})
    conclusion = check_run.get("conclusion")

    if action == "completed":
        # Get associated PRs
        prs = check_run.get("pull_requests", [])
        for pr in prs:
            pr_number = pr.get("number")
            logger.info(f"CI completed for PR #{pr_number}: {conclusion}")

            # Could trigger re-review here if needed
            if conclusion == "failure":
                logger.info(f"CI failed, reviewer will handle this")

    return {"status": "processed"}


def process_issue_async(issue_number: int):
    """Process issue in background."""
    try:
        orchestrator = SDLCOrchestrator()
        result = orchestrator.process_issue(issue_number)
        logger.info(f"Issue #{issue_number} processed: {result.message}")
    except Exception as e:
        logger.error(f"Error processing issue #{issue_number}: {e}")


def review_pr_async(pr_number: int, body: str):
    """Review PR in background."""
    try:
        orchestrator = SDLCOrchestrator()

        # Extract issue number from PR body
        issue_number = orchestrator._extract_issue_number(body)

        result = orchestrator.reviewer_agent.review_pr(pr_number, issue_number)
        logger.info(f"PR #{pr_number} reviewed: {result['decision']}")
    except Exception as e:
        logger.error(f"Error reviewing PR #{pr_number}: {e}")


# Alternative: Direct API endpoints (for testing without webhooks)


@app.post("/api/issue/{issue_number}")
async def process_issue_api(issue_number: int, background_tasks: BackgroundTasks):
    """Manually trigger SDLC cycle for an issue."""
    background_tasks.add_task(process_issue_async, issue_number)
    return {"status": "processing", "issue": issue_number}


@app.post("/api/review/{pr_number}")
async def review_pr_api(
    pr_number: int,
    issue_number: int | None = None,
    background_tasks: BackgroundTasks = None,
):
    """Manually trigger review for a PR."""
    background_tasks.add_task(review_pr_async, pr_number, "")
    return {"status": "reviewing", "pr": pr_number}
