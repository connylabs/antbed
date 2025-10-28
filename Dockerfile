FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.7.19 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

ENV workdir=/app
RUN mkdir -p $workdir
WORKDIR $workdir
RUN apt-get update -y
RUN apt-get install -y openssl ca-certificates
RUN apt-get install -y libffi-dev build-essential libssl-dev git rustc cargo libpq-dev gcc curl
RUN mkdir -p bin; curl -Lo bin/goose https://github.com/pressly/goose/releases/download/v3.24.1/goose_linux_x86_64; \
     chmod +x bin/goose;
RUN pip install pip -U
RUN uv venv
COPY uv.lock $workdir
COPY pyproject.toml $workdir
RUN uv sync --locked --no-install-project --no-dev --compile-bytecode

RUN rm -rf /root/.cargo
# COPY code later in the layers (after dependencies are installed)
# It builds the containers 2x faster on code change
COPY . $workdir
RUN uv sync --locked --no-dev --compile-bytecode  --no-editable
# Most of dependencies are already installed, it only install the app


FROM python:3.12-slim
ENV workdir=/app
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_NO_SYNC=1
RUN apt-get update && apt-get install -y git curl libpq-dev gcc
WORKDIR $workdir
RUN mkdir -p /usr/share/fonts/truetype/dejavu

COPY --from=ghcr.io/astral-sh/uv:0.7.19 /uv /uvx /bin/
COPY --from=build /usr/bin/make /usr/bin/make
COPY --from=build /app /app
# RUN uv sync --locked --no-dev --compile-bytecode  --no-editable
