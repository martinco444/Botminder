import os
from dotenv import load_dotenv

load_dotenv()  # carga .env en el entorno
TOKEN = os.getenv("TOKEN")