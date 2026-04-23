# LetsEat Backend

FastAPI backend for the LetsEat group restaurant voting app.

## Stack
- **FastAPI** — API framework
- **Supabase** — Postgres database + auth
- **Yelp Fusion API** — Restaurant data
- **Railway** — Hosting (free tier)

---

## Local Setup

### 1. Clone and create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up Supabase
1. Create a free project at https://supabase.com
2. Go to **SQL Editor** and paste + run the contents of `schema.sql`
3. Go to **Project Settings > API** and copy:
   - Project URL
   - `anon` public key
   - `service_role` secret key

### 3. Get a Yelp API key
1. Create an app at https://www.yelp.com/developers
2. Copy your **API Key** from the app dashboard

### 4. Configure environment
```bash
cp .env.example .env
# Fill in all values in .env
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Run the server
```bash
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Create account |
| POST | `/auth/login` | Login, get JWT |
| GET | `/auth/me` | Get your profile |
| PATCH | `/auth/me` | Update name / preferences |
| POST | `/sessions` | Create a session |
| POST | `/sessions/join` | Join via code |
| GET | `/sessions/{id}` | Get session info |
| POST | `/sessions/{id}/start` | Host starts swiping |
| GET | `/sessions/{id}/restaurants` | Get restaurant deck |
| POST | `/votes` | Submit a swipe |
| POST | `/votes/{id}/done` | Mark yourself done swiping |
| GET | `/votes/{id}/results` | Get ranked results |
| WS | `/ws/{session_id}?token=...` | Real-time updates |

---

## Deploy to Railway

1. Install Railway CLI: https://docs.railway.app/develop/cli
2. ```bash
   railway login
   railway init
   railway up
   ```
3. Set environment variables in the Railway dashboard (same keys as `.env`)
4. Railway auto-detects FastAPI and runs `uvicorn app.main:app --host 0.0.0.0`

---

## Project Structure

```
app/
├── main.py              # App entry point, middleware, router registration
├── core/
│   ├── config.py        # Environment variable loading
│   ├── security.py      # JWT creation/verification, password hashing
│   └── database.py      # Supabase client
├── routers/
│   ├── auth.py          # Signup, login, profile
│   ├── sessions.py      # Create/join/start sessions
│   ├── votes.py         # Submit votes, get results
│   └── websocket.py     # Real-time session events
├── services/
│   ├── yelp.py          # Yelp API + group preference merging
│   └── session.py       # Session creation/management logic
└── schemas/
    └── schemas.py       # Pydantic request/response models
```
