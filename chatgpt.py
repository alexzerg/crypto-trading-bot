#!/usr/bin/env python3
"""
chatgpt_scalper_crypto.py

Paper-trading scalper using Crypto.com websocket market data and ChatGPT signals.
Real prices, fake money.

Features:
 - Telegram notifications and /performance command
 - Crypto.com orderbook streaming (websocket)
 - Price history + volatility analysis
 - GPT-4o-mini scalping signals (buy/hold/sell)
 - LearningManager that adapts based on past performance
 - SQLite logging of trades/signals/historical prices
 - LONG + SHORT paper trading (option A)
"""

import asyncio
import json
import os
import time
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import websockets
import aiohttp
from dotenv import load_dotenv
from openai import OpenAI
import statistics

# Quiet noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

START_TIME = time.time()


logging.basicConfig(
    filename="bot_log.txt",
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logging.getLogger().addHandler(console)
log = logging.getLogger("scalper")


def log_info(msg: str):
    log.info(msg)
    print(msg)


def log_err(msg: str):
    log.error(msg)
    print(msg)


# -------------------------
# Load env
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

env_paths = [
    "/path/to/your/.env_chatgpt",
    os.path.join(BASE_DIR, ".env_chatgpt"),
]

loaded = False
for p in env_paths:
    if os.path.isfile(p):
        load_dotenv(p, override=False)
        load_dotenv(p, override=False)
        log_info(f"Loaded env file: {p}")
        loaded = True
        break

if not loaded:
    raise SystemExit("❌ ERROR: No .env_chatgpt file found in known locations!")


def env_req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        log_err(f"Missing required env var: {name}")
        raise SystemExit(name)
    return v


def env_opt(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v else default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except Exception:
        return default


TELEGRAM_BOT_TOKEN = env_opt("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_IDS = env_opt("TELEGRAM_USER_IDS", "")
OPENAI_API_KEY = env_req("OPENAI_API_KEY")

# persistent DB in /path/to/your/storage by default
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.getenv("DB_FILE")
if not DB_FILE:
    raise RuntimeError("DB_FILE must be provided by wrapper")


GPT_MODEL = env_opt("GPT_MODEL", "gpt-4o-mini")

STOP_LOSS_PCT = env_float("STOP_LOSS_PCT", 0.5)
TAKE_PROFIT_PCT = env_float("TAKE_PROFIT_PCT", 0.7)
POSITION_SIZE_PCT = env_float("POSITION_SIZE_PCT", 0.02)
CAPITAL = env_float("CAPITAL", 500.0)

openai_client = OpenAI(api_key=OPENAI_API_KEY)


# -------------------------
# TELEGRAM IDS parsing
# -------------------------
def parse_telegram_ids(raw: str) -> List[str]:
    if not raw:
        return []
    parts = []
    for fragment in raw.replace(";", ",").split(","):
        f = fragment.strip().strip('"').strip("'")
        if not f:
            continue
        parts.append(f)
    return parts


TELEGRAM_IDS: List[str] = parse_telegram_ids(TELEGRAM_USER_IDS)

log_info(f"DEBUG: TELEGRAM_BOT_TOKEN set: {bool(TELEGRAM_BOT_TOKEN)}")
log_info(f"DEBUG: TELEGRAM_USER_IDS raw: {TELEGRAM_USER_IDS!r}")
log_info(f"DEBUG: TELEGRAM_IDS parsed: {TELEGRAM_IDS!r}")

COINS: List[str] = [
    "ETH_USD", "SOL_USD", "ADA_USD",
    "AVAX_USD", "DOT_USD",
]

log_info(f"Trading symbols: {', '.join(COINS)}")
log_info(
    f"Paper capital: ${CAPITAL:.2f}, position_size_pct={POSITION_SIZE_PCT}, "
    f"stop_loss={STOP_LOSS_PCT}%, take_profit={TAKE_PROFIT_PCT}%"
)


# -------------------------
# Database
# -------------------------
def init_db(path: str = DB_FILE):
    db_dir = os.path.dirname(path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    log_info(f"Initializing DB at {path}")
    con = sqlite3.connect(path, check_same_thread=False)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, side TEXT, size_base REAL,
            entry_price REAL, exit_price REAL,
            entry_time TEXT, exit_time TEXT, pnl REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, signal TEXT, ts TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historical_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, price REAL, ts TEXT
        )
    """)

    con.commit()
    return con   # ✅ return LAST


def db_log_trade(
    symbol,
    side,
    size_base,
    entry_price,
    exit_price,
    entry_time,
    exit_time,
    pnl,
):
    try:
        cur = DB.cursor()
        cur.execute(
            "INSERT INTO trades (symbol, side, size_base, entry_price, exit_price, "
            "entry_time, exit_time, pnl) VALUES (?,?,?,?,?,?,?,?)",
            (
                symbol,
                side,
                size_base,
                entry_price,
                exit_price,
                entry_time,
                exit_time,
                pnl,
            ),
        )
        DB.commit()
    except Exception as e:
        log_err(f"DB trade log error: {e}")


def db_log_signal(symbol, signal):
    try:
        cur = DB.cursor()
        cur.execute(
            "INSERT INTO signals (symbol, signal, ts) VALUES (?,?,?)",
            (symbol, signal, datetime.utcnow().isoformat()),
        )
        DB.commit()
    except Exception as e:
        log_err(f"DB signal log error: {e}")


def db_insert_historical(symbol, price, ts):
    try:
        cur = DB.cursor()
        cur.execute(
            "INSERT INTO historical_data (symbol, price, ts) VALUES (?,?,?)",
            (symbol, float(price), ts),
        )
        DB.commit()
    except Exception as e:
        log_err(f"DB historical log error: {e}")


# -------------------------
# Async Telegram helpers
# -------------------------
async def send_telegram_async(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_IDS:
        log_err("Telegram not configured.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with aiohttp.ClientSession() as session:
        for uid in TELEGRAM_IDS:
            try:
                async with session.post(
                    url,
                    data={"chat_id": uid, "text": msg},
                    timeout=10,
                ) as resp:
                    text = await resp.text()
                    log_info(f"TELEGRAM SENT → {uid}, status={resp.status}, resp={text}")
            except Exception as e:
                log_err(f"Telegram send failed to {uid}: {e}")


def send_telegram(msg: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_telegram_async(msg))
    except RuntimeError:
        asyncio.run(send_telegram_async(msg))


# -------------------------
# Market state
# -------------------------
class MarketState:
    def __init__(self, symbols):
        self.symbols = symbols
        self.orderbooks: Dict[str, Dict[str, List[List[float]]]] = {
            s: {"b": [], "a": []} for s in symbols
        }
        self.last_price: Dict[str, Optional[float]] = {s: None for s in symbols}

    def update(self, symbol, bids, asks):
        try:
            bids = bids if isinstance(bids, list) else []
            asks = asks if isinstance(asks, list) else []
            b = (
                sorted([[float(p), float(sz)] for p, sz in bids], key=lambda x: -x[0])[
                    :100
                ]
                if bids
                else []
            )
            a = (
                sorted([[float(p), float(sz)] for p, sz in asks], key=lambda x: x[0])[
                    :100
                ]
                if asks
                else []
            )
            if symbol not in self.orderbooks:
                self.orderbooks[symbol] = {"b": b, "a": a}
                self.last_price[symbol] = (b[0][0] + a[0][0]) / 2.0 if b and a else None
                return
            self.orderbooks[symbol]["b"] = b
            self.orderbooks[symbol]["a"] = a
            if b and a:
                self.last_price[symbol] = (b[0][0] + a[0][0]) / 2.0
        except Exception as e:
            log_err(f"Failed to update book {symbol}: {e}")


MARKET = MarketState(COINS)


# -------------------------
# Price history (for trends / volatility)
# -------------------------
HISTORY_DIR = os.path.join(BASE_DIR, "price_history")
os.makedirs(HISTORY_DIR, exist_ok=True)


class PriceHistory:
    def __init__(self, symbols):
        self.files = {}
        for s in symbols:
            path = os.path.join(HISTORY_DIR, f"{s}.txt")
            self.files[s] = path
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def add(self, symbol, price: float):
        path = self.files.get(symbol)
        if not path:
            return
        ts = time.time()
        try:
            with open(path, "a") as f:
                f.write(f"{ts},{price}\n")
        except Exception as e:
            log_err(f"PriceHistory write error for {symbol}: {e}")

    def get_recent(self, symbol):
        path = self.files.get(symbol)
        if not path or not os.path.exists(path):
            return []

        rows = []
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ts, p = line.split(",")
                        rows.append((float(ts), float(p)))
                    except Exception:
                        continue
        except Exception as e:
            log_err(f"PriceHistory read error for {symbol}: {e}")
            return []

        cutoff = time.time() - 300  # last 5 minutes
        rows = [r for r in rows if r[0] >= cutoff]
        return rows

    def get_price_offset(self, rows, seconds: int):
        target = time.time() - seconds
        past = [p for (ts, p) in rows if ts <= target]
        return past[-1] if past else None

    def compute_volatility(self, rows):
        prices = [p for (_, p) in rows][-50:]
        if len(prices) < 5:
            return 0.0
        try:
            return statistics.stdev(prices)
        except Exception:
            return 0.0


PRICE_HISTORY = PriceHistory(COINS)


# -------------------------
# Paper broker (LONG + SHORT)
# -------------------------
class PaperBroker:
    def __init__(self, capital_usd):
        self.capital = capital_usd
        # positions[symbol] = {
        #   "side": "LONG" | "SHORT",
        #   "size_base": float,  # always positive
        #   "entry_price": float,
        #   "take_profit": float,
        #   "stop_loss": float,
        #   "entry_time": iso8601,
        # }
        self.positions: Dict[str, Dict[str, Any]] = {}
        log_info(f"PaperBroker initialized with ${self.capital:.2f}")

    def open_long(self, symbol, price, usd_size):
        if symbol in self.positions:
            log_info(f"Already have position for {symbol}, not opening another LONG.")
            return
        if price is None or price <= 0:
            log_err(f"Invalid price for open_long: {price}")
            return
        size_base = usd_size / price
        tp = price * (1 + TAKE_PROFIT_PCT / 100.0)
        sl = price * (1 - STOP_LOSS_PCT / 100.0)
        entry_time = datetime.utcnow().isoformat()
        self.positions[symbol] = {
            "side": "LONG",
            "size_base": size_base,
            "entry_price": price,
            "take_profit": tp,
            "stop_loss": sl,
            "entry_time": entry_time,
        }
        db_log_trade(symbol, "OPEN_LONG", size_base, price, None, entry_time, None, None)
        log_info(
            f"[PAPER] OPEN LONG {symbol} size={size_base:.6f} @ {price:.6f} "
            f"(tp={tp:.6f} sl={sl:.6f})"
        )
        send_telegram(f"[PAPER] OPEN LONG {symbol} @ {price:.6f}")

    def open_short(self, symbol, price, usd_size):
        if symbol in self.positions:
            log_info(f"Already have position for {symbol}, not opening another SHORT.")
            return
        if price is None or price <= 0:
            log_err(f"Invalid price for open_short: {price}")
            return
        size_base = usd_size / price
        # For short: profit if price goes DOWN
        tp = price * (1 - TAKE_PROFIT_PCT / 100.0)
        sl = price * (1 + STOP_LOSS_PCT / 100.0)
        entry_time = datetime.utcnow().isoformat()
        self.positions[symbol] = {
            "side": "SHORT",
            "size_base": size_base,
            "entry_price": price,
            "take_profit": tp,
            "stop_loss": sl,
            "entry_time": entry_time,
        }
        db_log_trade(
            symbol, "OPEN_SHORT", size_base, price, None, entry_time, None, None
        )
        log_info(
            f"[PAPER] OPEN SHORT {symbol} size={size_base:.6f} @ {price:.6f} "
            f"(tp={tp:.6f} sl={sl:.6f})"
        )
        send_telegram(f"[PAPER] OPEN SHORT {symbol} @ {price:.6f}")

    def close(self, symbol, price, reason="manual"):
        pos = self.positions.get(symbol)
        if not pos:
            return
        side = pos["side"]
        entry = pos["entry_price"]
        size_base = pos["size_base"]

        if side == "LONG":
            pnl = (price - entry) * size_base
        else:  # SHORT
            pnl = (entry - price) * size_base

        exit_time = datetime.utcnow().isoformat()
        db_log_trade(
            symbol,
            "CLOSE_" + side,
            size_base,
            entry,
            price,
            pos["entry_time"],
            exit_time,
            pnl,
        )
        log_info(
            f"[PAPER] CLOSE {symbol} {side} @ {price:.6f} pnl={pnl:.6f} ({reason})"
        )
        send_telegram(
            f"[PAPER] CLOSE {symbol} {side} @ {price:.6f} PnL={pnl:.6f} ({reason})"
        )
        del self.positions[symbol]

    def check_tpsl(self, symbol, mark_price: float):
        pos = self.positions.get(symbol)
        if not pos:
            return
        side = pos["side"]
        tp = pos["take_profit"]
        sl = pos["stop_loss"]

        if side == "LONG":
            if mark_price >= tp:
                self.close(symbol, mark_price, "TP")
            elif mark_price <= sl:
                self.close(symbol, mark_price, "SL")
        else:  # SHORT
            if mark_price <= tp:
                self.close(symbol, mark_price, "TP")
            elif mark_price >= sl:
                self.close(symbol, mark_price, "SL")


BROKER = PaperBroker(CAPITAL)


# -------------------------
# Historical preload
# -------------------------
def fetch_last_price_rest(symbol):
    try:
        url = f"https://api.crypto.com/v2/public/get-ticker?instrument_name={symbol}"
        r = requests.get(url, timeout=6)
        j = r.json()
        data = j.get("result", {}).get("data")
                if isinstance(data, list):
                    data = data[0] if data else None
                if not isinstance(data, dict):
                    return 1.0

                for k in ("a", "last", "c"):
                    v = data.get(k)
                    if v is None:
                        continue
                    if isinstance(v, list) and v:
                        v = v[0]
                    try:
                        return float(v)
                    except Exception:
                        pass
    except Exception as e:
        log_err(f"REST price fetch failed for {symbol}: {e}")
    return 1.0


def preload_historical_data(symbols):
    log_info("Preloading historical data...")
    for s in symbols:
        db_insert_historical(s, fetch_last_price_rest(s), datetime.utcnow().isoformat())
    log_info("Historical preload complete.")


symbol_last_gpt: Dict[str, float] = {}
GPT_COOLDOWN = 10  # seconds (we'll use a fraction of this)
GPT_QUOTA_BACKOFF = 600  # 10 minutes


def compute_trend_strength(price_now, p10, p30, p120):
    """
    Compute a simple trend strength score in [0,1].
    0 = strongly down, 1 = strongly up, 0.5 = flat/uncertain.
    """
    if price_now is None:
        return 0.5

    deltas = []
    for past in (p10, p30, p120):
        if past is not None and past > 0:
            deltas.append((price_now - past) / past)

    if not deltas:
        return 0.5

    avg_delta = sum(deltas) / len(deltas)

    # clip to [-0.02, +0.02] (~2% move) then scale
    if avg_delta > 0.02:
        avg_delta = 0.02
    if avg_delta < -0.02:
        avg_delta = -0.02

    # map [-0.02, 0.02] -> [0, 1]
    strength = (avg_delta + 0.02) / 0.04
    return max(0.0, min(1.0, strength))


# -------------------------
# GPT signal (AGGRESSIVE, LONG + SHORT, with LearningManager)
# -------------------------
async def ask_gpt_for_signal(symbol: str, book: dict) -> str:
    """
    Aggressive signal generator:

    - Uses orderbook + short-term history
    - GPT chooses buy/sell/hold from a rich prompt
    - Deterministic fallback makes HOLD rare
    - LearningManager.adjust_signal can DOWNGRADE risky trades
    """

    # ----------- Cooldown (aggressive: ~3s per symbol) -----------
    now = time.time()
    last_call = symbol_last_gpt.get(symbol, 0)
    if now - last_call < max(3, GPT_COOLDOWN * 0.3):  # minimum 3 seconds
        return "HOLD"
    symbol_last_gpt[symbol] = now

    # ----------- Orderbook Data -----------
    best_bid = book.get("b", [])[0][0] if book.get("b") else None
    best_ask = book.get("a", [])[0][0] if book.get("a") else None

    if best_bid is None or best_ask is None:
        return "HOLD"

    price_now = (best_bid + best_ask) / 2
    bid_vol = sum(sz for _, sz in (book.get("b") or [])[:5])
    ask_vol = sum(sz for _, sz in (book.get("a") or [])[:5])

    # ----------- Price History -----------
    rows = PRICE_HISTORY.get_recent(symbol)
    price_10s = PRICE_HISTORY.get_price_offset(rows, 10)
    price_30s = PRICE_HISTORY.get_price_offset(rows, 30)
    price_120s = PRICE_HISTORY.get_price_offset(rows, 120)
    volatility = PRICE_HISTORY.compute_volatility(rows)

    # ----------- Derived Features -----------
    trend_strength = compute_trend_strength(price_now, price_10s, price_30s, price_120s)
    ob_imbalance = (bid_vol + 1e-9) / (ask_vol + 1e-9)

    # Base deterministic decision (very loose thresholds)
    base_decision = "HOLD"
    # tiny trend edge
    if trend_strength > 0.502:
        base_decision = "BUY"
    elif trend_strength < 0.498:
        base_decision = "SELL"
    # tiny orderflow edge
    if ob_imbalance > 1.01:
        base_decision = "BUY"
    elif ob_imbalance < 0.99:
        base_decision = "SELL"

    # ----------- Learning state (for prompt only) -----------
    win_rate = sym_state.get("win_rate", 0.0)
    recommendation = sym_state.get("recommendation", "unknown")
    max_loss_streak = sym_state.get("max_loss_streak", 0)

    # ----------- GPT Prompt (rich, aggressive) -----------
    user_prompt = (
        f"Symbol: {symbol}\n"
        f"Current price: {price_now}\n"
        f"Price 10s ago: {price_10s}\n"
        f"Price 30s ago: {price_30s}\n"
        f"Price 120s ago: {price_120s}\n"
        f"Volatility (stddev, last 50 ticks): {volatility:.6f}\n"
        f"BestBid: {best_bid}\n"
        f"BestAsk: {best_ask}\n"
        f"Bid5 volume: {bid_vol:.6f}\n"
        f"Ask5 volume: {ask_vol:.6f}\n"
        f"Trend strength (0=down, 0.5=flat, 1=up): {trend_strength:.3f}\n"
        f"Orderbook imbalance (bid/ask): {ob_imbalance:.3f}\n"
        f"Deterministic base decision: {base_decision}\n"
        "Using all this market information, choose the most profitable action.\n"
        "You are allowed to be aggressive. HOLD only when everything is flat.\n"
        "Return ONLY one word: buy, sell, or hold."
    )

    system_prompt = (
        "You are a high-frequency crypto scalping engine.\n"
        "You trade BOTH long and short.\n"
        "Use:\n"
        " - Short-term trend (trend_strength)\n"
        " - Orderbook imbalance (bid/ask)\n"
        " - Volatility\n"
        " - Deterministic base_decision\n"
        "AGGRESSIVE RULES:\n"
        "- If trend_strength > 0.505 or orderbook imbalance > 1.01 → prefer BUY.\n"
        "- If trend_strength < 0.495 or orderbook imbalance < 0.99 → prefer SELL.\n"
        "- If base_decision is BUY or SELL, strongly prefer that side.\n"
        "- HOLD only if trend_strength is in [0.498, 0.502] AND "
        "  orderbook imbalance in [0.99, 1.01] AND there is no edge.\n"
        "- When in doubt, choose BUY or SELL rather than HOLD.\n\n"
        "Return ONLY one word: buy, sell, or hold."
    )

    # ----------- GPT CALL -----------
    try:
        def call():
            return openai_client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=4,
            )

        resp = await asyncio.to_thread(call)
        raw = resp.choices[0].message.content.strip().lower()

        if raw.startswith("buy"):
            sig = "BUY"
        elif raw.startswith("sell"):
            sig = "SELL"
        else:
            sig = "HOLD"

    except Exception as e:
        msg = str(e)

        if "insufficient_quota" in msg or "You exceeded your current quota" in msg:
            log_err(f"QUOTA EXCEEDED for {symbol}, backing off 10m")
            symbol_last_gpt[symbol] = now + GPT_QUOTA_BACKOFF
            await send_telegram_async("⚠ GPT quota exceeded. Cooling 10 minutes.")
            return "HOLD"

        if "429" in msg:
            log_err(f"RATE LIMIT for {symbol}, delaying 60s")
            symbol_last_gpt[symbol] = now + 60
            return "HOLD"

        log_err(f"GPT ERROR for {symbol}: {e}")
        return "HOLD"

    # ----------- Deterministic fallback: FORCE trades when edge exists -----------
    if sig == "HOLD":
        if trend_strength > 0.501:
            sig = "BUY"
        elif trend_strength < 0.499:
            sig = "SELL"
        elif ob_imbalance > 1.01:
            sig = "BUY"
        elif ob_imbalance < 0.99:
            sig = "SELL"

    # ----------- LearningManager as a safety filter -----------
    sig_adj = sig

    # Log decision
    db_log_signal(symbol, sig)
    log_info(
        f"[SIG] {symbol}: sig={sig}, trend={trend_strength:.3f}, ob={ob_imbalance:.3f}, "
        f"bid_vol={bid_vol:.2f}, ask_vol={ask_vol:.2f}, now={price_now}"
    )

    return sig


# -------------------------
# Crypto.com Websocket Client
# -------------------------
class CryptoComClient:
    def __init__(self, symbols, ws_url="wss://stream.crypto.com/v2/market"):
        self.symbols = symbols
        self.url = ws_url
        self._stopping = False

    async def start(self):
        delay = 1
        while not self._stopping:
            try:
                log.debug(f"Connecting WS: {self.url}")
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=None,
                ) as ws:
                    sub = {
                        "id": 1,
                        "method": "subscribe",
                        "params": {
                            "channels": [f"book.{s}.150" for s in self.symbols]
                        },
                    }
                    await ws.send(json.dumps(sub))
                    delay = 1
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        params = msg.get("params") or msg.get("result") or {}
                        data = params.get("data") if isinstance(params, dict) else None
                        channel = params.get("channel") or msg.get("method")
                        if data and isinstance(data, list):
                            for item in data:
                                sym = item.get("i") or item.get("instrument_name")
                                if not sym and channel and isinstance(channel, str):
                                    parts = channel.split(".")
                                    if len(parts) >= 2:
                                        sym = parts[1]
                                bids = item.get("b") or item.get("bids") or []
                                asks = item.get("a") or item.get("asks") or []
                                if not isinstance(bids, list):
                                    bids = []
                                if not isinstance(asks, list):
                                    asks = []
                                if sym:
                                    MARKET.update(sym, bids or [], asks or [])
                                    mid = MARKET.last_price.get(sym)
                                    if mid:
                                        PRICE_HISTORY.add(sym, mid)
                log.debug("WS closed, reconnecting...")
            except Exception as e:
                log_err(f"WS error: {e}")
                send_telegram(f"WS error: {e}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    def stop(self):
        self._stopping = True

def fetch_price(symbol):
    # ---------- PRIMARY: Crypto.com ----------
    try:
        url = "https://api.crypto.com/v2/public/get-ticker"
        params = {"instrument_name": symbol}
        r = requests.get(
            url,
            params=params,
            timeout=(3, 3),
            headers={"User-Agent": "cgpt-scalper/1.0"},
        )

        if r.status_code == 200:
            j = r.json()
            data = j.get("result", {}).get("data")
            if isinstance(data, dict):
                for k in ("a", "last", "price", "close"):
                    if k in data:
                        return float(data[k])
    except Exception as e:
        log_err(f"REST primary failed {symbol}: {e}")

    # ---------- FALLBACK: CoinGecko ----------
    try:
        mapping = {
            "ETH_USD": "ethereum",
            "SOL_USD": "solana",
            "ADA_USD": "cardano",
            "AVAX_USD": "avalanche-2",
            "DOT_USD": "polkadot",
        }

        coin_id = mapping.get(symbol)
        if not coin_id:
            return None

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}

        r = requests.get(url, params=params, timeout=(3, 3))
        if r.status_code == 200:
            j = r.json()
            return float(j[coin_id]["usd"])
    except Exception as e:
        log_err(f"REST fallback failed {symbol}: {e}")

    return None

# -------------------------
# Main loop
# -------------------------
# -------------------------
# Main loop (REST polling version, replacing WebSockets entirely)
# -------------------------
async def main_loop():
    preload_historical_data(COINS)
    test_sym = COINS[0]
    test_price = fetch_price(test_sym)
    log_info(f"DEBUG startup price {test_sym}={test_price}")
    if test_price:
            BROKER.open_long(test_sym, test_price, CAPITAL * POSITION_SIZE_PCT)

    log_info("Starting REST polling price feed (WebSocket disabled).")
    await send_telegram_async("🚀 ChatGPT scalper started (REST mode). Paper trading 8 altcoins.")

    def format_uptime(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}h {m}m {s}s"


    # 2-hour performance reports
    async def performance_report_loop():
        while True:
            await asyncio.sleep(2 * 3600)
            try:
                cur = DB.cursor()
                cur.execute("SELECT pnl FROM trades WHERE pnl IS NOT NULL")
                pnls = [r[0] or 0.0 for r in cur.fetchall()]
                total = sum(pnls)
                msg = f"📊 2-hour performance report:\nTotal PnL: {total:.2f} USDT"
                log_info(msg)
                await send_telegram_async(msg)
            except Exception as e:
                log_err(f"Performance report failed: {e}")

    # Telegram commands
    async def telegram_command_loop():
        last_update_id = 0
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

        def format_uptime(seconds: float) -> str:
            seconds = int(seconds)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}h {m}m {s}s"

        while True:
            try:
                params = {"offset": last_update_id + 1, "timeout": 10}
                resp = await asyncio.to_thread(
                    requests.get, url, params=params, timeout=15
                )
                j = resp.json()

                for u in j.get("result", []):
                    last_update_id = u["update_id"]

                    msg_text = u.get("message", {}).get("text", "")
                    if not msg_text:
                        continue

                    text = msg_text.strip().lower()
                    chat_id = u.get("message", {}).get("chat", {}).get("id")
                    if not chat_id:
                        continue

                    # =========================
                    # /performance command
                    # =========================
                    if text == "/performance":
                        try:
                            cur = DB.cursor()

                            # --- count ALL trade rows (OPEN + CLOSE)
                            cur.execute("SELECT COUNT(*) FROM trades")
                            total_rows = cur.fetchone()[0]

                            # --- closed trades only (pnl != NULL)
                            cur.execute(
                                "SELECT pnl, entry_time, exit_time FROM trades WHERE pnl IS NOT NULL"
                            )
                            rows = cur.fetchall()

                            pnls = [row[0] for row in rows]
                            closed_trades = len(pnls)

                            wins = sum(1 for p in pnls if p > 0)
                            losses = sum(1 for p in pnls if p < 0)
                            total_pnl = sum(pnls)

                            avg_win = (
                                sum(p for p in pnls if p > 0) / wins if wins else 0.0
                            )
                            avg_loss = (
                                sum(p for p in pnls if p < 0) / losses if losses else 0.0
                            )
                            win_rate = (
                                (wins / closed_trades) * 100 if closed_trades else 0.0
                            )

                            best_trade = max(pnls) if pnls else 0.0
                            worst_trade = min(pnls) if pnls else 0.0

                            # --- uptime
                            uptime = time.time() - START_TIME
                            uptime_str = format_uptime(uptime)

                            trades_per_hour = (
                                closed_trades / (uptime / 3600)
                                if uptime > 0
                                else 0.0
                            )
                            pnl_per_hour = (
                                total_pnl / (uptime / 3600)
                                if uptime > 0
                                else 0.0
                            )

                            # --- avg time between CLOSED trades
                            trade_times = []
                            for _, _, exit_time in rows:
                                try:
                                    t = datetime.fromisoformat(exit_time)
                                    trade_times.append(t.timestamp())
                                except Exception:
                                    pass

                            avg_interval = 0
                            if len(trade_times) > 1:
                                trade_times.sort()
                                diffs = [
                                    trade_times[i] - trade_times[i - 1]
                                    for i in range(1, len(trade_times))
                                ]
                                avg_interval = sum(diffs) / len(diffs)

                            avg_interval_str = (
                                format_uptime(avg_interval) if avg_interval else "N/A"
                            )

                            open_positions = len(BROKER.positions)

                            msg = (
                                "📊 EXTENDED PERFORMANCE REPORT\n"
                                "--------------------------------------\n"
                                f"⏱ Bot uptime: {uptime_str}\n"
                                f"📄 Trade rows (OPEN+CLOSE): {total_rows}\n"
                                f"✅ Closed trades: {closed_trades}\n"
                                f"📈 Wins: {wins} | 📉 Losses: {losses}\n"
                                f"🔥 Win rate: {win_rate:.2f}%\n\n"
                                f"💰 Total PnL: {total_pnl:.4f} USDT\n"
                                f"💸 Best trade: {best_trade:.4f}\n"
                                f"⚠️ Worst trade: {worst_trade:.4f}\n"
                                f"🏆 Avg Win: {avg_win:.4f}\n"
                                f"💀 Avg Loss: {avg_loss:.4f}\n\n"
                                f"📊 Trades/hr: {trades_per_hour:.3f}\n"
                                f"💹 PnL/hr: {pnl_per_hour:.4f}\n"
                                f"⏳ Avg time between trades: {avg_interval_str}\n\n"
                                f"📂 Open positions: {open_positions}\n"
                            )

                            await asyncio.to_thread(
                                requests.post,
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                                data={"chat_id": chat_id, "text": msg},
                                timeout=15,
                            )

                        except Exception as e:
                            log_err(f"Performance report error: {e}")

            except Exception as e:
                log_err(f"Telegram polling error: {e}")

            await asyncio.sleep(2.0)

    # Create background tasks
    perf_task = asyncio.create_task(performance_report_loop())
    tg_task = asyncio.create_task(telegram_command_loop())

    # MAIN TRADING ENGINE (REST LOOP)
    try:
        log_info("Entering main trading loop (REST polling).")

        # STARTUP SANITY TRADE (prove broker+DB+telegram works)
        _sym0 = COINS[0]
        _p0 = fetch_price(_sym0)
        if _p0:
            BROKER.open_long(_sym0, _p0, CAPITAL * POSITION_SIZE_PCT)

        while True:
            for sym in COINS:
                # get fresh price
                price = fetch_price(sym)
            
                    log_err(f"Price unavailable for {sym}, skipping")
                    continue
                BROKER.check_tpsl(sym, price)

                log_info(f"[PRICE] {sym} = {price}")

                # update market + history
                MARKET.last_price[sym] = price
                MARKET.orderbooks[sym] = {
                    "b": [[price * 0.999, 1.0]],
                    "a": [[price * 1.001, 1.0]],
                }
                PRICE_HISTORY.add(sym, price)

                # get GPT signal ONCE
                try:
                    signal = await ask_gpt_for_signal(sym, MARKET.orderbooks[sym])
                except Exception as e:
                    log_err(f"Signal error for {sym}: {e}")
                    signal = "HOLD"
                if sym not in BROKER.positions:
                    signal = "BUY"

                # WARM-UP OVERRIDE (must be AFTER GPT)
                if len(PRICE_HISTORY.get_recent(sym)) < 10 and sym not in BROKER.positions:
                    signal = "BUY"

                log_info(f"[DECISION] {sym} final_signal={signal}")

                if signal == "BUY":
                    BROKER.open_long(sym, price, CAPITAL * POSITION_SIZE_PCT)
                elif signal == "SELL":
                    BROKER.open_short(sym, price, CAPITAL * POSITION_SIZE_PCT)

                # WARM-UP: override GPT during cold start
                if len(PRICE_HISTORY.get_recent(sym)) < 10 and not BROKER.positions.get(sym):
                    signal = "BUY"

                # -------------------------
                # HARD AGGRESSIVE MODE
                # -------------------------

                # 1️⃣ Force BUY if price moved >0.05% upward in last 20s
                rows = PRICE_HISTORY.get_recent(sym)
                if len(rows) > 5:
                    old_ts, old_price = rows[0]
                    price_change = (price - old_price) / old_price
                    if price_change > 0.0005:  # 0.05%
                        signal = "BUY"

                # 2️⃣ Force BUY every 10 minutes if there were ZERO trades
                cur = DB.cursor()
                cur.execute("SELECT COUNT(*) FROM trades")
                trade_count = cur.fetchone()[0]
                if trade_count == 0:
                    signal = "BUY"

                # 3️⃣ If GPT says HOLD too long → BUY anyway
                global no_trade_counter
                try:
                    no_trade_counter += 1
                except:
                    no_trade_counter = 1

                if no_trade_counter > 300:  # ~5 minutes @ 1s intervals
                    log_info(f"⚠️ No trades for 5 mins → FORCING BUY on {sym}")
                    signal = "BUY"
                    no_trade_counter = 0

                # -------------------------
                # EXECUTE TRADE (forced or GPT)
                # -------------------------
                log_info(f"[DECISION] {sym} signal={signal}")

                log_info(f"[DECISION] {sym} final_signal={signal}")
                if signal == "BUY":
                    log_info(f"[EXEC] opening LONG {sym}")
                    BROKER.open_long(sym, price, CAPITAL * POSITION_SIZE_PCT)

            await asyncio.sleep(1.0)  # 1-second polling

    except KeyboardInterrupt:
        log_info("Manual stop.")
    except Exception as e:
        log_err(f"Main loop fatal: {e}")
        await send_telegram_async(f"❌ Fatal error: {e}")
    finally:
        perf_task.cancel()
        tg_task.cancel()

        # Cleanup history files
        for s, path in PRICE_HISTORY.files.items():
            try:
                os.remove(path)
            except:
                pass


# -------------------------
# Entry
# -------------------------
if __name__ == "__main__":
    log_info("Starting ChatGPT scalper (Crypto.com) - paper trading.")
    asyncio.run(main_loop())
