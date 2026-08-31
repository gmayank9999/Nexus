# Infrastructure

The root `compose.yaml` includes `docker-compose.yml` from this directory so the
complete development stack starts with `docker compose up --build` at the
repository root.

The core stack does not pull the large Ollama image. Start that optional service
with `docker compose --profile local-model up --build`, then set
`NEXUS_OLLAMA_MODEL` and explicitly pull a model only when you are ready to use
it.
