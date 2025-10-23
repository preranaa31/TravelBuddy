import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
import pandas as pd
import os
import random
import datetime
import requests
import json


if "itinerary" not in st.session_state:
    st.session_state.itinerary = None


APP_TITLE = "Student AI Travel Planner"
BACKGROUND_IMAGE = "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1400&q=80"
MAP_START_ZOOM = 12
GEOCODER_USER_AGENT = "student_travel_planner_app"


HF_API_KEY = os.getenv("HF_API_KEY")
HF_API_URL = os.getenv("HF_API_URL")  




def set_background():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url('{BACKGROUND_IMAGE}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .overlay {{
            background: rgba(255,255,255,0.85);
            padding: 20px;
            border-radius: 12px;
            color: #000;
        }}
        .metric-container {{
            background: rgba(255,255,255,0.85) !important;
            border-radius: 8px;
            padding: 10px;
            color: #000 !important;
        }}
        .block-container {{
            padding-top: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def geocode_city(city_name):
    geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT)
    try:
        location = geolocator.geocode(city_name, exactly_one=True, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except Exception:
        return None
    return None

def sample_pois_for_city(city_latlon, interests, n=8):
    lat, lon = city_latlon
    pois = []
    categories = interests if interests else ["cafe", "museum", "park", "market", "historic"]
    for i in range(n):
        jitter_lat = lat + (random.random() - 0.5) * 0.08
        jitter_lon = lon + (random.random() - 0.5) * 0.08
        cat = random.choice(categories)
        name = f"{cat.title()} Spot {i+1}"
        price_label = random.choice(["free", "low", "medium"])
        pois.append({
            "name": name,
            "lat": jitter_lat,
            "lon": jitter_lon,
            "category": cat,
            "price": price_label,
            "duration_hours": random.choice([0.5,1,1.5,2,3]),
        })
    return pois

def simple_budget_estimate(pois):
    cost_map = {"free": 0, "low": 200, "medium": 600}
    total = sum(cost_map.get(p["price"], 100) for p in pois)
    return total

def generate_rule_based_itinerary(destination, start_date, days, budget, interests):
    latlon = geocode_city(destination)
    if not latlon:
        return {"error": f"Could not geocode '{destination}'. Try another city."}

    pois = sample_pois_for_city(latlon, interests, n=days*4)
    itinerary = []
    idx = 0
    for day in range(days):
        day_pois = []
        hours_available = 8
        while hours_available > 0 and idx < len(pois):
            p = pois[idx]
            if p["duration_hours"] <= hours_available:
                day_pois.append(p)
                hours_available -= p["duration_hours"]
            idx += 1
        itinerary.append({
            "day": day+1,
            "date": (start_date + datetime.timedelta(days=day)).isoformat(),
            "activities": day_pois,
        })
    budget_est = simple_budget_estimate(pois)
    return {"latlon": latlon, "itinerary": itinerary, "pois": pois, "budget_est": budget_est}

def call_huggingface_for_itinerary(destination, start_date, days, budget, interests):
    prompt = f"""
    You are a travel planner for students on a budget.
    Destination: {destination}
    Start date: {start_date.isoformat()}
    Days: {days}
    Budget (INR): {budget}
    Interests: {', '.join(interests)}
    Provide a day-by-day itinerary in JSON format with keys: itinerary (list of days with activities), latlon (approximate coordinates), pois (list of POIs), budget_est
    """
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
        result = response.json()
        text = result[0]["generated_text"] if isinstance(result, list) else str(result)
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}  
    except Exception as e:
        return {"error": str(e)}



st.set_page_config(page_title=APP_TITLE, layout="wide")
set_background()

with st.container():
    st.markdown("<div class='overlay'>", unsafe_allow_html=True)
    st.title(APP_TITLE)
    st.write("Plan quick, budget-friendly trips tailored for students. Get a day-by-day itinerary, cost estimates, and an interactive map.")
    st.markdown("</div>", unsafe_allow_html=True)


st.sidebar.header("Trip details")
origin = st.sidebar.text_input("Starting location", value="")
if not origin:
    st.sidebar.error("Starting location is required!")

destination = st.sidebar.text_input("Destination city (e.g., Paris, France)", value="Bengaluru, India")
start_date = st.sidebar.date_input("Start date", value=datetime.date.today() + datetime.timedelta(days=7))
days = st.sidebar.number_input("Trip length (days)", min_value=1, max_value=14, value=2)
budget = st.sidebar.number_input("Budget (INR, approximate)", min_value=500, value=3000, step=100)
st.sidebar.markdown("---")
interests_raw = st.sidebar.multiselect(
    "Interests (choose a few)",
    options=["cafes","museums","nature/parks","shopping/markets","history","adventure","nightlife","budget-food"],
    default=["cafes","budget-food"]
)
use_hf = st.sidebar.checkbox("Use Hugging Face for itinerary generation", value=False)


if st.sidebar.button("Generate itinerary"):
    if not origin:
        st.warning("Please enter a starting location to continue.")
    else:
        with st.spinner("Creating your student-friendly itinerary..."):
            if use_hf and HF_API_KEY:
                result = call_huggingface_for_itinerary(destination, start_date, days, budget, interests_raw)
            else:
                result = generate_rule_based_itinerary(destination, start_date, days, budget, interests_raw)
            st.session_state.itinerary = result


if st.session_state.itinerary:
    result = st.session_state.itinerary
    if result.get("error"):
        st.error(result["error"])
    else:
        
        cols = st.columns(3)
        with cols[0]:
            st.metric("Destination", destination)
        with cols[1]:
            st.metric("Dates", f"{start_date.isoformat()} → {(start_date + datetime.timedelta(days=days-1)).isoformat()}")
        with cols[2]:
            est = result.get("budget_est", budget)
            st.metric("Estimated cost (INR)", f"~{est}")
        st.markdown("---")

        
        st.subheader("Itinerary")
        for day in result.get('itinerary', []):
            st.markdown(f"<div class='overlay'><b>Day {day['day']} — {day['date']}</b></div>", unsafe_allow_html=True)
            for act in day['activities']:
                st.markdown(f"<div class='overlay'>• {act['name']} ({act['category']}) — approx {act['duration_hours']} hr — cost: {act['price']}</div>", unsafe_allow_html=True)
            st.markdown("---")

        
        orig_coords = geocode_city(origin)
        dest_coords = result.get('latlon') or (result['pois'][0]['lat'], result['pois'][0]['lon'])
        fmap = folium.Map(location=orig_coords, zoom_start=MAP_START_ZOOM)

        
        folium.Marker(location=orig_coords, popup="Starting location", icon=folium.Icon(color='green')).add_to(fmap)
        folium.Marker(location=dest_coords, popup="Destination", icon=folium.Icon(color='red')).add_to(fmap)

        
        folium.PolyLine([orig_coords, dest_coords], color="blue", weight=4, opacity=0.7).add_to(fmap)

    
        mc = MarkerCluster()
        mc.add_to(fmap)
        for p in result.get('pois', []):
            popup_html = f"<b>{p['name']}</b><br>{p['category']} — {p['price']} — {p['duration_hours']}h"
            folium.Marker(location=(p['lat'],p['lon']), popup=popup_html, tooltip=p['name']).add_to(mc)

        st_folium(fmap, width=900, height=500)

        # Export CSV
        csv_export = []
        for day in result.get('itinerary', []):
            for act in day['activities']:
                csv_export.append({
                    'day': day['day'],
                    'date': day['date'],
                    'name': act['name'],
                    'category': act['category'],
                    'duration_hours': act['duration_hours'],
                    'price': act['price']
                })
        if csv_export:
            df = pd.DataFrame(csv_export)
            st.download_button("Download itinerary CSV", df.to_csv(index=False).encode('utf-8'), file_name='itinerary.csv', mime='text/csv')

        st.success("Itinerary ready — enjoy your trip! ✈️")


with st.container():
    st.markdown("""
        <div style="
            background: rgba(255, 255, 255, 0.85);
            padding: 20px;
            border-radius: 12px;
            color: #000;
        ">
        <h4>Student travel tips (quick)</h4>
        <ul>
            <li>Book buses/trains early to grab student discounts.</li>
            <li>Carry a refillable bottle and small snacks to save money.</li>
            <li>Use local markets and street food for cheap, authentic meals.</li>
            <li>Travel light — hostel lockers + packable daypack save money.</li>
        </ul>
        <div style='opacity:0.9;'>Built with ❤️ for students — open-source, single-file demo.</div>
        </div>
    """, unsafe_allow_html=True)
