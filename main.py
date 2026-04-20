"""
EcoFlow AI Backend v2.0
Smart Commute Decision System — MyAI Future Hackathon (Track 4: Green Horizon)
GDG UTM | Build with Google AI 2026
"""

import os
from google.cloud import discoveryengine_v1beta as discoveryengine
import google.generativeai as genai
import math
import time
import logging
from datetime import datetime
from typing import Optional, List

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================================
# Logging
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("ecoflow")

# ============================================================
# Load .env
# ============================================================
load_dotenv()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
FIREBASE_KEY     = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")

# --- GCP RAG / Vertex AI Search ---
# On Cloud Run we rely on the runtime service account (no key file needed).
# Locally, set GOOGLE_APPLICATION_CREDENTIALS in .env to point to your JSON key.
PROJECT_ID   = os.getenv("GCP_PROJECT_ID",   "my-future-ai-493816")
LOCATION     = os.getenv("GCP_LOCATION",     "global")
DATASTORE_ID = os.getenv("GCP_DATASTORE_ID", "ecoflow_1776621221780")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

# ============================================================
# Firebase Init
# ============================================================
if not firebase_admin._apps:
    try:
        # On Cloud Run, if no key file is present, fall back to default
        # credentials (the runtime service account).
        if os.path.exists(FIREBASE_KEY):
            cred = credentials.Certificate(FIREBASE_KEY)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        log.info("✅ Firebase connected")
    except Exception as e:
        log.error(f"❌ Firebase init failed: {e}")

db = firestore.client()

# ============================================================
# Gemini AI Init  ← FIXED: use google-generativeai (stable)
# ============================================================
gemini_model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",           # fast + free tier
            generation_config={"temperature": 0.7, "max_output_tokens": 300},
        )
        # Quick connectivity test
        test = gemini_model.generate_content("Say OK")
        log.info(f"✅ Gemini connected — test: {test.text.strip()[:20]}")
    except Exception as e:
        log.warning(f"⚠️  Gemini unavailable ({e}) — using smart fallback responses")
else:
    log.warning("⚠️  GEMINI_API_KEY not set in .env — AI features using fallback")

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="EcoFlow AI",
    description="Smart urban commute decisions — green, cheap, fast 🌿",
    version="2.0.0"
)
@app.get("/api/config")
async def get_config():
    return {"mapbox_token": MAPBOX_TOKEN}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content="", media_type="image/x-icon")

@app.middleware("http")
async def validate_user_header(request, call_next):
    # Skip security check for health status or index page
    if request.url.path in ["/", "/health", "/favicon.ico"]:
        return await call_next(request)
    
    # Check if 'X-User-ID' exists in the request headers
    # In a real production app, you would verify the Firebase JWT token here
    user_id = request.headers.get("X-User-ID")
    if not user_id and request.method == "POST":
        log.warning(f"🚫 Unauthenticated access attempt to {request.url.path}")
        # For now, we log it, but in production, you'd raise HTTPException(401)
        
    return await call_next(request)
# --- User Profile Data Model ---
class UserProfile(BaseModel):
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    # 偏好设置：默认各占 1/3
    prefer_fast: float = 0.33
    prefer_cheap: float = 0.33
    prefer_green: float = 0.34
    vehicle_type: str = "car"
    # 可选：保存工作地点以优化路线建议
    work_lat: Optional[float] = None
    work_lon: Optional[float] = None

@app.post("/api/v1/auth/sync")
async def sync_user(profile: UserProfile):
    """
    Synchronizes Firebase User UID with Firestore document.
    Ensures each user has a private record in the 'users' collection.
    """
    try:
        user_ref = db.collection("users").document(profile.user_id)
        doc = user_ref.get()

        if not doc.exists:
            user_data = profile.model_dump() 
            user_data["created_at"] = datetime.now()
            user_data["last_login"] = datetime.now()
            user_ref.set(user_data)
            log.info(f"✨ New user created: {profile.user_id}")
            return {"status": "created", "user_id": profile.user_id}
        else:
            user_ref.update({
                "last_login": datetime.now()
            })
            log.info(f"🔑 User synced: {profile.user_id}")
            return {"status": "synced", "user_id": profile.user_id}
            
    except Exception as e:
        log.error(f"❌ Sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error during sync")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Mount the Agentic AI layer (Gemini function-calling)
# Implements the "Chat → Action" Technical Mandate.
# ============================================================
from agent import agent_router
app.include_router(agent_router)

# ============================================================
# Malaysian Constants
# ============================================================

# CO2 emission kg per km per person
CO2 = {
    "drive":        0.171,   # avg petrol car Malaysia
    "carpool_2p":   0.0855,  # 2 sharing
    "carpool_3p":   0.057,   # 3 sharing
    "motorcycle":   0.103,
    "grab":         0.171,
    "bus":          0.089,   # per passenger
    "mrt_lrt":      0.041,   # per passenger
    "cycling":      0.0,
    "walking":      0.0,
}

# Rough cost references (RM)
RM = {
    "petrol_per_km":        0.17,   # ~RM 2.05/L, 12 km/L
    "parking_city":         5.00,   # avg city centre parking / trip
    "parking_park_ride":    1.00,
    "bus_flat":             2.00,   # RapidKL avg
    "mrt_base":             1.20,
    "mrt_per_km":           0.45,
    "mrt_cap":              7.50,   # KL Kelana Jaya Line max
    "grab_base":            2.00,
    "grab_per_km":          1.30,
    "grab_surge":           1.35,   # rush hour surge
    "motorcycle_per_km":    0.08,
}

# ============================================================
# Pydantic Models
# ============================================================

