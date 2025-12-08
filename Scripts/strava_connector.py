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
        cur.execute(    """
            CREATE TABLE IF NOT EXISTS activities (
                strava_id BIGINT PRIMARY KEY,

                -- 📌 1. Informazioni generali
                name VARCHAR(255),
                activity_description TEXT,
                type VARCHAR(50),
                sport_type VARCHAR(50),
                workout_type INTEGER,
                timezone VARCHAR(100),
                start_date_local TIMESTAMP,

                -- 📌 2. Durate e distanze
                distance_m REAL,
                moving_time_s INTEGER,
                elapsed_time_s INTEGER,
                elevation_gain_m REAL,
                elev_high_m REAL,
                elev_low_m REAL,

                -- 📌 4. Velocità, potenza, cadenza
                average_speed_mps REAL,
                max_speed_mps REAL,
                average_cadence REAL,

                -- 📌 5. Frequenza cardiaca
                has_heartrate BOOLEAN,
                average_heartrate REAL,
                max_heartrate REAL,
                heartrate_opt_out BOOLEAN,
                display_hide_heartrate_option BOOLEAN,

                -- 📌 6. Calorie & Parametri fisiologici
                calories REAL,
                average_temp REAL,
                max_temperature REAL,
                suffer_score REAL
            );
        """)
    conn.commit()
    
    

def insert_one_activity(conn, act):
    """
    Parses and inserts a single Strava activity into the DB.
    Commits immediately for granular control.
    """
    try:
        # ---------- 1) Informazioni generali ----------
        act_type = str(act.type) if getattr(act, "type", None) else None
        sport_type = str(act.sport_type) if getattr(act, "sport_type", None) else None
        workout_type = getattr(act, "workout_type", None)
        timezone = getattr(act, "timezone", None)

        description = (
            str(act.description) if getattr(act, "description", None) else "No description"
        )

        # start_date_local senza timezone (per TIMESTAMP "naive" in Postgres)
        if getattr(act, "start_date_local", None):
            start_date = act.start_date_local.replace(tzinfo=None)
        else:
            start_date = None

        # ---------- 2) Durate e distanze ----------
        # stravalib spesso usa oggetti Quantity; cast a float in metri
        dist = float(act.distance) if getattr(act, "distance", None) else 0.0
        elev_gain = (
            float(act.total_elevation_gain)
            if getattr(act, "total_elevation_gain", None)
            else 0.0
        )
        elev_high = float(act.elev_high) if getattr(act, "elev_high", None) else None
        elev_low = float(act.elev_low) if getattr(act, "elev_low", None) else None

        # moving_time / elapsed_time sono timedelta → convertiamo in secondi
        mov_time = (
            act.moving_time if getattr(act, "moving_time", None) else 0
        )
        ela_time = (
            act.elapsed_time if getattr(act, "elapsed_time", None) else 0
        )

        # ---------- 4) Velocità, potenza, cadenza ----------
        avg_spd = (
            float(act.average_speed)
            if getattr(act, "average_speed", None)
            else None
        )
        max_spd = float(act.max_speed) if getattr(act, "max_speed", None) else None
        avg_cad = (
            float(act.average_cadence)
            if getattr(act, "average_cadence", None)
            else None
        )

        # ---------- 5) Frequenza cardiaca ----------
        has_hr = getattr(act, "has_heartrate", None)
        avg_hr = getattr(act, "average_heartrate", None)
        max_hr = getattr(act, "max_heartrate", None)
        hr_opt_out = getattr(act, "heartrate_opt_out", None)
        hide_hr_opt = getattr(act, "display_hide_heartrate_option", None)

        # ---------- 6) Calorie & Parametri fisiologici ----------
        calories = getattr(act, "calories", None)
        avg_temp = getattr(act, "average_temp", None)
        max_temp = getattr(act, "max_temperature", None)
        suffer_score = getattr(act, "suffer_score", None)

        data = (
            act.id,           # strava_id
            act.name,         # name
            description,      # activity_description
            act_type,         # type
            sport_type,       # sport_type
            workout_type,     # workout_type
            timezone,         # timezone
            start_date,       # start_date_local

            dist,             # distance_m
            mov_time,         # moving_time_s
            ela_time,         # elapsed_time_s
            elev_gain,        # elevation_gain_m
            elev_high,        # elev_high_m
            elev_low,         # elev_low_m

            avg_spd,          # average_speed_mps
            max_spd,          # max_speed_mps
            avg_cad,          # average_cadence

            has_hr,           # has_heartrate
            avg_hr,           # average_heartrate
            max_hr,           # max_heartrate
            hr_opt_out,       # heartrate_opt_out
            hide_hr_opt,      # display_hide_heartrate_option

            calories,         # calories
            avg_temp,         # average_temp
            max_temp,         # max_temperature
            suffer_score      # suffer_score
        )

        # 2. Insert
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO activities (
                    strava_id,
                    name,
                    activity_description,
                    type,
                    sport_type,
                    workout_type,
                    timezone,
                    start_date_local,
                    distance_m,
                    moving_time_s,
                    elapsed_time_s,
                    elevation_gain_m,
                    elev_high_m,
                    elev_low_m,
                    average_speed_mps,
                    max_speed_mps,
                    average_cadence,
                    has_heartrate,
                    average_heartrate,
                    max_heartrate,
                    heartrate_opt_out,
                    display_hide_heartrate_option,
                    calories,
                    average_temp,
                    max_temperature,
                    suffer_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (strava_id) DO UPDATE SET
                    name                         = EXCLUDED.name,
                    activity_description          = EXCLUDED.activity_description,
                    type                          = EXCLUDED.type,
                    sport_type                    = EXCLUDED.sport_type,
                    workout_type                  = EXCLUDED.workout_type,
                    timezone                      = EXCLUDED.timezone,
                    start_date_local              = EXCLUDED.start_date_local,
                    distance_m                    = EXCLUDED.distance_m,
                    moving_time_s                 = EXCLUDED.moving_time_s,
                    elapsed_time_s                = EXCLUDED.elapsed_time_s,
                    elevation_gain_m              = EXCLUDED.elevation_gain_m,
                    elev_high_m                   = EXCLUDED.elev_high_m,
                    elev_low_m                    = EXCLUDED.elev_low_m,
                    average_speed_mps             = EXCLUDED.average_speed_mps,
                    max_speed_mps                 = EXCLUDED.max_speed_mps,
                    average_cadence               = EXCLUDED.average_cadence,
                    has_heartrate                 = EXCLUDED.has_heartrate,
                    average_heartrate             = EXCLUDED.average_heartrate,
                    max_heartrate                 = EXCLUDED.max_heartrate,
                    heartrate_opt_out             = EXCLUDED.heartrate_opt_out,
                    display_hide_heartrate_option = EXCLUDED.display_hide_heartrate_option,
                    calories                      = EXCLUDED.calories,
                    average_temp                  = EXCLUDED.average_temp,
                    max_temperature               = EXCLUDED.max_temperature,
                    suffer_score                  = EXCLUDED.suffer_score;
                """,
                data,)
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
            import json 
            with open('detail_json.json', "w") as f:
                json.dump(detail_json, f)
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
        
            
            
            
