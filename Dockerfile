FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py run.py ./
COPY app/ ./app/
COPY consumer/ ./consumer/

EXPOSE 5000 9091

CMD ["python", "run.py"]
