# 📡 TradingView to cTrader Webhook – Full Integration Guide

This project creates a **secure bridge** between TradingView alerts and real-time market orders on **cTrader**, using the official Spotware **Open API** (Protobuf + Twisted).

Perfect for automated strategies triggered by TradingView signals.

---

## ⚙️ Architecture Overview

```
[TradingView Alert] → [Flask Webhook Server] → [cTrader Open API (TCP/Protobuf)] → [Live or Demo Account]
                             │
                             └── Logs each trade in monthly CSV files
```

---

## 🧱 Requirements

- Python 3.12+
- [`ctrader-open-api`](https://github.com/spotware/OpenApiPy) (official Spotware library)
- `Flask`
- `Twisted`
- `python-dotenv`
- Valid cTrader App credentials (Client ID & Secret)
- Access Token (manually or via OAuth2)
- Server (AWS EC2, VPS, etc.) to host the webhook

---

## 🚀 Detailed Setup Instructions

### 1. Create a cTrader Application

1. Go to [Connect cTrader Developer Portal](https://connect.spotware.com/apps)
2. Register/Login and create a new application
3. Set the following:
   - **App Type**: Standard Application
   - **Redirect URLs**: Add your server URL (e.g., `http://your-server-ip/webhook`)
   - **Permissions**: Check "Trading" (essential) and "Data"
4. Once created, note your:
   - **App ID**: Usually in format like `12345_AbCdEfGhIjK...`
   - **App Secret**

### 2. Get Access Token

1. In the cTrader desktop application, go to:
   - **Settings** → **Tools** → **Open API**
2. Click "New API token" and select your application
3. Grant the required permissions (trading)
4. Copy the generated **Access Token**

### 3. Server Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv git

# Clone the repository (or create a directory for the project)
git clone https://github.com/yourusername/tradingview-ctrader.git
# Or: mkdir -p tradingview-ctrader

# Navigate to the project directory
cd tradingview-ctrader

# Create a virtual environment
python3 -m venv env

# Activate the virtual environment
source env/bin/activate

# Install dependencies
pip install flask twisted python-dotenv ctrader-open-api
```

### 4. Create Project Files

#### Create .env file

```bash
nano .env
```

Add the following content:

```
SECRET_TOKEN=your_secure_random_token
CTRADER_CLIENT_ID=your_app_id
CTRADER_CLIENT_SECRET=your_app_secret
CTRADER_ACCESS_TOKEN=your_access_token
ACCOUNT_ID=your_account_id
```

> **IMPORTANT**: Replace `your_account_id` with the actual cTrader account ID, not the trading account login number.

#### Create ctrader.py file

```bash
nano ctrader.py
```

Copy the [provided ctrader.py code](#) into this file.

#### Create webhook.py file

```bash
nano webhook.py
```

Copy the [provided webhook.py code](#) into this file.

### 5. Find Your Account ID and Symbol IDs

We need to use the correct account ID and symbol IDs for orders to work properly.

#### Find Account ID

```bash
# Create a script to list available accounts
nano list_accounts.py
```

Copy the following code:

```python
import os
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# ⚙️ Configuration
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")

print("=== Listing accounts available for this token ===")
print(f"CLIENT_ID: {CLIENT_ID}")
print("=====================================")

client = None
list_completed = defer.Deferred()

def on_connected(client_instance):
    print("[TEST] ✅ Connected to server")
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_error)

def on_app_auth_success(response):
    print("[TEST] ✅ Application authenticated")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetAccountListByAccessTokenReq
    request = ProtoOAGetAccountListByAccessTokenReq()
    request.accessToken = ACCESS_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_list_success)
    deferred.addErrback(on_error)

def on_account_list_success(response):
    from ctrader_open_api import Protobuf
    
    try:
        account_list = Protobuf.extract(response)
        print("\n[TEST] ✅ Account list received")
        print("\n=== AVAILABLE ACCOUNTS ===")
        
        if hasattr(account_list, 'ctidTraderAccount') and len(account_list.ctidTraderAccount) > 0:
            for account in account_list.ctidTraderAccount:
                print(f"ID: {account.ctidTraderAccountId}")
                print(f"  - Login: {account.traderLogin}")
                print(f"  - Is Live: {account.isLive}")
                print("-------------------")
        else:
            print("❌ No accounts found for this access token")
            
        print("===========================\n")
    except Exception as e:
        print(f"[TEST] ❌ Error processing account list: {e}")
    
    list_completed.callback(None)

