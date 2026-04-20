# 🌿 EcoFlow — Smart Green Commute AI

> **MyAI Future Hackathon 2026 — Track 4: Green Horizon (Smart Cities & Mobility)**
> Team: **Can Win Just Enough** | Organised by GDG On Campus UTM

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Cloud%20Run-4285F4?style=for-the-badge&logo=google-cloud)](https://ecoflow-ai-196537430669.asia-southeast1.run.app)
[![Track](https://img.shields.io/badge/Track-Green%20Horizon-22C55E?style=for-the-badge)]()
[![Built with](https://img.shields.io/badge/Built%20with-Google%20AI-EA4335?style=for-the-badge&logo=google)]()

---

## 🚨 Problem Statement

Urban centres in Malaysia — particularly along the **Johor-Singapore Innovation Corridor** — face severe mobility congestion. The average KL commuter spends **150+ hours per year** stuck in traffic, generating unnecessary carbon emissions that push Malaysia further from its **Net Zero 2050** target.

There is no single intelligent tool that helps everyday Malaysians compare transport modes by **time, cost (RM), and carbon footprint simultaneously** — and then takes autonomous action to plan, match carpools, and ground recommendations in official national policy.

---

## 💡 Solution: EcoFlow

EcoFlow is an **Agentic AI green mobility assistant** that autonomously:

1. **Plans** the most eco-friendly commute route (MRT, Bus, Carpool, Cycling, Walking, Grab, Park & Ride)
2. **Calculates** real Malaysian costs (RM), CO₂ emissions (kg), and congestion levels
3. **Matches** users with carpool partners on similar routes
4. **Grounds** every recommendation in Malaysia's official transport policy via RAG (NETR, RapidKL data)
5. **Tracks** personal and community carbon savings over time

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     index.html (Frontend)                    │
│         Firebase Auth · Leaflet Map · Real-time UI          │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTPS
┌───────────────────▼─────────────────────────────────────────┐
│              FastAPI Backend (Google Cloud Run)              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         EcoFlow Agentic Layer (agent.py)             │   │
│  │   Firebase Genkit @flow  ←→  Gemini Function-calling │   │
│  │     ├── plan_commute_tool                           │   │
│  │     ├── find_carpool_tool                           │   │
│  │     ├── search_policy_tool  ←── Vertex AI Search    │   │
│  │     └── get_user_impact_tool                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ Gemini 2.5   │  │ Vertex AI Search │  │   Firebase   │  │
│  │ Flash (Brain)│  │  RAG Datastore   │  │  Firestore   │  │
│  └──────────────┘  └─────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Google AI Ecosystem Stack (Technical Mandate)

| Requirement | Implementation | Status |
|---|---|---|
| **1. Intelligence (Brain)** | Gemini 2.5 Flash via `google-generativeai` | ✅ |
| **2. Orchestrator** | Firebase Genkit `@ai.flow()` + `@ai.tool()` in `agent.py` | ✅ |
| **2b. Agent Builder** | Vertex AI Agent Builder — EcoFlow Agent with datastore tool | ✅ |
| **3. Deployment Lifecycle** | Deployed on Google Cloud Run (serverless container deployment)| ✅ |
| **4. Context (RAG)** | Vertex AI Search — `ecoflow_1776621221780` datastore (NETR + transport policy) | ✅ |
| **Mandatory** | Google AI Studio used for model testing and prompt iteration | ✅ |

---

## 🚀 Features

### 🗺️ Smart Route Planning
- Input: origin + destination on interactive Leaflet map
- Output: All transport modes ranked by personalised Eco Score (0–100)
- Real Malaysian data: RapidKL fares, Grab surge pricing, petrol costs (RM 2.05/L)
- KL traffic patterns: morning rush (7–9am), evening peak (5–7pm)

### 🤖 Agentic AI Chat (Firebase Genkit + Vertex AI)
- Autonomous multi-step reasoning: intent → tool selection → execution → grounded response
- Supports up to 4 chained tool calls per query
- Integrated with Gemini function-calling for dynamic tool orchestration
- Grounded in Malaysia’s NETR policy via Vertex AI Search (RAG datastore)
- Graceful fallback to direct Gemini responses when Genkit is unavailable

### 🤝 Carpool Matching
- Register your daily route; get matched with users on similar paths
- Real-time pool from Firestore, filtered by detour distance

### 📊 Impact Tracking
- Personal CO₂ saved, RM saved, trees equivalent
- Community leaderboard
- Yearly projection based on commute habits
- Achievement badges (First Trip → EcoHero)

### 🌤️ Live Conditions
- Weather via Open-Meteo API
- Air quality index
- Real-time congestion factor

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS, Leaflet.js |
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI Brain | Google Gemini 2.5 Flash (`google-generativeai`) |
| AI Orchestration | Firebase Genkit (`genkit`, `genkit-google-ai`) |
| RAG / Knowledge | Vertex AI Search (`google-cloud-discoveryengine`) |
| Auth & Database | Firebase Auth + Firestore (`firebase-admin`) |
| Deployment | Google Cloud Run (asia-southeast1) |
| Routing | OSRM (Open Source Routing Machine) |
| Maps | Leaflet.js + OpenStreetMap |

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.11+
- A Google Cloud project with Vertex AI Search enabled
- Firebase project with Auth + Firestore
- Gemini API key from Google AI Studio

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/ecoflow-ai.git
cd ecoflow-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
FIREBASE_KEY_PATH=firebase-key.json
GCP_PROJECT_ID=my-future-ai-493816
GCP_LOCATION=global
GCP_DATASTORE_ID=ecoflow_1776621221780
MAPBOX_TOKEN=your_mapbox_token_here   # optional
```

### 4. Add Firebase service account key
Download your Firebase Admin SDK key and save as `firebase-key.json` in the root directory.

### 5. Run the backend
```bash
uvicorn main:app --reload --port 8080
```

### 6. Open the frontend
Visit `http://localhost:8080` in your browser.

---

## 🌐 Live Deployment

**Cloud Run URL:** https://ecoflow-ai-196537430669.asia-southeast1.run.app

## 🔌 API Endpoints (Production – Cloud Run)
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main app (index.html) |
| `/health` | GET | Health check |
| `/api/v1/full-analysis` | POST | AI route recommendation |
| `/api/v1/agent` | POST | Agentic AI chat (Genkit + Gemini tools) |
| `/api/v1/ai-chat` | POST | RAG-grounded chat (Vertex AI Search) |
| `/api/v1/smart-routing` | POST | Transport options |
| `/api/v1/save-trip` | POST | Save completed trip |
| `/api/v1/impact/{user_id}` | GET | Personal carbon impact |
| `/api/v1/community-impact` | GET | Global stats |
| `/api/v1/leaderboard` | GET | Top eco-commuters |
| `/api/v1/carpool-match` | POST | Find carpool partners |
| `/docs` | GET | Interactive API docs (Swagger) |

---

## 🤖 AI Disclosure

This project used the following AI coding tools during development:
- **Google Gemini** (via AI Studio) — for code generation assistance and prompt engineering
- **Firebase Genkit** — as the agentic orchestration framework

All AI-generated code has been reviewed, tested, and understood by the team. Every part of the codebase can be explained and defended by team members during judging.

---

## 🌱 Impact & Malaysian Context

EcoFlow directly addresses **Track 4: Green Horizon** by:

- Helping Malaysians make data-driven commute decisions grounded in real RM costs
- Supporting Malaysia's **Net Zero 2050** target through behavioural carbon tracking
- Promoting MRT/LRT adoption along the **Johor-Singapore Innovation Corridor**
- Reducing per-capita carbon footprint through intelligent carpool matching
- Grounding all recommendations in Malaysia's **National Energy Transition Roadmap (NETR)**

---

## 👥 Team — Can Win Just Enough

Built with 💚 for the MyAI Future Hackathon 2026
Organised by Google Developer Groups On Campus UTM

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
