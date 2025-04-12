import os
import csv
import datetime
from flask import Flask, request, jsonify
from ctrader import CTrader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Loaded token:", os.getenv("SECRET_TOKEN"))

SECRET_TOKEN = os.getenv("SECRET_TOKEN")
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = os.getenv("CTRADER_ACCOUNT_ID")


# Initialize cTrader client
ctrader = CTrader(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, access_token=ACCESS_TOKEN)

app = Flask(__name__)

# Ensure logs folder exists
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

@app.route("/webhook", methods=["POST"])
def webhook():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth.split(" ")[1] != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    symbol = data.get("symbol")
    order_type = data.get("order")
    volume = data.get("volume")

    if not all([symbol, order_type, volume]):
        return jsonify({"error": "Invalid payload"}), 400

    try:
        # Execute order
        if order_type.upper() == "BUY":
            response = ctrader.place_market_order(ACCOUNT_ID, symbol, "buy", volume)
        elif order_type.upper() == "SELL":
            response = ctrader.place_market_order(ACCOUNT_ID, symbol, "sell", volume)
        else:
            return jsonify({"error": "Unknown order type"}), 400

        # Log the operation
        now = datetime.datetime.now(datetime.timezone.utc)
        log_filename = f"{LOGS_DIR}/operations_{now.strftime('%Y-%m')}.csv"
        with open(log_filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                now.isoformat(),
                symbol,
                order_type.upper(),
                volume,
                response.get("order_id", "N/A")
            ])

        return jsonify({"status": "success", "order": response}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
