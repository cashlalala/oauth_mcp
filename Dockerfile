FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Listen on all interfaces so the port is reachable from outside the container.
    HOST=0.0.0.0 \
    PORT=8000 \
    # FastMCP keeps OAuth client registrations and encrypted tokens here.
    FASTMCP_HOME=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data
USER 10001

VOLUME /data
EXPOSE 8000

CMD ["python", "server.py"]
