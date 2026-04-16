# EcoFlow AI — Backend v2.0
**Smart Commute Decision System | MyAI Future Hackathon 2026**
Track 4: Green Horizon — Smart Cities & Mobility | GDG UTM

---

## Quick Setup (5 minutes)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Fix the AI connection
```bash
# First, test your Gemini key
python test_gemini.py
```
If it fails, the script will tell you exactly what to fix.

### 3. Set environment variables
```bash
cp .env.example .env
# Edit .env and add your keys
```

Your `.env` file:
```
GEMINI_API_KEY=AIzaSy...          ← from https://aistudio.google.com/app/apikey
FIREBASE_KEY_PATH=firebase-key.json
```

### 4. Run the server
```bash
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000/docs  (interactive API docs)

---

## API Endpoints

| Method | Endpoint | What it does |
|--------|----------|-------------|
| GET  | `/` | Health check + AI status |
| GET  | `/health` | Detailed system status |
| POST | `/api/v1/smart-routing` | Get ranked transport options |
| POST | `/api/v1/ai-insight` | Gemini AI recommendation |
| POST | `/api/v1/ai-chat` | Conversational trip assistant |
| POST | `/api/v1/save-trip` | Record a completed trip |
| GET  | `/api/v1/trip-history/{user_id}` | User's past trips |
| POST | `/api/v1/user-profile` | Save commute preferences |
| GET  | `/api/v1/user-profile/{user_id}` | Load preferences |
| GET  | `/api/v1/impact/{user_id}` | Personal carbon savings + badges |
| GET  | `/api/v1/community-impact` | All-users impact stats |
| GET  | `/api/v1/leaderboard` | Top eco-commuters |
| POST | `/api/v1/carpool-match` | Find nearby carpool partners |

---

## Key Fixes in v2.0

| Issue | Fix |
|-------|-----|
| Hardcoded API key | All secrets in `.env` |
| Wrong AI package (`google-genai`) | Changed to `google-generativeai` (stable) |
| Duplicate `@app.post` decorator | Removed |
| No error handling | Try/except on all external calls |
| Simulated traffic (true/false) | Real KL rush-hour patterns by hour |
| Inaccurate costs/carbon | Real Malaysian values (RM, CO₂/km) |
| No fallback if Gemini down | Smart rule-based fallback |
| Load all Firestore docs | `.limit()` + date filtering |

---

## Transport Data Sources
- CO₂ factors: MyCC Malaysia Carbon Calculator, PEMANDU
- Fuel cost: RM 2.05/L petrol, 12 km/L average
- MRT fares: Prasarana fare structure
- Grab: RideHailing Malaysia Q1 2026 averages
- Carbon sink: 21.77 kg CO₂/tree/year (IPCC standard)

# .env.example
VITE_MAPBOX_KEY=your_mapbox_public_key_here