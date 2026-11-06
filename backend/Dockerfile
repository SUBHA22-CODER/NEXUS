# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.14-slim
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY demo_data /srv/demo_data
RUN useradd --create-home nexus
USER nexus
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
