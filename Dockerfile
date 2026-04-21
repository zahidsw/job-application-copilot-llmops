FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8080 8081 8090

CMD ["python", "-m", "uvicorn", "job_app_ops.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
