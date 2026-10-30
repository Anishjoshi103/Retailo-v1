.PHONY: config build up down restart logs ps backend-shell migrate makemigrations test clean-volumes

config:
	@test -f .env || (echo "Missing .env. Run: cp .env.example .env, then set a strong local password."; exit 1)
	docker compose config --quiet

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

backend-shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web python manage.py test

clean-volumes:
	@printf "This permanently deletes local SQL Server data. Type DELETE to continue: "; read answer; test "$$answer" = "DELETE"
	docker compose down --volumes
