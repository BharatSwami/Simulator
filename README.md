## Economic World Simulator – V1

This project is a minimal full-stack prototype of an economic/financial world simulator with four interconnected time series:

- Gold price
- Interest rate
- Dollar index
- Wheat price

Gold and the interest rate are treated as \"drivers\", while dollar and wheat depend on them via a simple Bayesian-style model.

### Tech stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, NumPy, SQLModel/SQLAlchemy, PostgreSQL
- **Realtime**: FastAPI WebSocket
- **Frontend**: React, TypeScript, Vite, Recharts
- **Database**: PostgreSQL (for simulation runs and history)

### Getting started (high level)

1. **Backend**
   - Create and activate a virtual environment.
   - Install dependencies:

     ```bash
     cd backend
     pip install -r requirements.txt
     uvicorn app.main:app --reload
     ```

2. **Frontend**
   - Install Node.js (LTS recommended).
   - Install dependencies and run dev server:

     ```bash
     cd frontend
     npm install
     npm run dev
     ```

3. Open the frontend dev URL (usually `http://localhost:5173`) and verify the four charts update in real time from the backend simulation.

