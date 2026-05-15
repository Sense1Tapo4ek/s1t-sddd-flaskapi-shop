FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        default-mysql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

RUN mkdir -p media/products data/dumps

ENV PYTHONPATH=/app/src

# Apply migrations, seed defaults, then serve.
CMD ["sh", "-c", "python scripts/db_apply.py && python data/seed.py && gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 'root.entrypoints.api:create_app()'"]
