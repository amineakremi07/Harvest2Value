# 🌾 Harvest2Value

AI-powered agricultural decision-support and supply chain optimization system for smallholder farmers. Built for GOMYCODE Hackathon 2026.

---

## 🏛️ Architecture & API Endpoints

```
                      +-----------------------------+
                      |   Next.js 14 Frontend (App) |
                      +--------------+--------------+
                                     |
                       HTTP / JSON   v  (:8000)
                      +-----------------------------+
                      |       FastAPI Backend       |
                      +--------------+--------------+
                                     |
     +-------------------------------+-------------------------------+
     |                               |                               |
     v                               v                               v
[POST /api/v1/optimize]     [POST /api/v1/scenario]      [POST /api/v1/explain]
     |                               |                               |
     v                               v                               v
+------------------+        +------------------+        +------------------+
| PuLP MILP Solver |        | NVIDIA NIM LLM   |        | NVIDIA NIM XAI   |
| (Supply/Storage/ |        | (Llama-3.1-70B   |        | (Plain-language  |
|  Demand/Logistics|        |  NL -> Constraint|        |  recommendations |
+------------------+        +--------+---------+        +------------------+
                                     |
                                     v
                            +------------------+
                            | PuLP Re-solve    |
                            +------------------+
```

---

## 🚀 Quickstart

### Prerequisites
- Docker & Docker Compose **OR** Python 3.11+ & Node.js 20+
- NVIDIA NIM API Key (`NIM_API_KEY`)

### Option A: Docker (Recommended)
```bash
# 1. Set environment variable
export NIM_API_KEY="your_nvidia_nim_key"

# 2. Build and launch all services
docker-compose up --build
```
- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B: Local Execution

```bash
# Backend (Terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export NIM_API_KEY="your_nvidia_nim_key"
uvicorn app.main:app --reload --port 8000

# Frontend (Terminal 2)
cd frontend
npm install
npm run dev -- -p 5173
```

---

## 📊 Datasets (Tunisia Agriculture)

All fixtures in `data/` validate against `data/schema.json` and represent realistic Tunisian agricultural hubs:

- **`tunisia_olives.json`** — *Sfax* | 12,000 kg olives | Oil mills & Radès export port trade-offs.
- **`tunisia_dates.json`** — *Tozeur* | 18,000 kg Deglet Nour dates | High storage & export optimization.
- **`tunisia_citrus.json`** — *Cap Bon* | 16,000 kg Maltese oranges | Fresh wholesale vs. juice transformation.
- **`tunisia_tomatoes.json`** — *Kairouan* | 14,000 kg perishable tomatoes | Industrial paste cannery vs. wholesale markets.
- **`tunisia_wheat.json`** — *Béja* | 30,000 kg durum wheat (*Blé Dur*) | Office des Céréales silo vs. industrial mills.

---

## 👥 Team & Responsibilities

| Role | Perimeter | Key Deliverables |
| :--- | :--- | :--- |
| **Member 1 (Lead / Backend)** | `backend/` | FastAPI REST API, PuLP MILP solver, Pydantic models |
| **Member 2 (Frontend Dashboard)** | `frontend/` | Next.js 14 layout, HarvestInput, AllocationTable, RiskGauge |
| **Member 3 (What-If & XAI)** | `frontend/`, `backend/` | WhatIfChat, ExplainView, NIM Llama-3.1-70B constraint parsing |
| **Member 4 (Data, Viz & DevOps)** | `data/`, `frontend/`, DevOps | Datasets, SankeyChart, FlowChart, Docker Compose, README |
