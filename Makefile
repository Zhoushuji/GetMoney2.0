up:
	./start.sh

down:
	docker compose down

logs:
	docker compose logs -f

backend-test:
	docker compose exec backend pytest

frontend-lint:
	docker compose exec frontend npm run build
