# Trading Exchange

A learning-grade trading exchange backend with simple UI.

## Which topics involves the project

- **Matching engine** — in-process order book that matches buy/sell orders by price-time priority.
- **Event-driven architecture** — trades flow through a queue to an asynchronous settlement worker.
- **Cloud services** — S3, SQS, SNS, Kinesis, DynamoDB, Secrets Manager, IAM, CloudWatch (emulated by LocalStack, so there are no AWS costs).
- **Observability & testing** — structured logs and tested core functionality.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| API | FastAPI + Uvicorn |
| Persistence | PostgreSQL (SQLAlchemy 2.0, Alembic migrations) |
| Cloud (emulated) | LocalStack + Terraform |
| Tests | pytest |
| Orchestration | Docker Compose |

### Running tests locally (without Docker)

The backend package is rooted at `backend/`, so tests run from there:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt -r ../requirements-dev.txt
python -m pytest
```

Or simply `make test` from the repo root.

## Roadmap

- [x] **Sprint 1** — Project scaffold, Docker Compose, health check
- [ ] **Sprint 2** — Matching engine + order book + tests
- [ ] **Sprint 3** — REST API + database + migrations
- [ ] **Sprint 4** — Terraform + LocalStack resources
- [ ] **Sprint 5** — Asynchronous settlement worker
- [ ] **Sprint 6** — Frontend + WebSocket real-time updates
- [ ] **Sprint 7** — Polish: CI, load test, screenshots
