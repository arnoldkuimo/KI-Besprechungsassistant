FROM node:24-alpine AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/dist
RUN useradd --create-home appuser && mkdir -p /app/data/uploads && chown -R appuser:appuser /app
USER appuser
EXPOSE 8030
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8030"]
