FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependências primeiro, para aproveitar o cache de camadas
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY coletor ./coletor
COPY fontes ./fontes
COPY dbt ./dbt
RUN uv sync --frozen --no-dev

ARG VERSAO=local
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ELEITORADO_VERSAO=$VERSAO

ENTRYPOINT ["coletor"]
CMD ["pipeline"]
