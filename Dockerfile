FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config ./config
COPY sentinel ./sentinel
COPY data/raw ./data/raw
COPY tests ./tests
EXPOSE 8000
# Hosting (Render etc.) sets PORT; docker-compose overrides this command.
CMD ["sh", "-c", "uvicorn sentinel.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
