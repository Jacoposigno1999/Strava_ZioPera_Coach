from datapizza.tools import tool
from Scripts.domain.models import UserStats, TrainingPlan
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os 
load_dotenv()
import json 


# TODO: Move DB connection logic to a shared utils file
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
def compare_plan_vs_actual(user_id: str, date: str) -> str:
    """
    Compares the planned workout vs actual activity for a specific date (YYYY-MM-DD).
    Returns a summary of compliance (e.g., "Planned 5k, Ran 0k").
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)#dovrei RealDictCursor sembra piu comodo per prendere i valori con i nomi delle colonne
    try:
        # 1. Get the PLAN for that day
        # TODO Better handling if multiple plans exist
        cur.execute("""
            SELECT plan_id, distance_km, target_pace_min_per_km, description
            FROM workouts 
            WHERE user_id = %s AND scheduled_date = %s
        """, (user_id, date))
        planned = cur.fetchone()
        
        print(f'planned workout found: {planned}')

        if not planned:
            return "No workout was scheduled for this date."

        # 2. Get the ACTUAL (Sum of runs on that day)
        # Note: We sum strictly based on date. Strava dates can be tricky with timezones!
        cur.execute("""
            SELECT SUM(distance_m) / 1000.0 as total_km, 
                   AVG(average_speed_mps) as avg_speed
            FROM activities 
            WHERE type ILIKE '%%Run%%' 
            AND start_date_local::date = %s 
        """, (date,))
        actual = cur.fetchone()
        
        print(f'actual activity found: {actual}')
        
        actual_km = actual['total_km'] if actual and actual['total_km'] else 0.0
        
        # 3. Calculate Compliance
        # Simple logic: Did they do at least 80% of the distance?
        compliance_score = (actual_km / planned['distance_km']) * 100
        
        status = {
            "date": date,
            "plan_id": planned['plan_id'],
            "planned_km": planned['distance_km'],
            "actual_km": round(actual_km, 2),
            "compliance_percent": round(compliance_score, 1),
            "verdict": "Missed" if compliance_score < 50 else "Good"
        }
        
        return json.dumps(status)

    except Exception as e:
        return f"Agent_2: Error comparing data: {str(e)}"
    finally:
        conn.close()
        
        
        
@tool
def update_training_plan(plan_id: int, new_workouts_json: str) -> str:
    """
    Updates the FUTURE workouts for an existing plan.
    Input 'new_workouts_json' must be a list of workout objects.
    WARNING: This deletes all existing workouts for this plan from the start date of the new list onwards.
    """
    conn = None
    try:
        data = json.loads(new_workouts_json) # List of dicts
        if not data: return "No workouts provided."

        # Sort to find the "Cutoff Date" (The first date we are changing)
        sorted_workouts = sorted(data, key=lambda x: x['date'])
        cutoff_date = sorted_workouts[0]['date']
        
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. DELETE old future workouts (Clean the slate)
        # We don't touch the past! Only change the future.
        cur.execute("""
            DELETE FROM workouts 
            WHERE plan_id = %s AND scheduled_date >= %s
        """, (plan_id, cutoff_date))
        
        deleted_count = cur.rowcount

        # 2. INSERT new workouts
        workout_tuples = []
        for w in sorted_workouts:
            workout_tuples.append((
                plan_id,
                # We need user_id... typically we'd fetch it from the plan_id, 
                # but let's assume the LLM passes it or we query it. 
                # For simplicity, let's query the user_id from the plan first:
                w.get('date'),
                w.get('type', 'Run'),
                float(w.get('distance_km', 0)),
                w.get('pace', ''), 
                w.get('description', '')
            ))
            
        # Helper: Fetch user_id for this plan --> TODO Optimize
        cur.execute("SELECT user_id FROM training_plans WHERE plan_id = %s", (plan_id,))
        user_row = cur.fetchone()
        if not user_row: raise Exception("Plan ID not found")
        user_id = user_row[0]

        # Re-build tuples with user_id
        final_tuples = [(t[0], user_id, *t[1:]) for t in workout_tuples]

        cur.executemany("""
            INSERT INTO workouts 
            (plan_id, user_id, scheduled_date, workout_type, distance_km, target_pace_min_per_km, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, final_tuples)

        conn.commit()
        return f"Updated Plan {plan_id}: Deleted {deleted_count} old workouts, added {len(final_tuples)} new ones starting from {cutoff_date}."

    except Exception as e:
        if conn: conn.rollback()
        return f"Update failed: {e}"
    finally:
        if conn: conn.close()