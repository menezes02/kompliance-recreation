FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 kompliance \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin kompliance

WORKDIR /app

COPY --chown=10001:10001 local-app /app/local-app
COPY --chown=10001:10001 examples /app/examples
COPY --chown=10001:10001 production-data /app/production-data

RUN mkdir -p /app/local-app/data \
    && chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=3).read()"]

WORKDIR /app/local-app

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8090"]
