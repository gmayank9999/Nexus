# NEXUS Server

FastAPI entry point for NEXUS. From this directory, install development
dependencies and start the service:

```bash
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Liveness is exposed at `GET /health`; dependency readiness is exposed at
`GET /ready`.

