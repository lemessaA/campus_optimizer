# Campus Operations Optimization System

Multi-agent system for smart campus management: scheduling, equipment booking, energy optimization, and customer support.

## Overview

- **Purpose**: Automate and optimize campus operations through AI agents
- **Architecture**: FastAPI backend + LangGraph supervisor + specialized agents (Scheduling, Equipment, Energy, Support, Notification, Analytics, Health, Insights)
- **Key components**: Supervisor orchestrates workflows; agents handle domain-specific tasks; Redis for cache/metrics; PostgreSQL for persistence

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis

### Setup

```bash
# Clone and enter project
cd campus_optimizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template and configure
cp .env.sample .env
# Edit .env with your DATABASE_URL, REDIS_URL, GROQ_API_KEY, etc.
```

### Run

```bash
# Start API server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal: start Streamlit UI
streamlit run src/ui/streamlit_app.py
```

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **UI**: http://localhost:8501

## Configuration

See [.env.sample](.env.sample) for all environment variables. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:qaws@localhost:5432/campus` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `GROQ_API_KEY` | Groq API key for LLM (optional) | — |
| `SECRET_KEY` | JWT secret (change in production) | `your-secret-key-here` |

## Testing

```bash
# Run all tests
pytest src/tests/ -v

# With coverage (install pytest-cov first: pip install pytest-cov)
pytest src/tests/ --cov=src --cov-report=html
# Open htmlcov/index.html for report
```

## Deployment

- **Docker**: Use `docker-compose up` (see [docker-compose.yml](docker-compose.yml))
- **Production**: Set `ENVIRONMENT=production`, use gunicorn, restrict CORS, enable auth
- **Health check**: `GET /health` returns system status

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and recovery steps.

## License

MIT
