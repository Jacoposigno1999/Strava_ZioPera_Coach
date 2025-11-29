import os, json, time
from pathlib import Path
from flask import Flask, request
from dotenv import load_dotenv
from stravalib import Client
import requests
import psycopg2
import datetime

load_dotenv()

CLIENT_ID = int(os.getenv("STRAVA_CLIENT_ID"))
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI", "http://127.0.0.1:5000/callback")
SCOPES = os.getenv("STRAVA_SCOPES", "read").split(",")

TOKENS_PATH = Path("strava_tokens.json")
API_BASE = "https://www.strava.com/api/v3"

app = Flask(__name__) #Creates the Flask app instance

# =================================================
# TOKENS
# =================================================

#Function to save tokens in a json file
def save_tokens(t: dict):
    # stravalib returns expires_at (epoch), access_token, refresh_token, athlete info
    TOKENS_PATH.write_text(json.dumps(t, indent=2))
    
    
    #Function to laod tokens from a json file
def load_tokens():
    return json.loads(TOKENS_PATH.read_text()) if TOKENS_PATH.exists() else None


#===================================
# Builds a stravalib.Client. If tokens are present and expired, stravalib can refresh them automatically 
# (since it knows your refresh token and expiry).
#===================================
def make_client():
    t = load_tokens() or {}
    return Client(
        access_token=t.get("access_token"),
        refresh_token=t.get("refresh_token"),
        token_expires=t.get("expires_at")
    )
    
# =================================================
# FLASK ROUTES (Only used for initial OAuth authorization)
# =================================================
@app.route("/")
def index():
    url = Client().authorization_url(
        client_id=CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES
    )
    return f"""
            <html>
            <body style="font-family:sans-serif">
                <h3>Strava OAuth</h3>
                <p><a href="{url}"><button>Connect Strava</button></a></p>
            </body>
            </html>
            """

#=====================
# Part the receive strava response
#=====================
@app.route("/callback")
def callback():
    if request.args.get("error"):
        return f"Error: {request.args['error']}", 400
    code = request.args.get("code") #Extracts the temporary authorization code from the URL.
    c = Client()
    token = c.exchange_code_for_token(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, code=code
    )
    save_tokens(token)
    return "<h3>Authorized!</h3><p>You can close this tab and re-run the script.</p>"


#==================
#This function lets you call Strava's API directly, bypassing stravalib.
#So you can see the real JSON Strava returns — the raw API response.
#==================
def raw_get(path, params=None):
    """Direct REST call to see the exact JSON Strava returns."""
    t = load_tokens()
    if not t: raise RuntimeError("No tokens yet.")
    headers = {"Authorization": f"Bearer {t['access_token']}"} #This is how API requests prove your identity.
    r = requests.get(f"{API_BASE}{path}", headers=headers, params=params or {}, timeout=30)
    print(f'r status: {r.status_code}')
    if r.status_code == 401:
        print('Token expired, refreshing...')
        # Refresh the token using stravalib
        c = Client()
        refreshed_token = c.refresh_access_token(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token=t['refresh_token']
        )
        # Save the new tokens
        save_tokens(refreshed_token)
        # Retry the request with new token
        headers = {"Authorization": f"Bearer {refreshed_token['access_token']}"}
        r = requests.get(f"{API_BASE}{path}", headers=headers, params=params or {}, timeout=30)

    r.raise_for_status()
    return r.json(), r

#=================================================
# DATABASE 
#=================================================


def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )
    return conn


def create_activities_table(conn):
    """Creates the table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                strava_id BIGINT PRIMARY KEY,
                name VARCHAR(255),
                activity_description TEXT,
                start_date_local TIMESTAMP,
                type VARCHAR(50),
                distance_m REAL,
                moving_time_s INTEGER,
                elapsed_time_s INTEGER,
                elevation_gain_m REAL,
                average_speed_mps REAL,
                max_speed_mps REAL,
                average_heartrate REAL,
                max_heartrate REAL
            );
        """)
    conn.commit()
    
    

def insert_one_activity(conn, act):
    """
    Parses and inserts a single Strava activity into the DB.
    Commits immediately for granular control.
    """
    try:
        # 1. Extract Data safely (handling None or Units)
        # Note: 'act.type' is often an object, we want the string key
        act_type = str(act.type) 
        
        description = str(act.description) if getattr(act, "description", None) else "No description"
        

        # Distances/elevation/speeds might be Quantities like "1000 m"
        
        dist = act.distance if getattr(act, "distance", None) else 0.0 
        elev = (
            act.total_elevation_gain
            if getattr(act, "total_elevation_gain", None)
            else 0.0
        )
        avg_spd = act.average_speed if getattr(act, "average_speed", None) else 0.0
        max_spd = act.max_speed if getattr(act, "max_speed", None) else 0.0

        # Timedeltas
        mov_time = (
            act.moving_time if getattr(act, "moving_time", None) else 0
        )
        ela_time = (
            act.elapsed_time if getattr(act, "elapsed_time", None) else 0
        )

        # Dates (strip timezone for simple Postgres TIMESTAMP)
        start_date = act.start_date_local.replace(tzinfo=None)

        # Heart rate (may be missing)
        avg_hr = getattr(act, "average_heartrate", None)
        max_hr = getattr(act, "max_heartrate", None)

        data = (
            act.id, act.name, description, start_date, act_type, 
            dist, mov_time, ela_time, elev, 
            avg_spd, max_spd, avg_hr, max_hr
        )

        # 2. Insert
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO activities (
                    strava_id, name, activity_description, start_date_local, type, distance_m,
                    moving_time_s, elapsed_time_s, elevation_gain_m,
                    average_speed_mps, max_speed_mps, average_heartrate, max_heartrate
                ) VALUES (%s, %s,  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (strava_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    distance_m = EXCLUDED.distance_m;
            """, data)
            # Note: I added "ON CONFLICT DO UPDATE" so if you re-run it, 
            # it updates the name/distance if they changed, rather than crashing.

        conn.commit()
        print(f"✅ Saved: {act.name} ({act.id})")

    except Exception as e:
        conn.rollback() #undo all changes since last commit 
        print(f"❌ Failed to save {act.id}: {e}")




if __name__ == "__main__":
    if not TOKENS_PATH.exists():
        print("Open http://127.0.0.1:5000 to authorize…")
        app.run("127.0.0.1", 5000, debug=False)
    else:
        print("\n--- 🏃 Starting Strava Pipeline ---")
        client = make_client()

        # 1) Who am I?
        me = client.get_athlete()
        print(f"👋 Athlete: {me.firstname} {me.lastname} — id={me.id}")

        # 2) Show 5 most recent activities (friendly summary from stravalib objects)
        acts = list(client.get_activities(limit=50))

        # 3) Raw JSON (exact API format) for the most recent activity
        if acts:
            first_id = acts[0].id
            detail_json, _ = raw_get(f"/activities/{first_id}", params={"include_all_efforts": "true"})
            #print("\n🧪 Raw JSON for the latest activity (first 1):")
            #print(json.dumps(detail_json, indent=2)[:4000])  # avoid flooding the console
        
        conn = get_db_connection()
        create_activities_table(conn)
            
        print("Writing to PostgreSQL...")
        for act in acts:
            insert_one_activity(conn, act) 
            
        if 'conn' in locals() and conn:
                conn.close()
                print("--- Pipeline Finished (Connection Closed) ---") 
        
            
            
            
