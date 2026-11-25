FROM python:3.12-alpine AS builder

WORKDIR /app

COPY requirements.txt .

# Install build dependencies, create venv, install requirements, then remove build deps
RUN python -m venv /venv \
    && . /venv/bin/activate \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && find /venv -name '__pycache__' -type d -exec rm -rf {} +

FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /venv /venv
COPY main.py .

CMD ["/venv/bin/python", "main.py"]
