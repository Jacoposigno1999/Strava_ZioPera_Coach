import os
from datapizza.agents import Agent
from datapizza.clients.openai import OpenAIClient # Or Azure, Anthropic
from datapizza.clients.openai_like import OpenAILikeClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Scripts.tools.runner_tools import get_runner_stats, save_training_plan
from datapizza.clients.google import GoogleClient



api_key = os.getenv("GEMINI_API_KEY")


#TODO: Replace llama with GEMINI free
client = GoogleClient(
    api_key= api_key,
    model = "gemini-flash-latest",
    system_prompt="You are an helpful assitant"
)

'''
client = OpenAILikeClient(
    api_key= "",
    model = "llama3.1:8b",
    system_prompt="You are an helpful assitant",
    base_url="http://localhost:11434/v1"
)
'''

# 2. Define the "System Prompt" (The Personality & Rules)
SYS_PROMPT = """
You are a Function Calling Engine. You are NOT a Chatbot.
Your only purpose is to trigger tools based on user requests.

### YOUR INSTRUCTIONS
1. Call `get_runner_stats(user_id)` to check the user's fitness.
2. Based on the stats, GENERATE a JSON training plan in your memory.
3. Call `save_training_plan(plan_data)` with that JSON.

### STRICT FORMATTING RULES
- **DO NOT** write Python code.
- **DO NOT** write explanations.
- **ONLY** output the tool calls.
- **EXCEPTION:** If you have successfully saved the plan and received the success message, you **MUST** output a final text confirmation to the user (e.g., "Plan created successfully").

### EXAMPLE OF SUCCESS (Mimic This!)
User: "Create a plan for user_123."
Assistant:
Tool Call: get_runner_stats(user_id="user_123")
... (Tool returns stats) ...
Tool Call: save_training_plan(plan_data='{"user_id": "user_123", 
                                          "goal_description": "10k in 45m", 
                                          "workouts": [{"date": "2025-01-01", "distance_km": 5.0}]}')

### NOW PROCESS THIS REQUEST:
"""

# 3. Initialize the Agent
agent_1 = Agent(
    name="ZioPera_Architect",
    client=client,
    system_prompt=SYS_PROMPT,
    tools=[get_runner_stats, save_training_plan], # Register the tools
   
)

def run_planner_pipeline(user_request: str, user_id: str):
    """
    The entry point for our backend API.
    """
    print(f"🤖 Agent 1 Active. Processing: {user_request}")
    
    # We inject the user_id into the prompt context so the agent knows who to look up
    full_prompt = f"User ID: {user_id}. Request: {user_request}"
    
    response = agent_1.run(full_prompt)
    
    print("✅ Pipeline Finished.")
    return response

# --- TEST RUN ---
if __name__ == "__main__":
    # Simulating the User Input from your sketch
    user_input = "Create a plan to run 10km in 45 minutes. The run will be 10/03/2026."
    
    run_planner_pipeline(user_input, user_id="user_123")