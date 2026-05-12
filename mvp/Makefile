.PHONY: up down clean install pull-models dev health ingest query

# ── Infrastruttura ────────────────────────────────────────────────────────────

## Avvia i 4 servizi Docker (MinIO, PostgreSQL, Qdrant, Ollama)
up:
	docker compose up -d
	@echo ""
	@echo "Servizi avviati. Attendi 10-15s che siano healthy."
	@echo "Poi esegui:  make pull-models   (prima volta, ~5 min)"

## Ferma i servizi (mantiene i dati nei volumi)
down:
	docker compose down

## Ferma e cancella tutti i volumi (reset completo)
clean:
	docker compose down -v
	@echo "Volumi rimossi — DB, bucket e modelli azzerati."

## Stato salute dei container
status:
	docker compose ps

# ── Modelli Ollama ────────────────────────────────────────────────────────────

## Scarica i modelli nella prima installazione (~2.5 GB nomic + ~2 GB llama3.2)
pull-models:
	@echo "Download nomic-embed-text..."
	docker exec mvp_ollama ollama pull nomic-embed-text
	@echo "Download llama3.2..."
	docker exec mvp_ollama ollama pull llama3.2
	@echo "Modelli pronti."

## Elenca modelli installati in Ollama
list-models:
	docker exec mvp_ollama ollama list

# ── Applicazione ──────────────────────────────────────────────────────────────

## Installa dipendenze Python (usa uv se disponibile, altrimenti pip)
install:
	uv pip install -r requirements.txt 2>/dev/null || pip install -r requirements.txt

## Avvia il server FastAPI in modalità sviluppo (hot-reload)
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Test rapidi ───────────────────────────────────────────────────────────────

## Verifica health dell'API
health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool

## Indicizza un PDF di esempio (richiede FILE=percorso/al/file.pdf)
ingest:
	@test -n "$(FILE)" || (echo "Uso: make ingest FILE=mio.pdf" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/ingest \
	     -F "file=@$(FILE)" | python3 -m json.tool

## Esegui una query di esempio
query:
	@test -n "$(Q)" || (echo "Uso: make query Q=\"la tua domanda\"" && exit 1)
	curl -s -X POST http://localhost:8000/api/v1/query \
	     -H "Content-Type: application/json" \
	     -d "{\"query\": \"$(Q)\"}" | python3 -m json.tool

# ── UI ────────────────────────────────────────────────────────────────────────
ui:
	@echo "MinIO Console  →  http://localhost:9001  (minioadmin / minioadmin)"
	@echo "Qdrant         →  http://localhost:6333/dashboard"
	@echo "API Docs       →  http://localhost:8000/docs"
