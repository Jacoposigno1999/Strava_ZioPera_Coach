from datapizza.tools import tool
from Scripts.domain.models import UserStats, TrainingPlan
# In a real app, you would import your DB repository here

@tool
def get_runner_stats(user_id: str) -> str:
    """
    Fetches the historical performance and stats of the runner from the DB.
    Use this BEFORE creating a plan to understand the user's fitness.
    """
    # MOCK DB CALL - In production, this queries Postgres
    # Simulating a user who runs 10k in 55 mins currently
    mock_stats = UserStats(
        user_id=user_id,
        age=30,
        avg_weekly_km=25.0,
        recent_5k_time_min=26.5,
        injury_status="None"
    )
    return mock_stats.model_dump_json()

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