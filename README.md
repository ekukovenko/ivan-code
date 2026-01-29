# SDLC Agent

AI-powered SDLC automation system with Code Agent and Reviewer Agent.

## Features

- **Code Agent**: Reads GitHub Issues, generates code fixes, creates Pull Requests
- **Reviewer Agent**: Analyzes PRs, checks CI status, provides code review
- **Iterative cycle**: Automatically addresses review feedback
- **Multiple LLM providers**: OpenRouter, OpenAI, Groq, Mistral, Anthropic
- **Webhook support**: Real-time GitHub event processing
- **Docker support**: Easy deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                        │
│  Issue → PR → CI → Review → Fix → Review → Approve/Merge    │
└─────────────────────────────────────────────────────────────┘
              │                        │
              ▼                        ▼
       ┌─────────────┐         ┌─────────────────┐
       │ Code Agent  │◄───────►│ Reviewer Agent  │
       │  (Isolated) │         │   (Isolated)    │
       └─────────────┘         └─────────────────┘
```

## Quick Start

### 1. Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required variables:
- `LLM_API_KEY`: Your API key (OpenRouter recommended)
- `GITHUB_TOKEN`: GitHub Personal Access Token
- `GITHUB_REPO`: Target repository (owner/repo format)

### 2. Installation

```bash
# Install dependencies
pip install -e .

# Or use Docker
docker-compose up -d
```

### 3. Usage

#### CLI Commands

```bash
# Process issue through full SDLC cycle
python -m src.cli issue 42

# Run Code Agent only
python -m src.cli code 42

# Run Reviewer Agent only
python -m src.cli review 123 --issue 42

# Start webhook server
python -m src.cli server --port 8080
```

#### GitHub Actions

Add secrets to your repository:
- `LLM_API_KEY`: Your LLM provider API key

Add variables (optional):
- `LLM_PROVIDER`: Provider name (default: openrouter)
- `LLM_MODEL`: Model name (default: google/gemini-2.5-flash)

Create an issue with label `auto-fix` or `ai-agent` to trigger the workflow.

## LLM Provider Configuration

The system supports multiple providers via OpenAI-compatible API:

| Provider | LLM_PROVIDER | Default Model |
|----------|--------------|---------------|
| OpenRouter | `openrouter` | `google/gemini-2.5-flash` |
| OpenAI | `openai` | `gpt-4o-mini` |
| Groq | `groq` | `llama-3.3-70b-versatile` |
| Mistral | `mistral` | `mistral-small-latest` |
| Anthropic | `anthropic` | `claude-3-5-sonnet-20241022` |

## Project Structure

```
├── src/
│   ├── agents/           # Code and Reviewer agents
│   ├── core/             # Config and orchestrator
│   ├── github/           # GitHub API client
│   ├── tools/            # Agent tools
│   ├── webhook/          # Webhook server
│   └── cli.py            # CLI interface
├── tests/                # Unit tests
├── .github/workflows/    # GitHub Actions
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## API Endpoints

When running as webhook server:

- `GET /health` - Health check
- `POST /webhook` - GitHub webhook endpoint
- `POST /api/issue/{number}` - Manually trigger issue processing
- `POST /api/review/{number}` - Manually trigger PR review

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run tests
pytest -v
```
