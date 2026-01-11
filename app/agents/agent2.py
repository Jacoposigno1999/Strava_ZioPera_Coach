import os
from datapizza.agents import Agent
from datapizza.clients.openai import OpenAIClient # Or Azure, Anthropic
from datapizza.clients.openai_like import OpenAILikeClient
from datapizza.clients.google import GoogleClient
import sys

from app.tools.agent2_tools import compare_plan_vs_actual, update_training_plan
from app.config import Config


client = GoogleClient(
    api_key= Config.GEMINI_API_KEY,
    model = Config.MODEL_NAME,
    system_prompt="You are an expert running coach managing an athlete's progress."
)


# The System Prompt for the Coach
COACH_SYS_PROMPT = """
You are "Coach ZioPera", an expert running coach managing an athlete's progress.
Your goal is to KEEP THE PLAN REALISTIC based on actual performance.

### YOUR PROCESS
1. Receive a `user_id` and a `check_date` (usually yesterday).
2. Call `compare_plan_vs_actual(user_id, date)`.
3. ANALYZE the result:
   - If `compliance_percent` > 50%: DO NOTHING. Praise the user.
   - If `compliance_percent` < 50% (Missed Run): You MUST reschedule.
     - Move the missed key run to a later date?
     - Reduce volume for the rest of the week?
4. IF rescheduling is needed:
   - Generate a JSON list of NEW workouts starting from tomorrow.
   - Call `update_training_plan(plan_id, new_workouts_json)`.
   - Output a text explanation to the user (e.g., "I noticed you missed yesterday's run, so I shifted your long run to Sunday.").

### CRITICAL RULES
- Be empathetic but firm.
- Only reschedule if the deviation is significant.
- Always output the final text message to the user.
"""

agent_coach = Agent(
    name="ZioPera_Coach",
    client=client, 
    system_prompt=COACH_SYS_PROMPT,
    tools=[compare_plan_vs_actual, update_training_plan]
)


if __name__ == "__main__":
    # Simulate a daily check
    # Imagine User 123 missed their run yesterday (2025-01-01)
    
    date_to_check = "2026-01-01" 
    
    print(f"🕵️ Coach checking status for {date_to_check}...")
    
    prompt = f"Check my progress for {date_to_check} and adjust if necessary. User: user_123"
    
    agent_coach.run(prompt)