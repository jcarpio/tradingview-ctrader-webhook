# TradingView Webhook to cTrader Bridge

This project provides a secure webhook server for receiving alerts from TradingView and executing corresponding trading operations via the cTrader Open API. It includes logging and can run alongside other services using Nginx as a reverse proxy. The webhook is launched as a background systemd service for robustness.

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
- systemd (for service management)
- CSV for trade logging
- TradingView (Alert origin)

---

## 📁 Project Structure

```
/home/ubuntu/henry-webhook/
|│  henry-webhook.py         # Flask server that handles webhook requests
|│  requirements.txt       # Python dependencies
|├── env/              # Python virtual environment
|├── logs/             # Folder where trades are logged monthly in CSV files
|└── webhook-bot.service  # Optional reference systemd service file
```

---

## 🚀 Setup Instructions

### 1. Prepare the Python Environment

```bash
sudo apt update
sudo apt install python3-venv nginx
cd /home/ubuntu
python3 -m venv env
source env/bin/activate
pip install -r henry-webhook/requirements.txt
```

### 2. Create the Systemd Service

Create the following file:
```bash
sudo nano /etc/systemd/system/webhook-bot.service
```
Paste this content:
```ini
[Unit]
Description=Webhook Bot Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/henry-webhook
Environment="PATH=/home/ubuntu/env/bin"
ExecStart=/home/ubuntu/env/bin/python3 henry-webhook.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Then run:
```bash
sudo systemctl daemon-reload
sudo systemctl enable webhook-bot
sudo systemctl start webhook-bot
sudo systemctl status webhook-bot
```

### 3. Configure Nginx Reverse Proxy

Update `/etc/nginx/sites-available/default`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080; # Existing Prolog or web service
    }

    location /webhook {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Reload nginx:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Flask Development Mode Warning

Note: Flask prints a warning about being a development server. For production, you may later deploy this using `gunicorn` or `uwsgi`, but for now, `systemd` + `Flask` is sufficient.

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

**Note:** One alert can be created for BUY and another for SELL with different messages.

---

## 📅 Logging

- Trades are saved in CSV format inside the `logs/` directory.
- One file per month (e.g. `operations_2025-04.csv`)
- Includes timestamp, symbol, order type, volume, order ID

---

## ⚖️ Security

- Endpoint is protected by a secret token using Bearer authentication.
- Nginx proxy handles routing and isolates `/webhook` from other services.
- No credentials are hardcoded publicly.

---

## 🚫 Known Warnings

- `DeprecationWarning`: If `datetime.datetime.utcnow()` is deprecated in your Python version, replace it with:
```python
datetime.datetime.now(datetime.timezone.utc)
```

---

## 🙏 Credits

This project was born from the vision of simplifying and empowering peaceful, automated trading operations for people around the world ✨.
