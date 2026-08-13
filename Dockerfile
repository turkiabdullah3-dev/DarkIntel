FROM node:22-alpine AS frontend
WORKDIR /build/dashboard/frontend
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./
RUN npm ci
COPY dashboard/frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
LABEL org.opencontainers.image.title="DarkIntel" \
      org.opencontainers.image.description="CTI & OSINT Investigation Platform" \
      org.opencontainers.image.authors="Turki Almuraykhi"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DARKINTEL_CASES_DIR=/data/cases
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 darkintel
COPY darkintel/ darkintel/
COPY dashboard/ dashboard/
COPY main.py ./
COPY --from=frontend /build/dashboard/frontend/dist dashboard/frontend/dist
RUN mkdir -p /data/cases && chown -R darkintel:darkintel /data
USER darkintel
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"
CMD ["python", "main.py", "dashboard", "--host", "0.0.0.0", "--port", "8000"]
