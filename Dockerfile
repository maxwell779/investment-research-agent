# ── 1단계: React(Vite) 빌드 ──
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── 2단계: FastAPI 백엔드 + 정적(React) 서빙 ──
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY universe.json ./
COPY --from=frontend /fe/dist ./frontend/dist

# Hugging Face Spaces 기본 포트 = 7860 (GEMINI_API_KEY/GITHUB_TOKEN은 Space Secret으로 주입)
EXPOSE 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
