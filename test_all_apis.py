"""
test_all_apis.py — Test every EcoFlow endpoint
Run: python test_all_apis.py
Make sure uvicorn is running first: uvicorn main:app --reload
"""

import requests, json

BASE = "http://localhost:8000"

def p(label, r):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"  Status: {r.status_code}")
    print(f"{'='*55}")
    try:
        d = r.json()
        print(json.dumps(d, indent=2, ensure_ascii=False)[:1200])
        if len(json.dumps(d)) > 1200: print("  ... (truncated)")
    except:
        print(r.text[:500])

# ── 1. Health ─────────────────────────────────────────────
p("1. HEALTH CHECK", requests.get(f"{BASE}/health"))

# ── 2. Smart Routing ──────────────────────────────────────
p("2. SMART ROUTING (KL Sentral → KLCC)",
  requests.post(f"{BASE}/api/v1/smart-routing", json={
    "user_id":        "test_user_01",
    "start_lat":      3.1340,
    "start_lon":      101.6862,
    "end_lat":        3.1579,
    "end_lon":        101.7119,
    "departure_time": "08:30",
    "vehicle_type":   "car",
    "num_passengers": 1
  }))

# ── 3. Full AI Analysis ───────────────────────────────────
p("3. FULL AI ANALYSIS — Eco Priority (Chinese)",
  requests.post(f"{BASE}/api/v1/full-analysis", json={
    "user_id":        "test_user_01",
    "start_lat":      3.1340,
    "start_lon":      101.6862,
    "end_lat":        3.1579,
    "end_lon":        101.7119,
    "departure_time": "08:30",
    "vehicle_type":   "car",
    "priority":       "eco",
    "language":       "zh"
  }))

p("3b. FULL AI ANALYSIS — Balanced Priority (English, Evening Rush)",
  requests.post(f"{BASE}/api/v1/full-analysis", json={
    "user_id":        "test_user_01",
    "start_lat":      3.1340,
    "start_lon":      101.6862,
    "end_lat":        3.1579,
    "end_lon":        101.7119,
    "departure_time": "17:30",
    "vehicle_type":   "car",
    "priority":       "balanced",
    "language":       "en"
  }))

# ── 4. AI Insight ─────────────────────────────────────────
p("4. AI INSIGHT (MRT route)",
  requests.post(f"{BASE}/api/v1/ai-insight", json={
    "route_name":   "KL Sentral → KLCC via MRT",
    "mode":         "MRT / LRT",
    "time_mins":    22,
    "cost_rm":      2.80,
    "carbon_kg":    0.028,
    "distance_km":  5.2,
    "user_context": "morning rush hour, eco-conscious commuter"
  }))

# ── 5. AI Chat ────────────────────────────────────────────
p("5. AI CHAT",
  requests.post(f"{BASE}/api/v1/ai-chat", json={
    "user_id": "test_user_01",
    "message": "我应该用Touch n Go还是现金坐MRT比较省钱？"
  }))

# ── 6. Register Carpool ───────────────────────────────────
p("6. REGISTER CARPOOL (发布行程)",
  requests.post(f"{BASE}/api/v1/register-carpool", json={
    "user_id":         "test_user_01",
    "name":            "Ali",
    "start_lat":       3.1340,
    "start_lon":       101.6862,
    "end_lat":         3.1579,
    "end_lon":         101.7119,
    "departure_time":  "08:00",
    "seats_available": 2,
    "contact_hint":    "WhatsApp 012-xxx"
  }))

# ── 7. Find Carpool ───────────────────────────────────────
p("7. FIND CARPOOL (找同路人)",
  requests.post(f"{BASE}/api/v1/find-carpool", json={
    "user_id":       "test_user_02",
    "start_lat":     3.1350,
    "start_lon":     101.6870,
    "end_lat":       3.1570,
    "end_lon":       101.7110,
    "max_detour_km": 2.0
  }))

# ── 8. Save Trip ──────────────────────────────────────────
p("8. SAVE TRIP",
  requests.post(f"{BASE}/api/v1/save-trip", json={
    "user_id":                 "test_user_01",
    "mode_chosen":             "MRT / LRT",
    "route_name":              "KL Sentral → KLCC",
    "time_mins":               22,
    "cost_rm":                 2.80,
    "carbon_kg":               0.028,
    "distance_km":             5.2,
    "start_lat":               3.1340,
    "start_lon":               101.6862,
    "end_lat":                 3.1579,
    "end_lon":                 101.7119,
    "carbon_saved_vs_driving": 0.861
  }))

# ── 9. User Profile ───────────────────────────────────────
p("9. SAVE USER PROFILE (eco-focused)",
  requests.post(f"{BASE}/api/v1/user-profile", json={
    "user_id":      "test_user_01",
    "prefer_fast":  0.2,
    "prefer_cheap": 0.3,
    "prefer_green": 0.5,
    "vehicle_type": "car",
    "work_lat":     3.1579,
    "work_lon":     101.7119
  }))

p("9b. GET USER PROFILE",
  requests.get(f"{BASE}/api/v1/user-profile/test_user_01"))

# ── 10. Personal Impact ───────────────────────────────────
p("10. PERSONAL IMPACT & BADGES",
  requests.get(f"{BASE}/api/v1/impact/test_user_01"))

# ── 11. Trip History ──────────────────────────────────────
p("11. TRIP HISTORY",
  requests.get(f"{BASE}/api/v1/trip-history/test_user_01?limit=5"))

# ── 12. Community Impact ─────────────────────────────────
p("12. COMMUNITY IMPACT",
  requests.get(f"{BASE}/api/v1/community-impact"))

# ── 13. Leaderboard ───────────────────────────────────────
p("13. LEADERBOARD (top 5)",
  requests.get(f"{BASE}/api/v1/leaderboard?limit=5"))

print("\n✅ All tests done! Check results above.")
