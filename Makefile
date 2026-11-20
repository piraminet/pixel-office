# Pixel Startup — build & run (visual environment: Pixel Office)
IMAGE   := pixel-startup
# Legacy image tag `pixel-office` may still exist locally from earlier builds; it is
# untouched (re-tag or `make clean` to retire it after Python cutover).
PORT    ?= 19000
ENVFILE := $(wildcard .env)
VERSION := $(shell node -p "require('./package.json').version")

.DEFAULT_GOAL := help
.PHONY: help install test build run stop logs clean tag

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

install: ## Install npm dependencies
	npm install

test: ## Run integration/presence self-checks
	npm test

build: ## Build the Docker image
	docker build -t $(IMAGE):latest .

run: ## Run the container (PORT from host side, data/ mounted, .env if present)
	docker run -d --rm --name $(IMAGE) \
	  -p $(PORT):19000 \
	  $(if $(ENVFILE),--env-file .env) \
	  -v $(CURDIR)/data:/app/data \
	  $(IMAGE):latest

stop: ## Stop the container
	-docker stop $(IMAGE)

logs: ## Tail container logs
	docker logs -f $(IMAGE)

tag: ## Tag the current commit as annotated v$(VERSION) (SemVer, from package.json) and push the tag
	git tag -a v$(VERSION) -m "v$(VERSION)"
	git push origin v$(VERSION)

clean: ## Stop the container and remove the image
	-docker stop $(IMAGE)
	-docker rmi $(IMAGE):latest