class SmartRoutingRequest(BaseModel):
    user_id: str
    start_lat: float = Field(..., ge=-90, le=90)
    start_lon: float = Field(..., ge=-180, le=180)
    end_lat:   float = Field(..., ge=-90, le=90)
    end_lon:   float = Field(..., ge=-180, le=180)
    departure_time:  Optional[str]  = None   # "HH:MM"
    vehicle_type:    Optional[str]  = "car"  # car | motorcycle | none
    num_passengers:  Optional[int]  = 1

class UserPreference(BaseModel):
    user_id:      str
    prefer_fast:  float = Field(default=0.33, ge=0, le=1)
    prefer_cheap: float = Field(default=0.33, ge=0, le=1)
    prefer_green: float = Field(default=0.34, ge=0, le=1)
    vehicle_type: Optional[str] = "car"
    home_lat:     Optional[float] = None
    home_lon:     Optional[float] = None
    work_lat:     Optional[float] = None
    work_lon:     Optional[float] = None

class SaveTripRequest(BaseModel):
    user_id:       str
    mode_chosen:   str
    route_name:    str
    time_mins:     float
    cost_rm:       float
    carbon_kg:     float
    distance_km:   float
    start_lat:     float
    start_lon:     float
    end_lat:       float
    end_lon:       float
    carbon_saved_vs_driving: float = 0.0

class CarpoolMatchRequest(BaseModel):
    user_id:        str
    start_lat:      float
    start_lon:      float
    end_lat:        float
    end_lon:        float
    departure_time: Optional[str]  = None
    max_detour_km:  float = 2.0

class AIInsightRequest(BaseModel):
    route_name:    str
    mode:          str
    time_mins:     float
    cost_rm:       float
    carbon_kg:     float
    distance_km:   float
    alternatives:  Optional[List[dict]] = None
    user_context:  Optional[str] = None

class ChatRequest(BaseModel):
    user_id:  str
    message:  str
    context:  Optional[dict] = None

# ============================================================
# Utility Helpers
# ============================================================

def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dLon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_traffic(departure_time: Optional[str]) -> tuple[float, str]:
    """Return (multiplier, congestion_label) based on KL traffic patterns."""
    try:
        hour = int((departure_time or datetime.now().strftime("%H:%M")).split(":")[0])
    except Exception:
        hour = datetime.now().hour

    if 7 <= hour <= 9:   return 1.65, "Very High"   # morning rush KL
    if 17 <= hour <= 19: return 1.75, "Very High"   # evening rush (worst)
    if 12 <= hour <= 13: return 1.20, "Medium"
    if 6  <= hour <= 7:  return 1.30, "High"
    if 9  <= hour <= 10: return 1.25, "High"
    if 20 <= hour or hour <= 5: return 0.85, "Very Low"
    return 1.0, "Low"


def get_osrm(start_lon, start_lat, end_lon, end_lat) -> tuple[float, float]:
    """Return (distance_km, duration_min). Falls back to haversine estimate."""
    try:
        url = (f"http://router.project-osrm.org/route/v1/driving/"
               f"{start_lon},{start_lat};{end_lon},{end_lat}?overview=false")
        r = requests.get(url, timeout=7)
        r.raise_for_status()
        rt = r.json()["routes"][0]
        return rt["distance"] / 1000, rt["duration"] / 60
    except Exception as e:
        log.warning(f"OSRM failed ({e}), using haversine fallback")
        d = haversine(start_lat, start_lon, end_lat, end_lon) * 1.3   # road factor
        return d, (d / 35) * 60   # assume 35 km/h avg


def mrt_cost(km: float) -> float:
    return min(RM["mrt_base"] + km * RM["mrt_per_km"], RM["mrt_cap"])


def grab_cost(km: float, rush: bool) -> float:
    surge = RM["grab_surge"] if rush else 1.0
    return round((RM["grab_base"] + km * RM["grab_per_km"]) * surge, 2)

def search_rag_knowledge(query: str) -> str:
    """去 Vertex AI Search (你上传的 PDF) 中寻找马来西亚交通政策背景"""
    try:
        client = discoveryengine.SearchServiceClient()
        serving_config = client.serving_config_path(
            project=PROJECT_ID, location=LOCATION,
            data_store=DATASTORE_ID, serving_config="default_config"
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=3,
            content_search_spec={"summary_spec": {"summary_result_count": 5}}
        )
        response = client.search(request)
        return response.summary.summary_text if response.summary else ""
    except Exception as e:
        log.warning(f"⚠️ RAG 检索失败: {e}")
        return ""

def call_gemini(prompt: str, fallback: str = "") -> str:
    """Call Gemini with a safe fallback."""
    if gemini_model:
        try:
            resp = gemini_model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            log.warning(f"Gemini call failed: {e}")
    return fallback or "🌱 Great choice making an eco-friendly commute!"

def smart_fallback(mode: str, context: str = "") -> str:
    """Professional rule-based fallback when Gemini is unavailable."""
    m = mode.lower()
    if "walk" in m:        return "Zero emissions, zero cost — perfect for short trips and optimal for health."
    if "cycl" in m:        return "Cycling minimizes costs and produces zero carbon emissions."
    if "mrt" in m or "lrt" in m: return "Rail transit offers high reliability and bypasses road congestion entirely."
    if "bus" in m:         return "Public bus networks provide the most cost-effective urban mobility."
    if "carpool" in m:     return "Carpooling significantly reduces per-capita carbon footprint and travel expenses."
    if "park" in m:        return "Park & Ride is a strategic hybrid approach to avoid city center parking fees."
    if "grab" in m:        return "E-hailing offers point-to-point convenience without parking friction."
    if "motor" in m:       return "Motorcycles provide the highest time-efficiency during peak congestion."
    
    return "Every eco-friendly transit choice contributes to Malaysia's Net Zero 2050 targets."


