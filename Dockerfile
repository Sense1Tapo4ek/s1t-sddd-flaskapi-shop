FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

RUN mkdir -p media/products

ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "python data/seed.py && gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 'root.entrypoints.api:create_app()'"]
