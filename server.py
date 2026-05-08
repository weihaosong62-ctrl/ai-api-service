#!/usr/bin/env python3
"""
AI API Service — DeepSeek V4 转售 + PayPal 自动发 Key
OpenAI 兼容接口: /v1/chat/completions
"""
import json, time, os, secrets, sqlite3, urllib.request, ssl, base64
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
if PROXY_URL:
    from urllib.request import ProxyHandler, build_opener, install_opener
    install_opener(build_opener(ProxyHandler({"https": PROXY_URL, "http": PROXY_URL})))

DIR = Path(__file__).parent
DB = DIR / "apikeys.db"

# DeepSeek
DS_API_KEY = "sk-f1c0b0ea78374fafa878a91b4ddcc082"
DS_URL = "https://api.deepseek.com/v1/chat/completions"
# PayPal
PP_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "Ad_t8wiCfnTwsQFaKVRsEffIyU0kzxIBoFmgaWVaf-CqwcxVDYU2keiEnza8zNsuNaBXJSsvvH6G9Khb")
PP_SECRET = os.environ.get("PAYPAL_SECRET", "ELZKMYVaWmdKd9OcEhw7LByzo5K4o-60DxqKtuSm7W0kjEKlKcID3Q4GgIWL7QCTfjk4XOvz_JkpTiv9")
PP_API = "https://api-m.paypal.com"  # Live

# Pricing tiers
TIERS = {
    "starter": {"name": "Starter", "price": "9.00", "tokens": 1000000, "days": 7},
    "pro":     {"name": "Pro",     "price": "29.00", "tokens": 5000000, "days": 30},
    "max":     {"name": "Max",     "price": "99.00", "tokens": 20000000, "days": 30},
}

