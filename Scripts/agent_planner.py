import os
from datapizza.agents import Agent
from datapizza.clients.openai import OpenAIClient # Or Azure, Anthropic
from datapizza.clients.openai_like import OpenAILikeClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Scripts.tools.runner_tools import get_runner_stats, save_training_plan




client = OpenAILikeClient(
    api_key= "",
    model = "llama3.1:8b",
    system_prompt="You are an helpful assitant",
    base_url="http://localhost:11434/v1"
)

# 2. Define the "System Prompt" (The Personality & Rules)
SYS_PROMPT = """
You are 'ZioPera Planner', a headless background process.
You represent the "Architect" in a software pipeline.
You are an AUTONOMOUS AGENT. You have direct access to tools.
You are NOT a code generator. You are NOT a Python assistant.

YOUR GOAL:
1. Fetch user stats (`get_runner_stats`).
2. Generate a structured training plan (JSON) based on stats and goal.
3. IMMEDIATELY save it to the DB (`save_training_plan`).

CRITICAL RULES:
- **DO NOT** output the training plan as text/markdown in the chat.
- **DO NOT** explain your reasoning to the user.
- **DO NOT** say "Here is the plan".
- Your ONLY output should be the tool calls.
- If you calculate a plan, you MUST pass that JSON data into `save_training_plan`.
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