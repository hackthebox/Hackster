ARG PYTHON_VERSION=3.13

FROM astral/uv:python${PYTHON_VERSION}-bookworm-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
ENV APP_PATH="/opt/hackster"
ENV VENV_PATH="$APP_PATH/.venv"
ENV PATH="$VENV_PATH/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    build-essential \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_PATH
COPY ./uv.lock ./pyproject.toml ./
RUN uv sync --frozen --no-dev --no-install-project

FROM astral/uv:python${PYTHON_VERSION}-bookworm-slim AS runtime

ARG VERSION=unknown

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
ENV APP_PATH="/opt/hackster"
ENV VENV_PATH="$APP_PATH/.venv"
ENV PATH="$VENV_PATH/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    mariadb-client \
    libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_PATH

COPY --from=builder $VENV_PATH $VENV_PATH

COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY src ./src
COPY resources ./resources
COPY startup.sh ./startup.sh
COPY pyproject.toml uv.lock ./
RUN chmod +x startup.sh

ENV PYTHONPATH=$APP_PATH
ENV VERSION=$VERSION

EXPOSE 1337
# Run the start script, it will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Uvicorn
ENTRYPOINT ["/opt/hackster/startup.sh"]
