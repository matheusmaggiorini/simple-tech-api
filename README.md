# Simple Tech

Cloud-based financial management platform for small businesses. Upload cash flow data, get ML-powered forecasts, run Monte Carlo scenario simulations, and generate AI reports.

Built by the Simple Tech team.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, shadcn/ui, Tailwind, Recharts |
| Backend | FastAPI, scikit-learn, XGBoost, Gemini API |
| Auth | JWT + bcrypt |
| Storage | SQLite (users) + Parquet per user (financial data) |

## Repositories

- **Frontend:** `simple-tech` (this repo)
- **Backend:** `Simple.Tech` → `Backend/` folder

## Quick start (local)

### 1. Backend

```powershell
cd Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```powershell
cd simple-tech
npm install
copy .env.example .env
npm run dev
```

App: http://localhost:8080

### 3. First use

1. Open http://localhost:8080
2. Create an account (`/auth`)
3. Upload Excel/CSV files (inflow and/or outflow)
4. Explore dashboard, forecasts, and simulations

## Environment variables

### Backend (`Backend/.env`)

| Variable | Description |
|----------|-------------|
| `JWT_SECRET_KEY` | Secret for signing tokens (change in production) |
| `GEMINI_API_KEY` | Optional — enables AI-generated reports |
| `CORS_ORIGINS` | Comma-separated frontend URLs |

### Frontend (`.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL (default: `http://localhost:8000`) |

## Features

- **Upload** — Excel/CSV with Brazilian currency formats
- **Dashboard** — KPIs, balance evolution, monthly summary
- **Forecast** — ML cash flow prediction (XGBoost)
- **Simulation** — Monte Carlo scenarios, business events, loan impact
- **Reports** — Markdown reports (Gemini when configured)

## CSV format

```csv
data,descricao,entrada,saida
2024-01-01,Product sale,1000.00,0.00
2024-01-02,Supplier payment,0.00,500.00
```

## Deploy (free tier)

- **Backend:** Render — set start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Frontend:** Vercel — set `VITE_API_BASE_URL` to your Render URL

Cold starts on free tier are expected; mention this in demos.

## License

Private team project. Contact the Simple Tech team for usage rights.
