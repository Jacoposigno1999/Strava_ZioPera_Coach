import os
from dotenv import load_dotenv

# This tells Python to look for the .env file in the folder ABOVE this one (the root)
# structure: Strava_Assistant/.env
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

class Config:
    """
    Central source for all environment variables.
    """
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Database Settings
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")

    # Agent Settings - Pinned version for stability
    MODEL_NAME = "gemini-flash-latest"

    @classmethod
    def validate(cls):
        """Checks if critical keys are missing and warns the user."""
        if not cls.GEMINI_API_KEY:
            raise ValueError("❌ CRITICAL ERROR: GEMINI_API_KEY is missing from .env file!")
        
        if not cls.POSTGRES_PASSWORD:
            print("⚠️ Warning: POSTGRES_PASSWORD is empty or missing.")

# Run validation immediately when this file is imported
Config.validate()