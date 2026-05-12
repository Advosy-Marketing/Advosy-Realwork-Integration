import os
from dotenv import load_dotenv

load_dotenv()

ENCIRCLE_TOKEN = os.environ["ENCIRCLE_TOKEN"]
COMPANYCAM_TOKEN = os.environ["COMPANYCAM_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
SUPABASE_DB_URL = os.environ["SUPABASE_DB_URL"]
COMPANYCAM_PROJECT_LABEL = os.environ.get("COMPANYCAM_PROJECT_LABEL", "Bloque Project From Encircle")

ENCIRCLE_BASE = "https://api.encircleapp.com"
COMPANYCAM_BASE = "https://api.companycam.com/v2"
