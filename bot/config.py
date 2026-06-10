import os
from dotenv import load_dotenv

load_dotenv()  # carga .env en el entorno
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")