# ===== DB =====
def init_db():
    with sqlite3.connect(DB) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS apikeys (
            key TEXT PRIMARY KEY,
            tier TEXT,
            total_tokens INTEGER,
            used_tokens INTEGER DEFAULT 0,
            expires TEXT,
            created TEXT
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            paypal_order_id TEXT,
            apikey TEXT,
            tier TEXT,
            amount TEXT,
            payer_email TEXT,
            created TEXT
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apikey TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            timestamp TEXT
        )""")
        db.commit()

def create_apikey(tier):
    key = "sk-aichat-" + secrets.token_hex(24)
    t = TIERS[tier]
    expires = (datetime.now() + timedelta(days=t["days"])).isoformat()
    with sqlite3.connect(DB) as db:
        db.execute("INSERT INTO apikeys(key,tier,total_tokens,expires,created) VALUES(?,?,?,?,?)",
                   (key, tier, t["tokens"], expires, datetime.now().isoformat()))
        db.commit()
    return key

def check_key(key):
    """Return (valid, total_tokens, used_tokens) or (False, 0, 0)"""
    with sqlite3.connect(DB) as db:
        row = db.execute("SELECT total_tokens, used_tokens, expires FROM apikeys WHERE key=?",
                         (key,)).fetchone()
        if not row: return False, 0, 0
        total, used, expires = row
        if expires < datetime.now().isoformat(): return False, 0, 0
        if used >= total: return False, total, used
        return True, total, used

def deduct_tokens(key, tokens):
    with sqlite3.connect(DB) as db:
        db.execute("UPDATE apikeys SET used_tokens=used_tokens+? WHERE key=?", (tokens, key))
        db.commit()

def log_usage(key, model, prompt_tok, comp_tok):
    with sqlite3.connect(DB) as db:
        db.execute("INSERT INTO usage_log(apikey,model,prompt_tokens,completion_tokens,total_tokens,timestamp) VALUES(?,?,?,?,?,?)",
                   (key, model, prompt_tok, comp_tok, prompt_tok + comp_tok, datetime.now().isoformat()))
        db.commit()

# ===== DeepSeek =====
def call_deepseek(messages, model="deepseek-chat"):
    data = json.dumps({"model": model, "messages": messages, "max_tokens": 4096}).encode()
    req = urllib.request.Request(DS_URL, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DS_API_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        return {
            "content": result["choices"][0]["message"]["content"],
            "model": result.get("model", model),
            "usage": result.get("usage", {})
        }

# ===== PayPal =====
def pp_auth():
    data = "grant_type=client_credentials".encode()
    auth = base64.b64encode(f"{PP_CLIENT_ID}:{PP_SECRET}".encode()).decode()
    req = urllib.request.Request(f"{PP_API}/v1/oauth2/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]

def pp_api(method, path, body=None):
    token = pp_auth()
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{PP_API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as e:
        try: print("PP err:", json.loads(e.read()))
        except: print("PP err:", e)
        return None

# ===== HTTP Handler =====
class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve("index.html")
        elif self.path == "/api/config":
            self._json({"paypalClientId": PP_CLIENT_ID})
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        body = self._body()
        if self.path == "/api/create-order":
            self._create_order(body)
        elif self.path == "/api/capture-order":
            self._capture_order(body)
        elif self.path == "/api/usage":
            self._usage(body)
        elif self.path == "/v1/chat/completions":
            self._chat_api(body)
        else:
            self._json({"error": "Not found"}, 404)

    # === API ===
    def _chat_api(self, data):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._json({"error": {"message": "Missing API key. Use Authorization: Bearer sk-aichat-...", "type": "invalid_request_error"}}, 401); return
        key = auth[7:]
        valid, total, used = check_key(key)
        if not valid:
            if total > 0 and used >= total:
                self._json({"error": {"message": "Quota exhausted. Purchase a new plan.", "type": "quota_exceeded"}}, 429); return
            self._json({"error": {"message": "Invalid or expired API key.", "type": "invalid_request_error"}}, 401); return

        try:
            result = call_deepseek(data.get("messages", []), data.get("model", "deepseek-chat"))
        except Exception as e:
            self._json({"error": {"message": f"Upstream error: {e}", "type": "api_error"}}, 502); return

        usage = result.get("usage", {})
        prompt_tok = usage.get("prompt_tokens", 0)
        comp_tok = usage.get("completion_tokens", 0)
        total_tok = usage.get("total_tokens", prompt_tok + comp_tok)

        deduct_tokens(key, total_tok)
        log_usage(key, data.get("model", "deepseek-chat"), prompt_tok, comp_tok)

        self._json({
            "id": "chatcmpl-" + secrets.token_hex(12),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": result["content"]}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tok, "completion_tokens": comp_tok, "total_tokens": total_tok}
        })

    def _create_order(self, data):
        tier = data.get("tier", "starter")
        price = data.get("price", TIERS[tier]["price"])
        t = TIERS.get(tier, TIERS["starter"])
        order = pp_api("POST", "/v2/checkout/orders", {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": price},
                "description": f'AI API {t["name"]} — {t["tokens"]//10000}万 Token'
            }],
            "application_context": {"brand_name": "AI API Service", "shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW"}
        })
        if order and "id" in order:
            self._json({"orderId": order["id"]})
        else:
            self._json({"error": "Order creation failed"}, 500)

    def _capture_order(self, data):
        order_id = data.get("orderId", "")
        tier = data.get("tier", "starter")
        result = pp_api("POST", f"/v2/checkout/orders/{order_id}/capture")
        if not result or result.get("status") != "COMPLETED":
            self._json({"error": "Payment failed"}, 402); return
        email = ""
        try: email = result["payment_source"]["paypal"]["email_address"]
        except: pass
        key = create_apikey(tier)
        with sqlite3.connect(DB) as db:
            db.execute("INSERT INTO orders(id,paypal_order_id,apikey,tier,amount,payer_email,created) VALUES(?,?,?,?,?,?,?)",
                       (secrets.token_hex(12), order_id, key, tier, TIERS[tier]["price"], email, datetime.now().isoformat()))
            db.commit()
        self._json({"apikey": key, "tier": tier, "email": email})

    def _usage(self, data):
        key = data.get("apikey", "")
        if not key:
            self._json({"error": "Missing API key"}, 400); return
        with sqlite3.connect(DB) as db:
            row = db.execute("SELECT key, tier, total_tokens, used_tokens, expires FROM apikeys WHERE key=?", (key,)).fetchone()
            if not row:
                self._json({"error": "Invalid API key"}, 404); return
            self._json({"key": row[0], "tier": row[1], "totalTokens": row[2], "usedTokens": row[3], "expires": row[4]})

    # === Helpers ===
    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _json(self, data, code=200):
        self.send_response(code)
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _serve(self, path):
        f = DIR / path
        if not f.exists():
            self._json({"error": "Not found"}, 404); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f.read_bytes())

    def log_message(self, *args): pass

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  AI API Service")
    print(f"  Home  : http://localhost:8888")
    print(f"  API   : http://localhost:8888/v1/chat/completions")
    print(f"  Tiers : Starter $9 | Pro $29 | Max $99")
    print("=" * 50)
    ThreadingHTTPServer(("0.0.0.0", 8888), Handler).serve_forever()
