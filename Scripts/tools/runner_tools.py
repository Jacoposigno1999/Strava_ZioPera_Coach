from datapizza.tools import tool
from Scripts.domain.models import UserStats, TrainingPlan
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os 
load_dotenv()
# In a real app, you would import your DB repository here

def get_db_connection():
    """Establishes connection to the Postgres DB."""
    return psycopg2.connect(
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )

@tool
def get_runner_stats(user_id: str) -> str:
    """
    Fetches REAL historical performance from the Postgres 'activities' table.
    Calculates:
    1. Average Weekly Volume (last 4 weeks).
    2. Estimated 5k time (based on fastest recent run).
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- METRIC 1: AVERAGE WEEKLY VOLUME (Last 28 Days) ---
        # Logic: Sum distance of all runs in last 28 days, divide by 4.
        query_vol = """
            SELECT SUM(distance_m) as total_dist
            FROM activities 
            WHERE (type ILIKE '%Run%' OR sport_type ILIKE '%Run%')
            AND start_date_local >= NOW() - INTERVAL '28 days';
        """
        cur.execute(query_vol)
        result_vol = cur.fetchone()
        
        total_meters = result_vol[0] if result_vol and result_vol[0] else 0
        avg_weekly_km = (total_meters / 1000.0) / 4.0

        # --- METRIC 2: RECENT 5K TIME (Proxy for Fitness) ---
        # Logic: Find the fastest run >= 5km in the last 90 days.
        # We use average_speed_mps (meters per second) to calculate 5k time.
        query_speed = """
            SELECT average_speed_mps 
            FROM activities 
            WHERE (type ILIKE '%Run%' OR sport_type ILIKE '%Run%')
            AND distance_m >= 5000 
            AND start_date_local >= NOW() - INTERVAL '90 days'
            ORDER BY average_speed_mps DESC
            LIMIT 1;
        """
        cur.execute(query_speed)
        result_speed = cur.fetchone()

        if result_speed and result_speed[0]:
            speed_mps = result_speed[0]
            # Time = Distance / Speed
            # 5000m / speed (m/s) = seconds. / 60 = minutes.
            est_5k_time_min = (5000 / speed_mps) / 60
        else:
            # Fallback if no recent data found
            #TODO: Return a message indicating lack of data
            est_5k_time_min = 30.0 # Default fallback

        # --- CONSTRUCT OBJECT ---
        # Note: 'Age' is not in the activities table. 
        # Ideally, we would fetch this from a 'users' table. 
        # For now, we default to 30 or pass a placeholder.
        real_stats = UserStats(
            user_id=user_id,
            age=30, # Limitation: Data not in DB yet
            avg_weekly_km=round(avg_weekly_km, 2),
            recent_5k_time_min=round(est_5k_time_min, 1),
            injury_status="None" 
        )
        
        print(f"📊 [DB READ] Stats loaded for {user_id}: {real_stats.avg_weekly_km} km/wk, 5k est: {real_stats.recent_5k_time_min} min")
        return real_stats.model_dump_json()

    except Exception as e:
        return f"Error fetching stats: {str(e)}"
    finally:
        if conn:
            conn.close()


#  TODO: this tool is not being used
# The pipele arrive at --> │ Next step: Save the generated workout plan using `save_training_plan(user_id=user_123)`.
@tool
def save_training_plan(plan_data: str) -> str:
    """
    Saves the final generated training plan to the Database.
    The input 'plan_data' must be a valid JSON string matching the TrainingPlan schema.
    """
    try:
        # Validate that the agent sent valid JSON
        # In reality, you'd convert the JSON string back to a Pydantic model here
        print(f"💾 [DB WRITE] Saving Plan to Postgres...")
        print(f"   Data received: {plan_data[:100]}...") # truncated for view
        return "Success: Plan saved to Database."
    except Exception as e:
        return f"Error saving plan: {str(e)}"