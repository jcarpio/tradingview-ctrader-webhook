import os
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# Endpoint de renovación de token
TOKEN_URL = "https://oauth.ctrader.com/token"

def refresh_access_token():
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    try:
        response = requests.post(TOKEN_URL, data=data)
        response.raise_for_status()
        tokens = response.json()

        print("\n✅ Nuevo access_token generado:")
        print(tokens['access_token'])

        print("\n🔁 Nuevo refresh_token (si ha cambiado):")
        print(tokens['refresh_token'])

        return tokens

    except requests.exceptions.RequestException as e:
        print("❌ Error al renovar el token:", e)
        print(response.text)
        return None

if __name__ == "__main__":
    refresh_access_token()
