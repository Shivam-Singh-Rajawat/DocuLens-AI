FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY doculens/ ./doculens/
COPY frontend/ ./frontend/
RUN mkdir -p /app/data && useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app/data
USER appuser
EXPOSE 8000
CMD ["uvicorn","doculens.api:app","--host","0.0.0.0","--port","8000"]