def calc_badges(stats: dict) -> List[str]:
    """Clean, professional badges without emojis."""
    badges = []
    trips = stats.get("total_trips", 0)
    saved = stats.get("total_carbon_saved", 0)
    
    if trips >= 1:    badges.append("First Trip")
    if trips >= 10:   badges.append("10 Trips Club")
    if trips >= 50:   badges.append("50 Trips Milestone")
    if trips >= 100:  badges.append("Century Commuter")
    
    if saved >= 1:    badges.append("1 kg CO2 Saved")
    if saved >= 10:   badges.append("10 kg CO2 Saved")
    if saved >= 50:   badges.append("EcoChampion")
    if saved >= 100:  badges.append("EcoHero")
    
    return badges

# ============================================================
# Route Option Builder
# ============================================================

def build_options(dist_km: float, base_time: float, traffic: float,
                  congestion: str, departure_time: Optional[str],
                  has_vehicle: bool) -> List[dict]:
    """Build all applicable transport modes for a journey."""

    rush = congestion in ("High", "Very High")
    drive_t = base_time * traffic

    # Walk timings
    walk_to_stop_t = min((dist_km * 0.12 / 5.0) * 60, 12)  # 12 min cap
    bus_wait_t     = 10 if rush else 7
    mrt_wait_t     = 5  if rush else 3
    bus_travel_t   = (dist_km * 0.82 / 25.0) * 60
    mrt_travel_t   = (dist_km * 0.85 / 55.0) * 60

    options = []

    # ── Drive ─────────────────────────────────────────────
    if has_vehicle:
        cost = dist_km * RM["petrol_per_km"] + RM["parking_city"]
        options.append({
            "mode":         "Drive",
            "emoji":        "🚗",
            "time_mins":    round(drive_t, 1),
            "cost_rm":      round(cost, 2),
            "carbon_kg":    round(dist_km * CO2["drive"], 3),
            "congestion":   congestion,
            "tags":         ["direct", "convenient"],
            "note":         "Fastest solo option but highest cost and emissions.",
        })

    # ── Carpool ───────────────────────────────────────────
    if has_vehicle:
        cost = (dist_km * RM["petrol_per_km"] + RM["parking_city"]) / 2
        options.append({
            "mode":         "Carpool",
            "emoji":        "🤝",
            "time_mins":    round(drive_t + 7, 1),
            "cost_rm":      round(cost, 2),
            "carbon_kg":    round(dist_km * CO2["carpool_2p"], 3),
            "congestion":   congestion,
            "tags":         ["eco", "savings", "social"],
            "note":         "Split cost and carbon with a neighbour going the same way.",
        })

    # ── Motorcycle ────────────────────────────────────────
    if has_vehicle and dist_km <= 20:
        options.append({
            "mode":         "Motorcycle",
            "emoji":        "🏍️",
            "time_mins":    round(drive_t * 0.80, 1),  # bikes filter traffic
            "cost_rm":      round(dist_km * RM["motorcycle_per_km"], 2),
            "carbon_kg":    round(dist_km * CO2["motorcycle"], 3),
            "congestion":   "Low",
            "tags":         ["fast", "cheap"],
            "note":         "Fastest during rush hour — lane-filtering helps a lot.",
        })

    # ── Grab ──────────────────────────────────────────────
    options.append({
        "mode":         "Grab / E-hailing",
        "emoji":        "📱",
        "time_mins":    round(drive_t + 6, 1),
        "cost_rm":      grab_cost(dist_km, rush),
        "carbon_kg":    round(dist_km * CO2["grab"], 3),
        "congestion":   congestion,
        "tags":         ["no-parking", "door-to-door"],
        "note":         "No parking stress. Check promos to lower fare.",
    })

    # ── Bus ───────────────────────────────────────────────
    if dist_km > 1.0:
        pub_t = walk_to_stop_t + bus_wait_t + bus_travel_t + 5
        options.append({
            "mode":         "Bus / RapidKL",
            "emoji":        "🚌",
            "time_mins":    round(pub_t, 1),
            "cost_rm":      RM["bus_flat"],
            "carbon_kg":    round(dist_km * CO2["bus"], 3),
            "congestion":   "Very Low",
            "tags":         ["cheapest", "eco"],
            "note":         "Lowest fare option. Use Touch 'n Go for discounts.",
        })

    # ── MRT / LRT ─────────────────────────────────────────
    if dist_km > 3.0:
        mrt_t = walk_to_stop_t + mrt_wait_t + mrt_travel_t + 5
        options.append({
            "mode":         "MRT / LRT",
            "emoji":        "🚇",
            "time_mins":    round(mrt_t, 1),
            "cost_rm":      round(mrt_cost(dist_km), 2),
            "carbon_kg":    round(dist_km * CO2["mrt_lrt"], 3),
            "congestion":   "None",
            "tags":         ["fast", "reliable", "eco"],
            "note":         "Immune to road congestion. Best for >5 km journeys.",
        })

    # ── Park & Ride ───────────────────────────────────────
    if dist_km > 8.0 and has_vehicle:
        drive_km   = dist_km * 0.40
        transit_km = dist_km * 0.60
        pr_t = (drive_km / 40) * 60 + 8 + (transit_km / 55) * 60
        pr_cost = (drive_km * RM["petrol_per_km"]
                   + RM["parking_park_ride"]
                   + mrt_cost(transit_km))
        pr_co2 = (drive_km * CO2["drive"] + transit_km * CO2["mrt_lrt"])
        options.append({
            "mode":         "Park & Ride",
            "emoji":        "🅿️",
            "time_mins":    round(pr_t, 1),
            "cost_rm":      round(pr_cost, 2),
            "carbon_kg":    round(pr_co2, 3),
            "congestion":   "Low",
            "tags":         ["hybrid", "eco", "no-city-parking"],
            "note":         "Drive to nearest station, ride transit the rest. Avoids city parking.",
        })

    # ── Cycling ───────────────────────────────────────────
    if dist_km <= 8.0:
        options.append({
            "mode":         "Cycling",
            "emoji":        "🚴",
            "time_mins":    round((dist_km / 18.0) * 60, 1),
            "cost_rm":      0.0,
            "carbon_kg":    0.0,
            "congestion":   "None",
            "tags":         ["free", "zero-carbon", "healthy"],
            "note":         "Zero cost, zero emissions, great exercise. Best under 8 km.",
        })

    # ── Walking ───────────────────────────────────────────
    if dist_km <= 2.5:
        options.append({
            "mode":         "Walking",
            "emoji":        "🚶",
            "time_mins":    round((dist_km / 5.0) * 60, 1),
            "cost_rm":      0.0,
            "carbon_kg":    0.0,
            "congestion":   "None",
            "tags":         ["free", "zero-carbon", "healthy"],
            "note":         "The greenest option of all. Easy for short trips.",
        })

    return options

