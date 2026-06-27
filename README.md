# Simple Tech — Backend API

[![Live API](https://img.shields.io/badge/API-live-success?style=flat-square)](https://simple-tech-api.onrender.com/health)
[![Frontend](https://img.shields.io/badge/demo-GitHub%20Pages-blue?style=flat-square)](https://matheusmaggiorini.github.io/simple-tech-app/)

FastAPI backend for **Simple Tech**: JWT auth, per-user financial data storage, ML cash-flow forecasting, Monte Carlo simulations, and executive report generation.

**API base:** https://simple-tech-api.onrender.com  
**Interactive docs:** https://simple-tech-api.onrender.com/docs  
**Frontend:** https://github.com/matheusmaggiorini/simple-tech-app

---

## Architecture

```
Client (React / GitHub Pages)
        │  Bearer JWT
        ▼
FastAPI (Render)
        ├── SQLite        → users
        ├── Parquet       → processed cash-flow per user
        ├── scikit-learn / XGBoost → forecasts
        └── Monte Carlo   → scenario simulation
```

---

## Features

| Area | Endpoints | Description |
|------|-----------|-------------|
| **Auth** | `/api/auth/register`, `/login`, `/me` | JWT + bcrypt |
| **Data** | `/api/data/upload_excel_bundle`, `/statistics`, `/view_processed` | CSV/XLSX upload, KPIs |
| **Charts** | `/api/data/balance_evolution_simple`, `/monthly_summary`, `/yearly_monthly_data` | Dashboard series |
| **Forecast** | `POST /api/predictions/cashflow` | Train & predict N days |
| **Simulation** | `/api/simulations/scenarios`, `/scenario-simulation` | Monte Carlo, events, loans |
| **Reports** | `POST /api/reports/generate` | Markdown reports (heuristic or Gemini) |

All data routes require `Authorization: Bearer <token>`.

---

## Quick start (local)

```powershell
git clone https://github.com/matheusmaggiorini/simple-tech-api.git
cd simple-tech-api/Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
powershell -ExecutionPolicy Bypass -File run-api.ps1
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

### Environment (`Backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes (prod) | Token signing secret |
| `CORS_ORIGINS` | Yes (prod) | e.g. `https://matheusmaggiorini.github.io` |
| `GEMINI_API_KEY` | No | Enables AI-enhanced reports |

---

## Deploy (Render — free tier)

| Setting | Value |
|---------|--------|
| Root Directory | `Backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

Set `JWT_SECRET_KEY` and `CORS_ORIGINS` in Render environment variables.

**Limitations (free tier):** ephemeral filesystem — SQLite and Parquet may reset on redeploy or long spin-down. Mention this in demos.

---

## CSV format

```csv
data,descricao,entrada,saida,id_cliente
2025-01-09,Product sale,1000.00,0.00,C01
2025-01-02,Supplier,0.00,500.00,S01
```

Filenames containing `fluxo_caixa` or `fluxo` are treated as combined inflow/outflow files.

---

## Tests

```powershell
cd Backend
pytest
```

CI runs on push to `main` (GitHub Actions).

---

## Stack

Python 3.11+ · FastAPI · pandas · scikit-learn · XGBoost · SQLite · Parquet · JWT · bcrypt · Docker

Optional: Google Gemini API for rich AI reports.

---

## Team & role

**Simple Tech** — group project.  
**Matheus Maggiorini** — CTO: backend architecture, auth, ML endpoints, Render deployment, CI.

---

## License

Team project. Contact the Simple Tech team for usage rights.
