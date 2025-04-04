# TradingView Webhook to cTrader Bridge

This project provides a secure webhook server for receiving alerts from TradingView and executing corresponding trading operations via the cTrader Open API. It includes logging and can run alongside other services using Nginx as a reverse proxy.

---

## ✨ Project Overview

This application acts as a bridge between TradingView alerts and cTrader trading accounts. It allows for automated trading strategies triggered by alerts on TradingView. The webhook server receives alert payloads, validates them using a shared secret, and executes market orders in a cTrader account.

---

## 🔧 Tech Stack

- Python 3.12+
- Flask (Webhook server)
- Nginx (Reverse proxy)
- cTrader Open API (via Spotware)
- AWS EC2 (Hosting)
- CSV for trade logging
- TradingView (Alert origin)

---

## 📁 Project Structure

```
project-root/
|│  webhook_bot.py           # Flask server that handles webhook requests
|│  requirements.txt         # Python dependencies
|├── logs/                # Folder where trades are logged monthly in CSV files
|└── nginx config        # Instructions to add reverse proxy
```

---

## 🚀 Setup Instructions

### 1. Prepare your environment

```bash
sudo apt update
sudo apt install python3-venv nginx
python3 -m venv env
source env/bin/activate
pip install flask
```

### 2. Configure Nginx reverse proxy

Update `/etc/nginx/sites-available/default`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080; # Your existing Prolog server
    }

    location /webhook {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Then reload:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Set your environment variables or update the Python file

In `webhook_bot.py`, configure:

```python
SECRET_TOKEN = "your_generated_secret"
client_id = "your_ctrader_client_id"
client_secret = "your_ctrader_client_secret"
access_token = "your_access_token"
account_id = "your_trading_account_id"
```

### 4. Run the Flask webhook

```bash
python webhook_bot.py
```

It listens at `http://localhost:5001/webhook`.

---

## 🌐 TradingView Webhook Configuration

**Webhook URL:**
```
http://your-domain.com/webhook
```

**Alert Body (JSON):**
```json
{
  "symbol": "US 30",
  "order": "BUY",
  "volume": 1
}
```

**Headers:**
```
Authorization: Bearer your_generated_secret
```

---

## 📅 Logging

- Trades are saved in CSV format inside the `logs/` directory.
- One file per month (e.g. `operations_2024-04.csv`)
- Includes timestamp, symbol, order type, volume, order ID

---

## ⚖️ Security

- Endpoint is protected by a secret token using Bearer authentication.
- Nginx proxy handles routing and isolates `/webhook` from other services.

---

## ⚡ Future Improvements

- Integrate cTrader authentication refresh tokens
- Add retry/failure handling logic
- Unit and integration tests
- Optional Telegram notifications

---

## 🙏 Credits

This project was born from the vision of simplifying and empowering peaceful, automated trading operations for people around the world ✨.

