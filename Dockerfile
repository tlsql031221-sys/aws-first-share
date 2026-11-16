FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
EXPOSE 5000
CMD ["sh", "-c", "python -c 'from app import init_db; init_db()' && gunicorn --workers 2 --bind 0.0.0.0:5000 app:app"]