def on_error(failure):
    print(f"[TEST] ❌ Error: {failure}")
    
    if not list_completed.called:
        list_completed.errback(failure)
    
    return failure

def shutdown_test(result=None):
    print("[TEST] Test completed, closing connection...")
    
    if client:
        client.stopService()
    
    reactor.callLater(1, reactor.stop)

# Initialize client
client = Client(
    EndPoints.PROTOBUF_DEMO_HOST, 
    EndPoints.PROTOBUF_PORT, 
    TcpProtocol
)

# Set callbacks
client.setConnectedCallback(on_connected)

# Set timeout
def on_timeout():
    if not list_completed.called:
        print("[TEST] ⚠️ Connection timeout!")
        list_completed.errback(Exception("Connection timeout"))

reactor.callLater(30, on_timeout)

# Add shutdown callback
list_completed.addBoth(shutdown_test)

# Start client
print("[TEST] Starting connection...")
client.startService()

# Run reactor
reactor.run()
```

Run the script and note the correct account ID:

```bash
python list_accounts.py
```

You will see output like:
```
ID: 42530173  # This is your Account ID
  - Login: 5084766  # This is your Login (not the same as Account ID)
```

Use the ID value (e.g., 42530173) in your .env file.

#### Find Symbol IDs

```bash
# Create a script to list available symbols
nano list_symbols.py
```

Copy the following code:

```python
import os
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# ⚙️ Configuration
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))

print("=== Getting symbols list for account ===")
print(f"ACCOUNT_ID: {ACCOUNT_ID}")
print("=====================================")

client = None
symbols_completed = defer.Deferred()

def on_connected(client_instance):
    print("[TEST] ✅ Connected to server")
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_error)

def on_app_auth_success(response):
    print("[TEST] ✅ Application authenticated")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_error)

def on_account_auth_success(response):
    print(f"[TEST] ✅ Account {ACCOUNT_ID} authenticated")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolsListReq
    request = ProtoOASymbolsListReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    
    deferred = client.send(request)
    deferred.addCallback(on_symbols_received)
    deferred.addErrback(on_error)

def on_symbols_received(response):
    from ctrader_open_api import Protobuf
    
    try:
        symbols = Protobuf.extract(response)
        print("\n[TEST] ✅ Symbol list received")
        print("\n=== AVAILABLE SYMBOLS ===")
        
        common_symbols = {
            "BTCUSD": None,
            "ETHUSD": None,
            "EURUSD": None,
            "XAUUSD": None
        }
        
        if hasattr(symbols, 'symbol') and len(symbols.symbol) > 0:
            print(f"Total symbols: {len(symbols.symbol)}")
            
            for symbol in symbols.symbol:
                name = symbol.symbolName
                symbol_id = symbol.symbolId
                
                if name in common_symbols:
                    common_symbols[name] = symbol_id
                    print(f"ID: {symbol_id} - Name: {name}")
            
            print("\n--- COMMON SYMBOLS FOUND ---")
            for name, symbol_id in common_symbols.items():
                if symbol_id:
                    print(f"  \"{name}\": {symbol_id},")
                else:
                    print(f"  \"{name}\": Not found,")
                    
        else:
            print("❌ No symbols found for this account")
            
        print("===========================\n")
        
    except Exception as e:
        print(f"[TEST] ❌ Error processing symbols: {e}")
    
    symbols_completed.callback(None)

def on_error(failure):
    print(f"[TEST] ❌ Error: {failure}")
    
    if not symbols_completed.called:
        symbols_completed.errback(failure)
    
    return failure

def shutdown_test(result=None):
    print("[TEST] Test completed, closing connection...")
    
    if client:
        client.stopService()
    
    reactor.callLater(1, reactor.stop)

# Initialize client
client = Client(
    EndPoints.PROTOBUF_DEMO_HOST, 
    EndPoints.PROTOBUF_PORT, 
    TcpProtocol
)

# Set callbacks
client.setConnectedCallback(on_connected)

# Set timeout
def on_timeout():
    if not symbols_completed.called:
        print("[TEST] ⚠️ Connection timeout!")
        symbols_completed.errback(Exception("Connection timeout"))

reactor.callLater(30, on_timeout)

# Add shutdown callback
symbols_completed.addBoth(shutdown_test)

# Start client
print("[TEST] Starting connection...")
client.startService()

