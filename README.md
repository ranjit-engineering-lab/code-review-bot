# Intelligent Code Review Bot

Automated GitHub PR reviews powered by GPT-4, LangChain, and FastAPI : deployed as a GitHub App running on AWS Lambda or Docker.

The bot performs **three parallel review passes** on every PR:
- **Security** — injections, hardcoded secrets, weak crypto, missing auth
- **Performance** — N+1 queries, blocking I/O, inefficient algorithms
- **Style** — PEP8, complexity, naming, type annotations, DRY

---

## Architecture

```
GitHub PR Event
      │
      ▼
GitHub Webhook (HMAC verified)
      │
      ▼
FastAPI /api/v1/webhook/github
      │
      ▼ (background task)
PRReviewService
      │
      ├── GitHubAppClient.get_pr_files()
      │
      ├── AIReviewOrchestrator
      │     ├── Security Pass  (LangChain → GPT-4)
      │     ├── Performance Pass
      │     └── Style Pass
      │
      └── GitHubAppClient.post_review()
             │
             └── GitHub PR Review + Commit Status
```

**Deployment options:**
- **AWS Lambda** — via Mangum ASGI adapter + ECR container image
- **Docker** — via `docker/docker-compose.yml`

---

## Quick Start

### 1. Create a GitHub App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Set **Webhook URL** to your deployed endpoint: `https://your-domain/api/v1/webhook/github`
3. Set **Webhook secret** (save it)
4. Grant permissions: **Pull requests** (Read & Write), **Commit statuses** (Read & Write)
5. Subscribe to **Pull request** events
6. Generate a **private key** and download the `.pem` file

### 2. Configure Environment

```bash
cp .env.example .env
# Fill in GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET, OPENAI_API_KEY
```

### 3. Run Locally

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Start the server
uvicorn app.main:app --reload --port 8000

# Expose via ngrok for GitHub webhook testing
ngrok http 8000
```

Or with Docker:

```bash
docker compose -f docker/docker-compose.yml up
# With ngrok:
docker compose -f docker/docker-compose.yml --profile ngrok up
```

### 4. Run Tests

```bash
pytest tests/ -v --cov=app
```

---

## Project Structure

```
code-review-bot/
├── app/
│   ├── main.py                    # FastAPI app + middleware
│   ├── api/
│   │   ├── webhook_router.py      # GitHub webhook endpoint
│   │   └── health_router.py       # Health & readiness checks
│   ├── core/
│   │   ├── config.py              # Pydantic settings (env vars)
│   │   └── logging_config.py      # Structured logging setup
│   ├── models/
│   │   ├── github_models.py       # GitHub webhook payload models
│   │   └── review_models.py       # CodeFinding, ReviewResult, etc.
│   ├── services/
│   │   ├── github_client.py       # GitHub App auth + REST API
│   │   ├── ai_reviewer.py         # LangChain orchestrator (3 passes)
│   │   └── pr_review_service.py   # Review pipeline coordinator
│   └── utils/
│       ├── signature_verifier.py  # HMAC webhook verification
│       └── diff_parser.py         # Unified diff utilities
├── lambda/
│   └── handler.py                 # AWS Lambda + Mangum entry point
├── docker/
│   ├── Dockerfile                 # Multi-stage production image
│   └── docker-compose.yml         # Local dev + optional ngrok
├── .github/
│   └── workflows/
│       └── ci-cd.yml              # Lint → Test → Build → Deploy
├── tests/
│   ├── test_webhook_router.py
│   ├── test_diff_parser.py
│   └── test_review_models.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                 # Ruff, mypy, pytest, coverage config
└── .env.example
```

---

## Deploy to AWS Lambda

### Prerequisites
- AWS ECR repository named `code-review-bot`
- Lambda function configured to use container images
- OIDC-based GitHub Actions IAM role

### Configure GitHub Secrets

```
AWS_DEPLOY_ROLE_ARN     = arn:aws:iam::123456789:role/github-deploy-role
LAMBDA_FUNCTION_NAME    = code-review-bot
```

Push to `main` — the CI/CD pipeline will:
1. Lint + test
2. Build Docker image → push to ECR
3. Update Lambda → smoke test

---

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_APP_ID` | GitHub App ID | required |
| `GITHUB_PRIVATE_KEY` | RSA private key (PEM) | required |
| `GITHUB_WEBHOOK_SECRET` | Webhook HMAC secret | required |
| `OPENAI_API_KEY` | OpenAI API key | required |
| `OPENAI_MODEL` | Model to use | `gpt-4-turbo-preview` |
| `MIN_SEVERITY_TO_BLOCK` | Min severity to request changes | `HIGH` |
| `MAX_FILES_PER_PR` | Max files to review | `50` |
| `MAX_DIFF_LINES` | Max diff lines per review | `2000` |
| `ENABLE_SECURITY_CHECKS` | Enable security pass | `true` |
| `ENABLE_PERFORMANCE_CHECKS` | Enable performance pass | `true` |
| `ENABLE_STYLE_CHECKS` | Enable style pass | `true` |

---

## License

MIT
