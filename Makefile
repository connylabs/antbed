.PHONY: format format-test check fix clean clean-build clean-pyc clean-test coverage install pylint pylint-quick pyre test publish uv-check publish isort isort-check docker-push docker-build migrate

APP_ENV ?= dev
VERSION := `cat VERSION`
package := antbed
NAMESPACE := antbed-dev
MIGRATE_BINARY = goose
GOTOOLS =
GOTOOLS += $(MIGRATE_BINARY)
CONTAINERIZE_BUILD ?= false

DATABASE_NAME ?= pythonapp-$(APP_ENV)
MIGRATION_DIR ?= ./$(package)/migrations
DATABASE_USER ?= antbed
DATABASE_PASSWORD ?= antbed
DATABASE_HOST ?= localhost
ifeq ($(APP_ENV), test)
DATABASE_URL ?= $(DATABASE_TEST)
DATABASE_PORT ?= 5434
else
DATABASE_URL ?= $(DATABASE_DEV)
DATABASE_PORT ?= 5438
endif
DATABASE_DATA ?= ./.cache/db/$(DATABASE_NAME)/data
DATABASE_TEST ?= postgres://$(DATABASE_USER):$(DATABASE_PASSWORD)@$(DATABASE_HOST):$(DATABASE_PORT)/$(DATABASE_NAME)?sslmode=disable
DATABASE_MIGRATE ?= postgres://$(DATABASE_USER):$(DATABASE_PASSWORD)@$(DATABASE_HOST):$(DATABASE_PORT)/$(DATABASE_NAME)?sslmode=disable
DATABASE_DEV ?= postgres://$(DATABASE_USER):$(DATABASE_PASSWORD)@$(DATABASE_HOST):$(DATABASE_PORT)/$(DATABASE_NAME)?sslmode=disable

DOCKER_BUILD_ARGS ?= "-q"

all: fix

tools: # $(TOOLS)
ifeq ($(CONTAINERIZE_BUILD), false)
	$(MAKE)  $(TOOLS)
else
	$(MAKE) -s $@-containerized
endif

.PHONY: clear-test-db create-cache-db clean-db .check-clear
clear-test-db:
ifeq ($(APP_ENV), test)
	rm -rf cache/db/antbed-test
endif


clear-db:
	rm -rf $(DATABASE_DATA)

create-cache-db:
	mkdir -p $(DATABASE_DATA)

prep-db: clear-test-db create-cache-db
	-@docker kill $(DATABASE_NAME)-pg
	echo @database_url=$(DATABASE_URL)
	@docker run --rm --name $(DATABASE_NAME)-pg -v $(DATABASE_DATA):/var/lib/postgresql/data -d -p $(DATABASE_PORT):5432 -e POSTGRES_USER=$(DATABASE_USER) -e POSTGRES_PASSWORD=$(DATABASE_PASSWORD) -e POSTGRES_DB=$(DATABASE_NAME) postgres:15
	until docker exec $(DATABASE_NAME)-pg /usr/bin/pg_isready -d $(DATABASE_NAME) -h $(DATABASE_HOST) -p 5432 -U $(DATABASE_USER) -q; do sleep 1 ; done
	$(MAKE) --no-print-directory DATABASE_URL=$(DATABASE_URL) migrate

stop-db:
	-docker kill $(DATABASE_NAME)-pg

migrate: $(MIGRATE_BINARY)
	$(MIGRATE_BINARY) -dir $(MIGRATION_DIR) postgres "$(DATABASE_URL)" up

migrate-up: migrate

migrate-down: $(MIGRATE_BINARY)
	$(MIGRATE_BINARY) -dir $(MIGRATION_DIR) postgres "$(DATABASE_URL)" down

$(MIGRATE_BINARY):
	go install github.com/pressly/goose/v3/cmd/goose@latest

prep-db-restart: stop-db prep-db

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "dist - package"
	@echo "install - install the package to the active Python's site-packages"
	@echo "migrate - Execute a db migration"

clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -not -path ".venv/*" -not -path ".cache/*" -prune  -name '*.egg-info' -exec rm -fr {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '*.egg' -exec rm -f {} +

clean-pyc:
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '*.pyc' -exec rm -f {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '*.pyo' -exec rm -f {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '*~' -exec rm -f {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name 'flycheck_*' -exec rm -f {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '__pycache__' -exec rm -fr {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '.mypy_cache' -exec rm -fr {} +
	find . -not -path ".venv/*" -not -path ".cache/*" -prune -name '.pyre' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -f coverage.xml
	rm -f report.xml
test:
	ANTBED_CONFIG=tests/data/test_config.yaml uv run pytest --cov=$(package) --verbose tests --cov-report=html --cov-report=term --cov-report xml:coverage.xml --cov-report=term-missing --junitxml=report.xml --asyncio-mode=auto

coverage:
	uv run coverage run --source $(package) setup.py test
	uv run coverage report -m
	uv run coverage html
	$(BROWSER) htmlcov/index.html

install: clean
	uv install

pylint-quick:
	uv run pylint --rcfile=.pylintrc $(package)  -E -r y

pylint:
	uv run pylint --rcfile=".pylintrc" $(package)

check: format-test isort-check ruff uv-check

pyre: pyre-check

pyre-check:
	uv run pyre --noninteractive check 2>/dev/null

format:
	uv run ruff format $(package)

format-test:
	uv run ruff format $(package) --check

uv-check:
	uv lock --locked --offline

publish: clean
	uv build
	uv publish

isort:
	uv run ruff check --select I $(package) tests --fix

isort-check:
	uv run ruff check --select I $(package) tests	

ruff:
	uv run ruff check

fix: format isort
	uv run ruff check --fix

.ONESHELL:
pyrightconfig:
	jq \
      --null-input \
      --arg venv "$$(basename $$(uv env info -p))" \
      --arg venvPath "$$(dirname $$(uv env info -p))" \
      '{ "venv": $$venv, "venvPath": $$venvPath }' \
      > pyrightconfig.json

rename:
	ack antbed -l | xargs -i{} sed -r -i "s/antbed/antbed/g" {}
	ack Antbed -i -l | xargs -i{} sed -r -i "s/Antbed/Antbed/g" {}
	ack ANTBED -i -l | xargs -i{} sed -r -i "s/ANTBED/ANTBED/g" {}

run-worker:
	uv run bin/antbed  looper --namespace $(NAMESPACE)  --host 127.0.0.1:7233 --config=localconfig.yaml

run-server:
	./bin/antbed server --config localconfig.yaml

temporal-init-namespace:
	temporal operator namespace  create -n $(NAMESPACE) --retention 72h0m0s --email devops@conny.legal --description "antbed stg namespace"

ipython:
	uv run ipython

temporal-schedule:
	uv run bin/antbed scheduler --namespace $(NAMESPACE)  --host 127.0.0.1:7233  --config=localconfig.yaml -s scheduly.yaml


docker-push-local: docker-build
	docker push img.conny.dev/oss/antbed:latest

docker-build-local:
	docker build --network=host -t img.conny.dev/oss/antbed:latest .

docker-push:
	docker buildx build --push -t img.conny.dev/conny/antbed:latest .

upgrade-dep:
	uv sync --upgrade
	uv lock -U --resolution=highest
