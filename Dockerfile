FROM ghcr.io/hackthebox/hackster:base as builder-base
# `production` image used for runtime
FROM builder-base as production

RUN apt-get update && \
    apt-get install -y mariadb-client libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder-base $APP_PATH $APP_PATH

WORKDIR $APP_PATH

COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY src ./src
COPY resources ./resources
COPY startup.sh ./startup.sh
COPY pyproject.toml ./pyproject.toml
RUN chmod +x startup.sh

ENV PYTHONPATH=$APP_PATH

EXPOSE 1337
# Run the start script, it will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Uvicorn
ENTRYPOINT ["/opt/hackster/startup.sh"]
