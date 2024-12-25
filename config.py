import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    CONTRACTS_DIR = os.path.join(BASE_DIR, 'contracts', 'samples')
    SECRET_KEY = 'dev-key-please-change-in-production'
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    FLASK_DEBUG = True
    