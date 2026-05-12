.PHONY: up down test logs clean install

## Avvia tutti i 6 servizi in background
up:
	docker compose up -d
	@echo ""
	@echo "Servizi avviati. Attendi ~60s per Neo4j e OpenSearch."
	@echo "Stato servizi:"
	@docker compose ps

## Ferma tutti i servizi (mantiene i volumi)
down:
	docker compose down

## Ferma e rimuove volumi (reset completo)
clean:
	docker compose down -v
	@echo "Volumi rimossi."

## Installa dipendenze Python per il test
install:
	pip install -r requirements-test.txt

## Esegui test di integrazione completo
test:
	python test_stack.py

## Mostra log in tempo reale
logs:
	docker compose logs -f

## Stato salute dei servizi
status:
	docker compose ps

## Accesso rapido MinIO web console
minio-ui:
	@echo "MinIO Console: http://localhost:9001"
	@echo "User: minioadmin / minioadmin"

## Accesso rapido Qdrant dashboard
qdrant-ui:
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"

## Accesso rapido Neo4j browser
neo4j-ui:
	@echo "Neo4j Browser: http://localhost:7474"
	@echo "User: neo4j / ragpassword"