# Run reactor
reactor.run()
```

Run the script to get the correct symbol IDs:

```bash
python list_symbols.py
```

You'll see output like:
```
--- COMMON SYMBOLS FOUND ---
  "BTCUSD": 22395,
  "ETHUSD": 22397,
  "EURUSD": 1,
  "XAUUSD": 41,
```

Update the `SYMBOLS` dictionary in ctrader.py with these values.

### 6. Run the Webhook Server

```bash
python webhook.py
```

Your server will start on port 5001. To test it, you can use a tool like curl:

```bash
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD", "order":"BUY", "volume":0.01, "token":"your_secure_random_token"}'
```

### 7. Set Up TradingView Alerts

1. In TradingView, create a new alert
2. Set your conditions
3. In the "Alert message" section, add JSON with your trading parameters:
   ```json
   {
     "symbol": "EURUSD",
     "order": "BUY",
     "volume": 0.01,
     "token": "your_secure_random_token"
   }
   ```
4. In the Webhook URL, enter:
   ```
   http://your-server-ip:5001/webhook
   ```
5. Save the alert

### 8. Production Deployment (Optional)

For production, it's recommended to:

#### A. Set up a systemd service

```bash
sudo nano /etc/systemd/system/tradingview-webhook.service
```

Add the following:

```ini
[Unit]
Description=TradingView to cTrader Webhook
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/tradingview-ctrader
Environment="PATH=/home/ubuntu/tradingview-ctrader/env/bin"
ExecStart=/home/ubuntu/tradingview-ctrader/env/bin/python webhook.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingview-webhook
sudo systemctl start tradingview-webhook
sudo systemctl status tradingview-webhook
```

#### B. Set up Nginx as a reverse proxy (with HTTPS)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

sudo nano /etc/nginx/sites-available/tradingview-webhook
```

Add the following:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/tradingview-webhook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Add HTTPS:

```bash
sudo certbot --nginx -d your-domain.com
```

---

## 🌐 TradingView Alert Setup

In your TradingView alert:

- **Webhook URL**
  ```
  http://your-domain.com/webhook
  ```
  or with HTTPS:
  ```
  https://your-domain.com/webhook
  ```

- **Alert Message (JSON)**
  ```json
  {
    "symbol": "BTCUSD",
    "order": "BUY",
    "volume": 0.01,
    "token": "your_secure_random_token"
  }
  ```

---

## ⚠️ Important Notes

1. **Volume Limits**: Check your account's maximum volume limit. The webhook will automatically limit orders to the maximum allowed.

2. **Balance**: Ensure your account has sufficient balance for the operations, especially for cryptocurrency trading.

3. **Symbol IDs**: Make sure you're using the correct Symbol IDs from your account (use the list_symbols.py script).

4. **Account ID vs Login**: Use the correct Account ID (not the login number) in your .env file.

---

## 📝 Logging

Each order is logged to a monthly CSV file in the `/logs` directory:

| timestamp (UTC)         | symbol | order | volume | status     |
|-------------------------|--------|-------|--------|------------|
| 2025-04-12T14:00:00+00:00 | BTCUSD | BUY   | 0.01   | SUCCESS    |

---

## ⚠️ Troubleshooting

### Common Errors

1. **"Trading account is not authorized"**
   - Check that your ACCESS_TOKEN is valid
   - Verify you're using the correct ACCOUNT_ID (not the login number)

2. **"Symbol not found with ID..."**
   - Run list_symbols.py to get the correct IDs
   - Update the SYMBOLS dictionary in ctrader.py

3. **"Order volume is bigger than maximum allowed volume"**
   - Reduce the volume in your TradingView alert
   - The webhook has a built-in limit but adjust it based on your account settings

4. **"Not enough money"**
   - Ensure your account has sufficient funds
   - Try with smaller volumes (e.g., 0.01 instead of 0.1)

### Checking Logs

```bash
# If using systemd:
sudo journalctl -u tradingview-webhook -f

# Check the logs directory:
ls -la logs/
cat logs/operations_2025-04.csv
```

---

## 🔐 Security

- Store your .env file securely (don't commit it to repositories)
- Use a strong, random SECRET_TOKEN
- Implement HTTPS for production (via Nginx + Let's Encrypt)
- Regularly rotate your cTrader access tokens

---

## 🔮 Future Enhancements

- Token refresh mechanism
- Support for limit and stop orders
- Telegram/Slack notifications for trades
- Web dashboard for monitoring
- Backtest integration

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

Built with ❤️ to connect TradingView's powerful alerts with cTrader's robust trading API.
