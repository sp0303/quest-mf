# quest-mf

Research platform for screening Indian mutual funds using rolling-window, benchmark-relative, risk- and friction-aware analysis, validated by walk-forward backtesting.

> Research only — not investment advice.

## Stack
React + TypeScript (Vite) · Python 3.12 FastAPI microservices (venv) · PostgreSQL 16 + TimescaleDB · Redis · OCI

## Docs
| Doc | What |
|---|---|
| [AGENTS.md](AGENTS.md) | **Binding rules** for agents and contributors |
| [HLD](docs/architecture/HLD.md) | High-level design: services, flows, latency, 1B-row scale |
| [LLD — Backend](docs/architecture/LLD-backend.md) | Services, APIs, workers, events |
| [LLD — Database](docs/architecture/LLD-database.md) | DDL, hypertables, partitions, Redis keys |
| [LLD — Frontend](docs/architecture/LLD-frontend.md) | Component structure, lazy loading, state, design mapping |
| [Deployment — OCI](docs/architecture/DEPLOYMENT-OCI.md) | Port registry, network, Nginx, Compose, CI/CD |
| [Spec v2](docs/mf_quant_screener_spec_v2.md) | Quant research spec (reviewed & extended) |
| [Spec v1](docs/mf_quant_screener_spec_v1.md) | Original draft |
| [DESIGN.md](docs/DESIGN.md) | UI design system |

## Getting started
```bash
git clone https://github.com/sp0303/quest-mf.git
cd quest-mf
```

Backend (venv):
```bash
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt && pip install -e libs/common -e libs/quant
```

Frontend:
```bash
cd frontend && npm ci && npm run dev
```

## Contributing
```bash
git checkout -b feat/<name>
git add -A
git commit -m "feat: <message>"
git push -u origin feat/<name>
```
Then open a pull request into `main`. See [AGENTS.md](AGENTS.md) §8.
