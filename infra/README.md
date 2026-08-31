# Infrastructure

The root `compose.yaml` includes `docker-compose.yml` from this directory so the
complete development stack starts with `docker compose up --build` at the
repository root.

Ollama starts without pulling a model. Set `NEXUS_OLLAMA_MODEL` and explicitly
pull that model only when you are ready to use it.

