.PHONY: up down logs backend frontend test migrate
up:        ; docker compose up --build
down:      ; docker compose down
logs:      ; docker compose logs -f
backend:   ; cd backend && uvicorn app.main:app --reload
frontend:  ; cd frontend && npm run dev
test:      ; cd backend && pytest -q
migrate:   ; cd backend && alembic upgrade head
