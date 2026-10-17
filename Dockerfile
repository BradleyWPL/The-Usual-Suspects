FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY . .
RUN mkdir -p data/generated data/analysis data/state \
    && useradd --create-home --uid 10001 incidentlens \
    && chown -R incidentlens:incidentlens /app
USER incidentlens
EXPOSE 8000
CMD ["sh", "-c", "python data/generate.py --profile quick && python pipelines/analyze.py && python data/load_postgres.py && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"]
