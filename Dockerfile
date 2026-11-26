FROM node:22-alpine AS frontend
WORKDIR /ui
COPY frontend/ ./
RUN npm ci && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scouting/ scouting/
COPY --from=frontend /ui/dist dist
CMD ["uvicorn","scouting.api:app","--host","0.0.0.0","--port","8000"]
