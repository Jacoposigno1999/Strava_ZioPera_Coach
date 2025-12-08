from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class UserStats(BaseModel):
    user_id: str
    age: int
    avg_weekly_km: float
    recent_5k_time_min: float
    injury_status: str

class Workout(BaseModel):
    date: str
    workout_type: str = Field(..., description="e.g., 'Long Run', 'Intervals', 'Rest'")
    distance_km: float
    description: str
    target_pace: Optional[str]

class TrainingPlan(BaseModel):
    goal: str
    workouts: List[Workout]