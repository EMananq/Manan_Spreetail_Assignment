# FairSplit — Shared Expenses Manager

A full-stack shared expenses app for flatmates, built with Django REST Framework + React/Vite.

## Live Demo
> Start the servers locally (see below) — no public deployment configured yet.

---

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13 · Django 5 · Django REST Framework |
| Auth | Custom JWT (PyJWT) — stateless, 30-day tokens |
| Database | PostgreSQL 14+ |
| Frontend | React 19 · Vite 8 · Axios · React Router v7 |
| Currency | Static rate: 1 USD = ₹95 (documented in DECISIONS.md) |

---

## Prerequisites
- Python ≥ 3.11
- Node.js ≥ 18
- PostgreSQL running locally

---

## Setup

### 1. Clone & enter repo
```bash
git clone <repo-url>
cd Spreetail
```

### 2. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Create the database
psql -U postgres -c "CREATE DATABASE fairsplit;"

# Apply migrations
python manage.py migrate

# (Optional) create superuser
python manage.py createsuperuser
```

**Environment variables** (create `backend/.env`):
```
DJANGO_SECRET_KEY=any-random-string
DB_NAME=fairsplit
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
JWT_SECRET=any-random-string
DEBUG=True
```

Start the backend:
```bash
python manage.py runserver
# API available at http://localhost:8000/api/
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173/
```

### 4. Seed demo accounts (optional)
Register 6 accounts through the app's Register page or via the API:
| Name  | Email              | Password    |
|-------|--------------------|-------------|
| Aisha | aisha@flat.app     | password123 |
| Rohan | rohan@flat.app     | password123 |
| Priya | priya@flat.app     | password123 |
| Meera | meera@flat.app     | password123 |
| Dev   | dev@flat.app       | password123 |
| Sam   | sam@flat.app       | password123 |

The Login page shows these demo credentials and auto-fills on click.

### 5. Import the CSV
1. Log in → open the group → click **Import** tab
2. Click the upload area → select `expenses_export.csv`
3. Review the anomaly preview
4. Click **Confirm & Import**

---

## Running the balance engine standalone (no DB required)
```bash
cd backend
python rohan_ledger.py
```
Prints Rohan's full row-by-row ledger, all group balances, simplified debts, and assignment audit.

---

## Running the test suite
```bash
cd backend
python test_engine.py   # requires DB + Django setup
```

---

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register/` | Register |
| POST | `/api/auth/login/` | Login → JWT token |
| GET | `/api/auth/me/` | Current user |
| GET | `/api/auth/users/` | All users (for member add) |
| GET/POST | `/api/groups/` | List / create groups |
| GET | `/api/groups/<id>/` | Group detail |
| GET/POST | `/api/groups/<id>/members/` | List / add members |
| PUT | `/api/groups/<id>/members/<id>/` | Set departure date |
| GET/POST | `/api/groups/<id>/expenses/` | List / create expenses |
| GET/POST | `/api/groups/<id>/settlements/` | List / record payments |
| GET | `/api/groups/<id>/balances/` | Net balances + drill-down |
| POST | `/api/groups/<id>/import/` | Import CSV (preview or confirm) |
| GET | `/api/groups/<id>/import-reports/` | Past import reports |
| PUT | `/api/groups/<id>/import-reports/<id>/anomalies/<id>/` | Approve/reject anomaly |

---

## AI Tool Used
**Antigravity (Google DeepMind)** — an AI coding assistant embedded in the IDE.

Key contributions:
- Scaffolding the Django models, serializers, and view patterns
- Suggesting the greedy debt-simplification algorithm
- Drafting the CSS design system

See `AI_USAGE.md` for the full AI usage log and three cases where the AI was wrong.