# ============================================================
# Endpoints
# ============================================================

@app.get("/", tags=["Health"])
def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"app": "EcoFlow AI v2.0", "ai_status": "connected" if gemini_model else "fallback"}


@app.get("/health", tags=["Health"])
def health():
    return {
        "status":    "healthy",
        "gemini":    "connected" if gemini_model else "fallback mode",
        "firebase":  "connected",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Smart Routing ──────────────────────────────────────────
@app.post("/api/v1/smart-routing", tags=["Routing"])
def smart_routing(req: SmartRoutingRequest):
    """
    Core endpoint. Returns ranked transport options with realistic
    Malaysian cost, carbon, and time data.
    """
    dist_km, base_time = get_osrm(req.start_lon, req.start_lat,
                                   req.end_lon,   req.end_lat)
    traffic, congestion = get_traffic(req.departure_time)

    # Load user preferences from Firestore
    pref_doc = db.collection("user_profiles").document(req.user_id).get()
    if pref_doc.exists:
        p = pref_doc.to_dict()
        w_time, w_cost, w_co2 = p.get("prefer_fast", 0.33), p.get("prefer_cheap", 0.33), p.get("prefer_green", 0.34)
    else:
        w_time, w_cost, w_co2 = 0.33, 0.33, 0.34

    has_vehicle = req.vehicle_type in ("car", "motorcycle")
    options = build_options(dist_km, base_time, traffic, congestion,
                            req.departure_time, has_vehicle)

    # Normalise + personalised score (lower = better)
    max_t    = max(o["time_mins"] for o in options) or 1
    max_c    = max(o["cost_rm"]   for o in options) or 1
    max_co2  = max(o["carbon_kg"] for o in options) or 1
    drive_co2 = dist_km * CO2["drive"]

    for o in options:
        o["score"] = round(
            (o["time_mins"] / max_t)    * w_time +
            (o["cost_rm"]   / max_c)    * w_cost +
            (o["carbon_kg"] / max_co2)  * w_co2,
            4
        )
        o["carbon_saved_vs_driving"] = round(max(0, drive_co2 - o["carbon_kg"]), 3)
        o["distance_km"] = round(dist_km, 2)

    options.sort(key=lambda x: x["score"])
    options[0]["is_recommended"] = True

    return {
        "distance_km":       round(dist_km, 2),
        "congestion":        congestion,
        "traffic_factor":    traffic,
        "departure_time":    req.departure_time or datetime.now().strftime("%H:%M"),
        "options":           options,
        "personalised_for":  req.user_id,
    }


# ── AI Insight ────────────────────────────────────────────
@app.post("/api/v1/ai-insight", tags=["AI"])
def ai_insight(data: AIInsightRequest):
    """Gemini-powered commute recommendation for a chosen route."""

    alts_text = ""
    if data.alternatives:
        alts_text = "\nOther options the user could have chosen:\n"
        for a in data.alternatives[:3]:
            alts_text += (f"  - {a.get('mode')}: {a.get('time_mins')} min, "
                          f"RM {a.get('cost_rm')}, {a.get('carbon_kg')} kg CO₂\n")

    ctx = f"\nUser context: {data.user_context}" if data.user_context else ""

    prompt = f"""You are EcoFlow, a friendly Malaysian commute assistant helping urban commuters in KL/Selangor make eco-friendly travel decisions.

The user chose: {data.mode} — {data.route_name}
Distance: {data.distance_km:.1f} km | Time: {data.time_mins:.0f} min | Cost: RM {data.cost_rm:.2f} | Carbon: {data.carbon_kg:.3f} kg CO₂
{alts_text}{ctx}

Give a SHORT (2–3 sentences), encouraging, specific recommendation in English.
Mention Malaysian context (KL traffic, ringgit, Touch 'n Go, Grab promos) where relevant.
Use exactly 1 emoji at the start."""

    fallback = smart_fallback(data.mode)
    text = call_gemini(prompt, fallback)

    return {
        "ai_insight": text,
        "model":      "gemini-2.5-flash" if gemini_model else "rule-based fallback",
        "mode":       data.mode,
    }

# ── AI Chat (RAG 升级版) ──────────────────────────────────
@app.post("/api/v1/ai-chat", tags=["AI"])
def ai_chat(req: ChatRequest):
    """
    结合了 Vertex AI Search (RAG) 的智能聊天。
    Gemini 会根据你上传的 PDF 政策文档（NETR等）来回答用户。
    """
    # 1. 先去 PDF 知识库搜索马来西亚官方政策背景 (RAG)
    kb_context = search_rag_knowledge(req.message)
    
    # 2. 构造 Prompt，将搜索到的知识喂给 Gemini
    ctx_str = f"\nRoute context: {req.context}" if req.context else ""
    
    prompt = f"""You are EcoFlow Assistant, a professional Malaysian green mobility expert.
    
    【Reference Policy Data (Grounded)】:
    {kb_context if kb_context else "No specific policy document found. Use general eco-knowledge."}
    
    {ctx_str}
    User Question: {req.message}

    Instructions:
    - If reference data mentions NETR (National Energy Transition Roadmap), 2050 carbon targets, or RapidKL/MRT specific policies, prioritize those facts.
    - Be concise (max 3 sentences).
    - Use 1-2 emojis and professional Malaysian context (e.g., mention Touch 'n Go or MRT)."""

    # 3. 调用 Gemini 生成带知识背景的回复
    fallback = "🌱 I'm here to help you commute smarter based on Malaysia's green policies!"
    reply = call_gemini(prompt, fallback)

    return {
        "reply": reply, 
        "user_id": req.user_id,
        "source": "Grounded in National Policy" if kb_context else "General Gemini Knowledge"
    }


# ── Save Trip ─────────────────────────────────────────────
@app.post("/api/v1/save-trip", tags=["Trips"])
def save_trip(data: SaveTripRequest):
    """Persist a completed trip and update per-user + global stats."""
    trip_id = f"{data.user_id}_{int(time.time())}"

    db.collection("trips").document(trip_id).set({
        "trip_id":                 trip_id,
        "user_id":                 data.user_id,
        "mode_chosen":             data.mode_chosen,
        "route_name":              data.route_name,
        "time_mins":               data.time_mins,
        "cost_rm":                 data.cost_rm,
        "carbon_kg":               data.carbon_kg,
        "distance_km":             data.distance_km,
        "carbon_saved_vs_driving": data.carbon_saved_vs_driving,
        "start_lat":               data.start_lat,
        "start_lon":               data.start_lon,
        "end_lat":                 data.end_lat,
        "end_lon":                 data.end_lon,
        "timestamp":               firestore.SERVER_TIMESTAMP,
        "date":                    datetime.utcnow().strftime("%Y-%m-%d"),
    })

    # Update personal cumulative stats (atomic increments)
    drive_cost_equivalent = data.distance_km * RM["petrol_per_km"] + RM["parking_city"]
    cost_saved = max(0, drive_cost_equivalent - data.cost_rm)

    db.collection("user_stats").document(data.user_id).set({
        "total_trips":        firestore.Increment(1),
        "total_distance_km":  firestore.Increment(data.distance_km),
        "total_carbon_kg":    firestore.Increment(data.carbon_kg),
        "total_cost_rm":      firestore.Increment(data.cost_rm),
        "total_carbon_saved": firestore.Increment(data.carbon_saved_vs_driving),
        "total_cost_saved":   firestore.Increment(cost_saved),
        "last_trip":          datetime.utcnow().strftime("%Y-%m-%d"),
    }, merge=True)

    # Update global community stats
    db.collection("community_stats").document("global").set({
        "total_trips":        firestore.Increment(1),
        "total_carbon_saved": firestore.Increment(data.carbon_saved_vs_driving),
        "total_cost_saved":   firestore.Increment(cost_saved),
        "total_distance_km":  firestore.Increment(data.distance_km),
    }, merge=True)

    trees_eq = round(data.carbon_saved_vs_driving / 21.77, 4)

    return {
        "status":           "saved",
        "trip_id":          trip_id,
        "carbon_saved_kg":  data.carbon_saved_vs_driving,
        "cost_saved_rm":    round(cost_saved, 2),
        "trees_equivalent": trees_eq,
        "message":          f"Trip saved! 🌱 You saved {data.carbon_saved_vs_driving:.3f} kg CO₂ — that's {trees_eq:.4f} trees worth of absorption.",
    }


# ── Trip History ──────────────────────────────────────────
@app.get("/api/v1/trip-history/{user_id}", tags=["Trips"])
def trip_history(user_id: str, limit: int = Query(default=20, le=100)):
    """Fetch recent trips for a user."""
    docs = (db.collection("trips")
              .where("user_id", "==", user_id)
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(limit)
              .stream())
    trips = [d.to_dict() for d in docs]
    return {"user_id": user_id, "trips": trips, "count": len(trips)}


# ── User Profile ──────────────────────────────────────────
@app.post("/api/v1/user-profile", tags=["Profile"])
def save_profile(pref: UserPreference):
    """Save (or update) user commute preferences."""
    total = pref.prefer_fast + pref.prefer_cheap + pref.prefer_green
    if total == 0:
        raise HTTPException(400, "Preference weights cannot all be zero.")

    data = {
        "prefer_fast":   round(pref.prefer_fast  / total, 3),
        "prefer_cheap":  round(pref.prefer_cheap / total, 3),
        "prefer_green":  round(pref.prefer_green / total, 3),
        "vehicle_type":  pref.vehicle_type,
        "updated_at":    datetime.utcnow().isoformat(),
    }
    if pref.home_lat is not None: data["home_lat"] = pref.home_lat
    if pref.home_lon is not None: data["home_lon"] = pref.home_lon
    if pref.work_lat is not None: data["work_lat"] = pref.work_lat
    if pref.work_lon is not None: data["work_lon"] = pref.work_lon

    db.collection("user_profiles").document(pref.user_id).set(data, merge=True)
    return {"status": "saved", "profile": data}


@app.get("/api/v1/user-profile/{user_id}", tags=["Profile"])
def get_profile(user_id: str):
    doc = db.collection("user_profiles").document(user_id).get()
    if not doc.exists:
        return {"user_id": user_id, "profile": None,
                "message": "No profile yet — using balanced defaults (33/33/34)."}
    return {"user_id": user_id, "profile": doc.to_dict()}


# ── Personal Impact ───────────────────────────────────────
@app.get("/api/v1/impact/{user_id}", tags=["Impact"])
def user_impact(user_id: str):
    """Personal carbon & cost savings summary with badges."""
    doc = db.collection("user_stats").document(user_id).get()
    if not doc.exists:
        return {"user_id": user_id, "stats": None,
                "message": "No trips recorded yet. Start your first EcoFlow journey!"}

    s = doc.to_dict()
    saved_co2 = s.get("total_carbon_saved", 0)

    return {
        "user_id": user_id,
        "stats": {
            "total_trips":         s.get("total_trips", 0),
            "total_distance_km":   round(s.get("total_distance_km", 0), 1),
            "total_carbon_kg":     round(s.get("total_carbon_kg", 0), 3),
            "total_carbon_saved":  round(saved_co2, 3),
            "total_cost_rm":       round(s.get("total_cost_rm", 0), 2),
            "total_cost_saved_rm": round(s.get("total_cost_saved", 0), 2),
            "trees_equivalent":    round(saved_co2 / 21.77, 3),
            "last_trip":           s.get("last_trip", "N/A"),
        },
        "badges": calc_badges(s),
    }


# ── Community Impact ──────────────────────────────────────
@app.get("/api/v1/community-impact", tags=["Impact"])
def community_impact():
    """Aggregated impact across all EcoFlow users."""
    doc = db.collection("community_stats").document("global").get()
    if not doc.exists:
        return {"message": "No community data yet.", "stats": {}}

    s = doc.to_dict()
    saved = s.get("total_carbon_saved", 0)
    return {
        "stats": {
            "total_trips":          s.get("total_trips", 0),
            "total_carbon_saved_kg": round(saved, 2),
            "total_cost_saved_rm":   round(s.get("total_cost_saved", 0), 2),
            "total_distance_km":     round(s.get("total_distance_km", 0), 1),
            "trees_equivalent":      round(saved / 21.77, 2),
        },
        "message": f"EcoFlow users have collectively saved {saved:.1f} kg CO₂ 🌍",
    }


# ── Leaderboard ───────────────────────────────────────────
@app.get("/api/v1/leaderboard", tags=["Impact"])
def leaderboard(limit: int = Query(default=10, le=50)):
    """Top eco-commuters ranked by CO₂ saved."""
    docs = (db.collection("user_stats")
              .order_by("total_carbon_saved", direction=firestore.Query.DESCENDING)
              .limit(limit)
              .stream())

    board = []
    for rank, doc in enumerate(docs, 1):
        d = doc.to_dict()
        board.append({
            "rank":            rank,
            "user_id":         doc.id[:6] + "***",    # privacy mask
            "carbon_saved_kg": round(d.get("total_carbon_saved", 0), 2),
            "total_trips":     d.get("total_trips", 0),
            "trees_eq":        round(d.get("total_carbon_saved", 0) / 21.77, 2),
            "badges":          calc_badges(d),
        })

    return {"leaderboard": board, "count": len(board)}


# ── Carpool Match ─────────────────────────────────────────
@app.post("/api/v1/carpool-match", tags=["Carpool"])
def carpool_match(req: CarpoolMatchRequest):
    """Find users with similar routes for carpooling."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        all_docs = (db.collection("trips")
                      .where("date", "==", today)
                      .limit(300)
                      .stream())
    except Exception:
        all_docs = db.collection("trips").limit(300).stream()

    matches = []
    for doc in all_docs:
        d = doc.to_dict()
        if d.get("user_id") == req.user_id:
            continue
        try:
            ds = haversine(req.start_lat, req.start_lon, d["start_lat"], d["start_lon"])
            de = haversine(req.end_lat,   req.end_lon,   d["end_lat"],   d["end_lon"])
        except (KeyError, TypeError):
            continue

        if ds <= req.max_detour_km and de <= req.max_detour_km:
            dist = d.get("distance_km", 0)
            matches.append({
                "user_id":          d["user_id"][:6] + "***",
                "route_name":       d.get("route_name", "Similar route"),
                "start_diff_km":    round(ds, 2),
                "end_diff_km":      round(de, 2),
                "mode":             d.get("mode_chosen", "Drive"),
                "carbon_saving_kg": round(dist * CO2["carpool_2p"], 3),
                "cost_saving_rm":   round((dist * RM["petrol_per_km"]) / 2, 2),
            })

    matches.sort(key=lambda x: x["start_diff_km"] + x["end_diff_km"])
    tip = ("Connect with matched users in the app to arrange carpooling!"
           if matches else "No matches right now — try again during morning/evening peak.")

    return {
        "matches_found": len(matches),
        "matches":       matches[:10],
        "tip":           tip,
    }


# ── Register Carpool (发布行程供别人匹配) ──────────────────
class CarpoolRegisterRequest(BaseModel):
    user_id:        str
    name:           str = "Anonymous"
    start_lat:      float
    start_lon:      float
    end_lat:        float
    end_lon:        float
    departure_time: str        # "HH:MM"
    seats_available: int = 1
    contact_hint:   Optional[str] = None  # e.g. "WhatsApp 012-xxx"

@app.post("/api/v1/register-carpool", tags=["Carpool"])
def register_carpool(req: CarpoolRegisterRequest):
    """
    发布行程 — 让其他用户可以找到你做拼车匹配。
    有效期24小时，过期自动失效。
    """
    doc_id = f"{req.user_id}_{req.departure_time.replace(':', '')}_{int(time.time())}"
    db.collection("carpool_pool").document(doc_id).set({
        "user_id":         req.user_id,
        "name":            req.name,
        "start_lat":       req.start_lat,
        "start_lon":       req.start_lon,
        "end_lat":         req.end_lat,
        "end_lon":         req.end_lon,
        "departure_time":  req.departure_time,
        "seats_available": req.seats_available,
        "contact_hint":    req.contact_hint or "Contact via app",
        "date":            datetime.utcnow().strftime("%Y-%m-%d"),
        "timestamp":       firestore.SERVER_TIMESTAMP,
        "active":          True,
    })
    return {
        "status":   "registered",
        "doc_id":   doc_id,
        "message":  f"Your carpool offer is live for today! Others near your route can now find you.",
        "expires":  "End of today (UTC)",
    }


@app.post("/api/v1/find-carpool", tags=["Carpool"])
def find_carpool(req: CarpoolMatchRequest):
    """
    找拼车 — 在 carpool_pool 里搜索今天出发、路线相近的用户。
    同时也搜索历史行程（carpool_match 的逻辑保留）。
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    matches = []

    # 搜索已注册的 carpool pool
    try:
        pool_docs = (db.collection("carpool_pool")
                       .where("date",   "==", today)
                       .where("active", "==", True)
                       .limit(200)
                       .stream())
        for doc in pool_docs:
            d = doc.to_dict()
            if d.get("user_id") == req.user_id:
                continue
            
            try:
                ds = haversine(req.start_lat, req.start_lon, d["start_lat"], d["start_lon"])
                de = haversine(req.end_lat,   req.end_lon,   d["end_lat"],   d["end_lon"])
            except (KeyError, TypeError):
                continue
                
            if ds <= req.max_detour_km and de <= req.max_detour_km:
                matches.append({
                    "source":           "carpool_pool",
                    "user_id":          d["user_id"][:6] + "***",
                    "name":             d.get("name", "Anonymous"),
                    "departure_time":   d.get("departure_time", "?"),
                    "seats_available":  d.get("seats_available", 1),
                    "contact_hint":     d.get("contact_hint", "Contact via app"),
                    "start_diff_km":    round(ds, 2),
                    "end_diff_km":      round(de, 2),
                    "estimated_saving_rm":  round(10 * RM["petrol_per_km"] / 2, 2),
                })
    except Exception as e:
        log.warning(f"Carpool pool search failed: {e}")

    matches.sort(key=lambda x: x["start_diff_km"] + x["end_diff_km"])
    tip = ("Great! Contact your match via the app to confirm pickup details." 
           if matches else "No carpool matches right now. Register your route so others can find you!")

    return {
        "matches_found": len(matches),
        "matches":       matches[:10],
        "tip":           tip,
    }


@app.get("/api/v1/eco-forecast/{user_id}", tags=["Impact"])
def eco_forecast(user_id: str):
    """Predicts yearly impact based on current user behavior."""
    doc = db.collection("user_stats").document(user_id).get()
    if not doc.exists:
        return {"message": "Need more data"}
    
    stats = doc.to_dict()
    saved = stats.get("total_carbon_saved", 0)
    trips = stats.get("total_trips", 1)
    
    # Simple projection: If user keeps this up for a year (avg 22 working days/month)
    yearly_projection = (saved / trips) * 22 * 12
    
    return {
        "projected_yearly_savings_kg": round(yearly_projection, 2),
        "trees_equivalent": round(yearly_projection / 21.77, 1),
        "eco_rank": "Sapling" if yearly_projection < 50 else "Forest Guardian"
    }

# ── Full AI Analysis (核心功能：综合比较所有路线，AI给最佳建议) ──
class FullAnalysisRequest(BaseModel):
    user_id:        str
    start_lat:      float
    start_lon:      float
    end_lat:        float
    end_lon:        float
    departure_time: Optional[str] = None
    vehicle_type:   Optional[str] = "car"
    priority:       Optional[str] = "balanced"  # "eco" | "fast" | "cheap" | "balanced"
    language:       Optional[str] = "en"        # "en" | "zh" | "ms"

@app.post("/api/v1/full-analysis", tags=["AI"])
def full_analysis(req: FullAnalysisRequest):
    """
    核心端点：
    1. 计算所有交通方式的时间+碳排放+费用+拥堵
    2. 为每个方案算 eco_score（0-100）
    3. Gemini AI 综合分析，用中/英/马来文给出最佳低碳出行建议
    """
    # --- Step 1: 计算路线 ---
    dist_km, base_time = get_osrm(req.start_lon, req.start_lat,
                                   req.end_lon,   req.end_lat)
    traffic, congestion = get_traffic(req.departure_time)
    has_vehicle = req.vehicle_type in ("car", "motorcycle")
    options = build_options(dist_km, base_time, traffic, congestion,
                            req.departure_time, has_vehicle)

    # --- Step 2: 算 Eco Score（0=最差，100=最好）---
    drive_co2  = dist_km * CO2["drive"]
    drive_cost = dist_km * RM["petrol_per_km"] + RM["parking_city"]
    drive_time = base_time * traffic

    for o in options:
        # Carbon score (权重50%): 节省多少碳排放
        carbon_pct = 1 - (o["carbon_kg"] / drive_co2) if drive_co2 > 0 else 1
        # Cost score (权重25%): 节省多少费用
        cost_pct   = 1 - (o["cost_rm"] / drive_cost) if drive_cost > 0 else 1
        # Congestion score (权重25%): 拥堵越低分越高
        cong_map   = {"None": 1.0, "Very Low": 0.9, "Low": 0.75,
                      "Medium": 0.5, "High": 0.3, "Very High": 0.1}
        cong_score = cong_map.get(o["congestion"], 0.5)

        raw = (carbon_pct * 0.50 + cost_pct * 0.25 + cong_score * 0.25)
        o["eco_score"]              = max(0, min(100, round(raw * 100)))
        o["carbon_saved_vs_driving"] = round(max(0, drive_co2 - o["carbon_kg"]), 3)
        o["cost_saved_vs_driving"]   = round(max(0, drive_cost - o["cost_rm"]), 2)
        o["distance_km"]             = round(dist_km, 2)

    # 按 eco_score 降序排列（最绿在前）
    options_by_eco = sorted(options, key=lambda x: -x["eco_score"])

    # --- Step 3: 根据 priority 决定推荐 ---
    if req.priority == "eco":
        recommended = options_by_eco[0]
    elif req.priority == "fast":
        recommended = min(options, key=lambda x: x["time_mins"])
    elif req.priority == "cheap":
        recommended = min(options, key=lambda x: x["cost_rm"])
    else:  # balanced
        # 平衡分：eco_score + 时间/最大时间 反比
        max_t = max(o["time_mins"] for o in options) or 1
        recommended = max(options,
                          key=lambda x: x["eco_score"] * 0.6
                          + (1 - x["time_mins"] / max_t) * 40)

    # --- Step 4: Gemini 综合分析 ---
    lang_prompt = {"zh": "用中文回复", "ms": "Balas dalam Bahasa Melayu", "en": "Reply in English"}
    lang_instr  = lang_prompt.get(req.language, "Reply in English")

    top3 = options_by_eco[:3]
    top3_text = "\n".join(
        f"  {i+1}. {o['mode']} — {o['time_mins']}min, RM{o['cost_rm']}, "
        f"{o['carbon_kg']}kg CO₂, Eco Score: {o['eco_score']}/100, Congestion: {o['congestion']}"
        for i, o in enumerate(top3)
    )

    all_text = "\n".join(
        f"  • {o['mode']}: {o['time_mins']}min | RM{o['cost_rm']} | {o['carbon_kg']}kg CO₂ | "
        f"Eco {o['eco_score']}/100 | {o['congestion']} congestion"
        for o in options_by_eco
    )

    prompt = f"""You are EcoFlow, a smart Malaysian urban commute AI for the MyAI Future Hackathon.

Journey: {round(dist_km, 1)} km | Departure: {req.departure_time or 'Now'} | Traffic: {congestion}

ALL transport options ranked by Eco Score:
{all_text}

User priority: {req.priority}
Recommended option: {recommended['mode']} (Eco Score: {recommended['eco_score']}/100)

{lang_instr}. Give a clear, friendly recommendation in 3–4 sentences:
1. Which option you recommend and WHY (mention time, cost, carbon, congestion together)
2. How much CO₂ and money they save vs driving alone
3. One practical tip for this commute in Malaysian context (Touch 'n Go, Grab promo, park & ride station, etc.)

Be specific, encouraging, and mention actual numbers."""

    fallback = (f"Based on your journey, {recommended['mode']} is your best choice — "
                f"Eco Score {recommended['eco_score']}/100. "
                f"You save RM{recommended['cost_saved_vs_driving']} and "
                f"{recommended['carbon_saved_vs_driving']} kg CO₂ compared to driving alone!")

    ai_recommendation = call_gemini(prompt, fallback)

    return {
        "journey": {
            "distance_km":    round(dist_km, 2),
            "congestion":     congestion,
            "traffic_factor": traffic,
            "departure_time": req.departure_time or datetime.now().strftime("%H:%M"),
        },
        "all_options_ranked_by_eco": options_by_eco,      # 全部选项，按eco_score排序
        "recommended": recommended,                         # AI选出的最佳方案
        "ai_recommendation": ai_recommendation,            # Gemini综合建议
        "baseline_driving": {                              # 对比基准（单人驾车）
            "time_mins":  round(drive_time, 1),
            "cost_rm":    round(drive_cost, 2),
            "carbon_kg":  round(drive_co2,  3),
            "eco_score":  0,
        },
     }


# ============================================================
# Vertex AI Agent Builder endpoint
# ============================================================
# dialogflow imported lazily in vertex_agent_chat
import uuid

VERTEX_AGENT_ID = "agent_1776677873136"
VERTEX_LOCATION  = "global"

_cx_sessions: dict = {}

class VertexAgentRequest(BaseModel):
    user_id: str
    message: str
    language: Optional[str] = "en"

@app.post("/api/v1/vertex-agent", tags=["Agent"])
def vertex_agent_chat(req: VertexAgentRequest):
    try:
        from google.cloud import dialogflow_cx_v3 as dialogflow
        import uuid
        session_id = _cx_sessions.get(req.user_id)
        if not session_id:
            session_id = str(uuid.uuid4())
            _cx_sessions[req.user_id] = session_id

        client = dialogflow.SessionsClient()
        session_path = client.session_path(
            project=PROJECT_ID,
            location=VERTEX_LOCATION,
            agent=VERTEX_AGENT_ID,
            session=session_id,
        )
        text_input = dialogflow.TextInput(text=req.message, language_code="en")
        query_input = dialogflow.QueryInput(text=text_input, language_code="en")
        response = client.detect_intent(
            request={"session": session_path, "query_input": query_input}
        )
        reply_texts = []
        for msg in response.query_result.response_messages:
            if msg.text and msg.text.text:
                reply_texts.extend(msg.text.text)
        reply = " ".join(reply_texts) if reply_texts else "I couldn't find an answer. Please try again."
        return {
            "reply": reply,
            "agent": "Vertex AI Agent Builder",
            "model": "gemini-2.5-pro",
            "session_id": session_id,
        }
    except Exception as e:
        log.error(f"Vertex Agent error: {e}")
        fallback_reply = call_gemini(
            f"You are EcoFlow, a Malaysian green mobility assistant. Answer briefly: {req.message}",
            "Please try again or use the Genkit agent."
        )
        return {"reply": fallback_reply, "agent": "Gemini Fallback", "error": str(e)}
