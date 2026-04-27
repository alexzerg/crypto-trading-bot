#!/usr/bin/env python3
"""
ALTSCALP BOT - AGGRESSIVE BEAR EDITION (DEC 2025 REFACTOR - TRADES IN GRIND)
Now trades in slow bears: looser volume, smaller rebounds, lower RSI, added dip-buy.
"""
import asyncio
import time
import argparse
import random
import os
import hmac
import hashlib
import json
import aiohttp
import requests
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env_grok")
class Settings:
    def __init__(self):
        # Telegram
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_ids = os.getenv('TELEGRAM_USER_IDS', '')
        self.TELEGRAM_USER_IDS = [int(x.strip()) for x in telegram_ids.split(',')] if telegram_ids else []
        # API Keys
        self.CRYPTOCOM_API_KEY = os.getenv('CRYPTOCOM_API_KEY')
        self.CRYPTOCOM_SECRET_KEY = os.getenv('CRYPTOCOM_SECRET_KEY')
        self.GROK_API_KEY = os.getenv('GROK_API_KEY')
        # Market Condition
        self.MARKET_CONDITION = os.getenv('MARKET_CONDITION', 'bear').lower()
        # <<< REFACTORED FOR ACTUAL TRADING IN CURRENT GRIND >>>
        if self.MARKET_CONDITION == 'bull':
            self.TRADE_BASE_PERCENT = float(os.getenv('TRADE_BASE_PERCENT_BULL', '20'))
            self.MAX_POSITIONS = int(os.getenv('MAX_POSITIONS_BULL', '5'))
            self.PROFIT_TARGET = float(os.getenv('PROFIT_TARGET_BULL', '3.0'))
            self.STOP_LOSS = float(os.getenv('STOP_LOSS_BULL', '1.5'))
            self.CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD_BULL', '0.60'))
            self.POSITION_TIMEOUT = int(os.getenv('POSITION_TIMEOUT_BULL', '3600'))
        else: # BEAR/EXTREME_BEAR - LOOSER TO FORCE TRADES
            self.TRADE_BASE_PERCENT = 8.0 # Bigger size to compensate smaller moves
            self.MAX_POSITIONS = 4
            self.PROFIT_TARGET = 4.2 # Realistic for small rebounds
            self.STOP_LOSS = 1.6
            self.CONFIDENCE_THRESHOLD = 0.35 # Lower threshold = more signals
            self.POSITION_TIMEOUT = 7200
            self.VOLUME_MULTIPLIER_REQUIRED = 1.4 # Much looser volume spike
            self.MIN_REBOUND_REQUIRED = 0.6 # Tiny rebound enough
            self.MAX_RSI_FOR_LONG = 42
        # Shared settings
        self.INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '500.0'))
        self.SIM_BALANCE = float(os.getenv('SIM_BALANCE', '500.0'))
        self.TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS', 'ETH,SOL,AVAX,DOT,LINK,ATOM,UNI,BCH')
        self.CYCLE_DELAY = int(os.getenv('CYCLE_DELAY', '11'))
        self.VERBOSE_MODE = os.getenv('VERBOSE_MODE', 'true').lower() == 'true'
        self.FEE_RATE = 0.002 # 0.2%
        self.LEVERAGE = 5 # Default leverage for futures
    @property
    def symbols(self) -> List[str]:
        return [s.strip() for s in self.TRADING_SYMBOLS.split(",") if s.strip()]
    def update_params(self, market_condition: str):
        self.MARKET_CONDITION = market_condition.lower()
        if self.MARKET_CONDITION == 'bull':
            self.TRADE_BASE_PERCENT = float(os.getenv('TRADE_BASE_PERCENT_BULL', '20'))
            self.MAX_POSITIONS = int(os.getenv('MAX_POSITIONS_BULL', '5'))
            self.PROFIT_TARGET = float(os.getenv('PROFIT_TARGET_BULL', '3.0'))
            self.STOP_LOSS = float(os.getenv('STOP_LOSS_BULL', '1.5'))
            self.CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD_BULL', '0.60'))
            self.POSITION_TIMEOUT = int(os.getenv('POSITION_TIMEOUT_BULL', '3600'))
        else: # bear or neutral
            self.TRADE_BASE_PERCENT = 8.0
            self.MAX_POSITIONS = 4
            self.PROFIT_TARGET = 4.2
            self.STOP_LOSS = 1.6
            self.CONFIDENCE_THRESHOLD = 0.35
            self.POSITION_TIMEOUT = 7200
            self.VOLUME_MULTIPLIER_REQUIRED = 1.4
            self.MIN_REBOUND_REQUIRED = 0.6
            self.MAX_RSI_FOR_LONG = 42
settings = Settings()
class GrokAnalyzer:
    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.enabled = bool(self.api_key)
        self.request_count = 0
        self.last_grok_call = 0
        self.MIN_INTERVAL = 20
    async def comprehensive_analysis(self, symbol: str, market_data: Dict) -> Dict:
        if not self.enabled:
            return self._get_fallback_analysis(symbol, market_data)
        now = time.time()
        if now - self.last_grok_call < self.MIN_INTERVAL:
            return self._get_fallback_analysis(symbol, market_data)
        market_condition = market_data.get('market_condition', 'bull')
        self.request_count += 1
        self.last_grok_call = now
        prompt = self._build_market_prompt(symbol, market_data, market_condition)
        try:
            print(f"GROK CALL #{self.request_count} — analyzing {symbol}...")
            response = await self._call_grok_api(prompt)
            return self._parse_ai_response(response, symbol, market_data)
        except Exception as e:
            print(f"Grok API error: {e}")
            return self._get_fallback_analysis(symbol, market_data)
    def _build_market_prompt(self, symbol: str, market_data: Dict, market_condition: str) -> str:
        supports = market_data.get('supports', [])
        support_str = f"Supports: {', '.join([f'${s:.4f}' for s in supports])}" if supports else "No supports detected"
        if market_condition == 'bull':
            return f"""
            ACT AS A CRYPTO SCALPING EXPERT IN A BULL MARKET. PRIORITIZE TREND-FOLLOWING.
            SYMBOL: {symbol}
            CURRENT PRICE: ${market_data['current_price']:.4f}
            TECHNICALS:
            - RSI: {market_data['rsi']:.1f}
            - Trend: {market_data['trend'].upper()}
            - Volatility: {market_data['volatility']:.1f}%
            - BTC Correlation: {market_data['btc_correlation']:.2f}
            - {support_str}
            BULL MARKET STRATEGY:
            - Enter on pullbacks (RSI 30-60) or breakout signals
            - Target 2-3% profit per trade
            - Use trailing stops to lock in gains
            - Allow moderate volatility (<15%)
            - Prefer coins with moderate BTC correlation (0.3-0.7)
            RECOMMENDATION:
            {{
                "action": "BUY/SELL/HOLD",
                "confidence": 0.0-1.0,
                "reasoning": "Bull market rationale - focus on trends",
                "risk_level": "LOW/MEDIUM/HIGH",
                "timeframe": "SCALP_15-30MIN",
                "price_target": "2-3% above entry",
                "stop_loss": "1-1.5% below entry"
            }}
            BE SELECTIVE BUT CAPTURE TRENDING MOVES.
            """
        else:
            return f"""
            YOU ARE A CONTRARIAN SCALPER IN A BRUTAL BEAR MARKET.
            BUY THE PANIC, SELL THE FOMO — GO AGAINST THE HERD.
            SYMBOL: {symbol} | PRICE: ${market_data['current_price']:.4f}
            RSI: {market_data['rsi']:.1f} | Volatility: {market_data['volatility']:.1f}%
            BTC Corr: {market_data['btc_correlation']:.2f} | {support_str}
            BUY when you see panic selling (sharp drop + volume spike).
            SELL on parabolic FOMO spikes.
            Target 4–8% rebounds from fear.
            Return ONLY valid JSON:
            {{
                "action": "BUY" or "SELL" or "HOLD",
                "confidence": 0.0 to 1.0,
                "reasoning": "short anti-herd explanation"
            }}
            """
    async def _call_grok_api(self, prompt: str) -> Dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-4.1-fast-reasoning",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 800
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=20
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Grok API returned {response.status}")
    def _parse_ai_response(self, response: Dict, symbol: str, market_data: Dict) -> Dict:
        try:
            content = response['choices'][0]['message']['content']
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group())
                if 'action' in ai_data and 'confidence' in ai_data:
                    return {
                        'action': ai_data['action'],
                        'confidence': float(ai_data['confidence']),
                        'reasoning': ai_data.get('reasoning', 'Grok Market Analysis'),
                        'risk_level': ai_data.get('risk_level', 'MEDIUM'),
                        'key_factors': ai_data.get('key_factors', []),
                        'source': 'GROK_MARKET'
                    }
            raise Exception("Invalid JSON format in Grok response")
        except Exception as e:
            print(f"Failed to parse Grok response: {e}")
            return self._get_fallback_analysis(symbol, market_data)
    def _get_fallback_analysis(self, symbol: str, market_data: Dict) -> Dict:
        return {
            'action': 'HOLD',
            'confidence': 0.0,
            'reasoning': 'Technical analysis only - Grok not available',
            'risk_level': 'MEDIUM',
            'key_factors': ['Using technical analysis fallback'],
            'source': 'TECHNICAL_FALLBACK'
        }
class CryptoComAPI:
    def __init__(self):
        # FIXED: Correct base URL for derivatives
        self.base_url = "https://deriv-api.crypto.com/v1"
        self.api_key = settings.CRYPTOCOM_API_KEY
        self.secret_key = settings.CRYPTOCOM_SECRET_KEY
        self.price_histories = {symbol.upper(): [] for symbol in settings.symbols}
        self.volume_histories = {symbol.upper(): [] for symbol in settings.symbols}
        self.session = None
        self.request_count = 0
        self.last_request_time = 0
    async def get_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=20)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    def _sign_request(self, request_params: Dict) -> str:
        if not self.secret_key:
            return ""
        param_str = ""
        if 'params' in request_params and request_params['params']:
            param_str = json.dumps(request_params['params'], separators=(',', ':'), sort_keys=True)
        sign_payload = request_params['method'] + str(request_params['id']) + request_params['api_key'] + param_str + str(request_params['nonce'])
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            sign_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    async def get_balances(self) -> Dict[str, float]:
        if not self.api_key or not self.secret_key:
            return {"USDT": settings.INITIAL_CAPITAL}
        try:
            params = {
                "id": int(time.time() * 1000),
                "method": "private/user-balance",
                "api_key": self.api_key,
                "nonce": int(time.time() * 1000),
                "params": {}
            }
            params['sig'] = self._sign_request(params)
            session = await self.get_session()
            async with session.post(
                    f"{self.base_url}/private/user-balance",
                    json=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0 and "result" in data:
                        # For derivatives, total margin balance in USDT
                        return {"USDT": float(data["result"].get("total_margin_balance", settings.INITIAL_CAPITAL))}
                print(f"Balance API error: HTTP {response.status}")
                return {"USDT": settings.INITIAL_CAPITAL}
        except Exception as e:
            print(f"Crypto.com balance error: {e}")
            return {"USDT": settings.INITIAL_CAPITAL}
    async def get_positions(self) -> Dict:
        if not self.api_key or not self.secret_key:
            return {}
        try:
            params = {
                "id": int(time.time() * 1000),
                "method": "private/get-positions",
                "api_key": self.api_key,
                "nonce": int(time.time() * 1000),
                "params": {"inst_type": "PERPETUAL_SWAP"}
            }
            params['sig'] = self._sign_request(params)
            session = await self.get_session()
            async with session.post(
                    f"{self.base_url}/private/get-positions",
                    json=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0:
                        positions = {}
                        for pos in data["result"].get("positions", []):
                            inst = pos["instrument_name"]
                            symbol = inst.replace("_USD_PERP", "").upper() # e.g., ETH_USD_PERP → ETH
                            qty = float(pos.get("quantity", 0))
                            entry = float(pos.get("avg_price", 0))
                            if symbol in settings.symbols:
                                positions[symbol] = {'qty': qty, 'entry': entry}
                        return positions
                return {}
        except Exception as e:
            print(f"Positions error: {e}")
            return {}
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        current_time = time.time()
        if current_time - self.last_request_time < 0.08: # ~12 req/sec limit
            await asyncio.sleep(0.08 - (current_time - self.last_request_time))
        self.last_request_time = time.time()
        # FIXED: Correct format for Crypto.com derivs
        trading_pair = f"{symbol.upper()}_USD_PERP"
        try:
            session = await self.get_session()
            url = f"{self.base_url}/public/get-ticker"
            params = {"instrument_name": trading_pair}
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 0:
                        ticker_data = data["result"]["data"]
                        price = float(ticker_data["a"]) # last traded price
                        volume_24h = float(ticker_data.get("v", 0))
                        if price > 0:
                            self.price_histories[symbol.upper()].append(price)
                            self.volume_histories[symbol.upper()].append(volume_24h)
                            if len(self.price_histories[symbol.upper()]) > 200:
                                self.price_histories[symbol.upper()].pop(0)
                                self.volume_histories[symbol.upper()].pop(0)
                            return {"price": price, "volume": volume_24h}
                print(f"Ticker {symbol}: HTTP {response.status} - {await response.text()}")
        except Exception as e:
            print(f"Ticker {symbol} failed ({e}) → using fallback")
        # Fallback logic (unchanged)
        symbol = symbol.upper()
        if symbol in self.price_histories and self.price_histories[symbol]:
            last = self.price_histories[symbol][-1]
            noise = random.uniform(-0.08, 0.08)
            fake_price = round(last * (1 + noise / 100), 6)
            self.price_histories[symbol].append(fake_price)
            if len(self.price_histories[symbol]) > 200:
                self.price_histories[symbol].pop(0)
            return {"price": fake_price, "volume": 20000}
        # Hardcoded defaults on cold start
        defaults = {
            "ETH": 3120.0, "SOL": 134.0, "AVAX": 28.5, "DOT": 6.8,
            "LINK": 13.7, "ATOM": 8.2, "UNI": 7.8, "BCH": 520.0
        }
        price = defaults.get(symbol, 100.0)
        self.price_histories[symbol].append(price)
        return {"price": price, "volume": 15000}
    async def place_order(self, symbol: str, side: str, amount: float, close_position: bool = False) -> Tuple[bool, float]:
        # Simulation mode
        if getattr(self, 'simulation', False):
            ticker = await self.get_ticker(symbol)
            price = ticker['price']
            if price <= 0:
                print(f"SIM ORDER FAILED {side} {symbol}")
                return False, 0
            filled_qty = amount / price
            print(f"SIMULATED {side.upper()} {filled_qty:.6f} {symbol} @ ${price:.4f} (${amount:.2f} USDT)")
            return True, filled_qty
        if not (self.api_key and self.secret_key):
            print(f"REAL ORDER SKIPPED {side} {symbol} — missing keys")
            return False, 0
        try:
            trading_pair = f"{symbol.upper()}_USD_PERP"
            ticker = await self.get_ticker(symbol)
            price = ticker['price']
            if price <= 0:
                return False, 0
            quantity = round(amount / price, 8)
            order_params = {
                "instrument_name": trading_pair,
                "side": side.upper(),
                "type": "MARKET",
                "quantity": str(quantity)
            }
            if close_position:
                order_params["exec_inst"] = ["REDUCE_ONLY"]
            params = {
                "id": int(time.time() * 1000),
                "method": "private/create-order",
                "api_key": self.api_key,
                "nonce": int(time.time() * 1000),
                "params": order_params
            }
            params['sig'] = self._sign_request(params)
            session = await self.get_session()
            async with session.post(
                    f"{self.base_url}/private/create-order",
                    json=params,
                    timeout=15
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"ORDER ERROR {resp.status}: {text[:200]}")
                    return False, 0
                data = await resp.json()
                if data.get("code") == 0:
                    print(f"REAL {side.upper()} ORDER EXECUTED: {symbol} @ ${price:.4f}")
                    return True, quantity
                else:
                    print(f"ORDER REJECTED: {data}")
                    return False, 0
        except Exception as e:
            print(f"ORDER EXCEPTION: {e}")
            return False, 0
def calculate_std_dev(numbers):
    if len(numbers) < 2:
        return 0.0
    mean = sum(numbers) / len(numbers)
    variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
    return variance ** 0.5
def calculate_correlation(x, y):
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denominator_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    denominator_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    if denominator_x == 0 or denominator_y == 0:
        return 0.0
    return numerator / (denominator_x * denominator_y)
class TechnicalAnalyzer:
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(change, 0) for change in changes[-period:]]
        losses = [max(-change, 0) for change in changes[-period:]]
        if not losses:
            return 100.0
        if not gains:
            return 0.0
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        return 100 - (100 / (1 + rs))
    def calculate_volatility(self, prices: List[float]) -> float:
        if len(prices) < 2:
            return 0.0
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        return calculate_std_dev(returns) * 100 if returns else 0.0
    def detect_trend(self, prices: List[float]) -> str:
        if len(prices) < 10:
            return "neutral"
        recent = prices[-10:]
        if recent[-1] > recent[0] * 1.02:
            return "bullish"
        elif recent[-1] < recent[0] * 0.98:
            return "bearish"
        return "neutral"
    def find_support_levels(self, prices: List[float], lookback: int = 50, threshold: float = 0.01) -> List[float]:
        if len(prices) < lookback:
            return []
        supports = []
        for i in range(lookback, len(prices)):
            if prices[i] <= min(prices[max(0, i - lookback):i + 1]):
                is_support = False
                for j in range(max(0, i - lookback), i):
                    if abs(prices[j] - prices[i]) / prices[i] < threshold:
                        is_support = True
                        break
                if is_support:
                    supports.append(prices[i])
        unique_supports = sorted(set(supports), key=lambda x: supports.count(x), reverse=True)
        return unique_supports[:3]
    def is_near_support(self, current_price: float, supports: List[float], tolerance: float = 0.01) -> bool:
        return any(abs(current_price - support) / support < tolerance for support in supports)
    def calculate_ema(self, prices: List[float], period: int = 5) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        ema = sum(prices[-period:]) / period
        multiplier = 2 / (period + 1)
        for price in prices[-period + 1:]:
            ema = (price - ema) * multiplier + ema
        return ema
class BitcoinCorrelationTracker:
    def __init__(self, api):
        self.api = api
        self.btc_prices = []
        self.altcoin_prices = {}
    async def get_btc_price(self) -> float:
        try:
            session = await self.api.get_session()
            async with session.get(
                    f"{self.api.base_url}/public/get-ticker?instrument_name=BTC_USD_PERP"
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    price = float(data["result"]["data"]["a"])
                    self.btc_prices.append(price)
                    if len(self.btc_prices) > 50:
                        self.btc_prices.pop(0)
                    return price
        except Exception as e:
            print(f"BTC direct fetch failed: {e}")
        return self.btc_prices[-1] if self.btc_prices else 92000.0
    def update_prices(self, symbol: str, price: float):
        symbol = symbol.upper()
        if symbol not in self.altcoin_prices:
            self.altcoin_prices[symbol] = []
        self.altcoin_prices[symbol].append(price)
        if len(self.altcoin_prices[symbol]) > 50:
            self.altcoin_prices[symbol].pop(0)
    def calculate_correlation(self, symbol: str) -> float:
        symbol = symbol.upper()
        if (symbol not in self.altcoin_prices or len(self.altcoin_prices[symbol]) < 10 or
                len(self.btc_prices) < 10):
            return 0.0
        min_len = min(len(self.altcoin_prices[symbol]), len(self.btc_prices))
        alt_prices = self.altcoin_prices[symbol][-min_len:]
        btc_prices = self.btc_prices[-min_len:]
        try:
            return calculate_correlation(alt_prices, btc_prices)
        except:
            return 0.0
class AltcoinSentimentAnalyzer:
    def __init__(self):
        self.technical = TechnicalAnalyzer()
    async def analyze_altcoin(self, symbol: str, current_price: float,
                              price_history: List[float], volume_history: List[float], current_volume: float,
                              btc_correlation: float, market_condition: str) -> Dict:
        if len(price_history) < 15:
            return {
                "advice": "Hold",
                "confidence": 0.0,
                "trend": "neutral",
                "rsi": 50.0,
                "volatility": 0.0,
                "btc_correlation": btc_correlation,
                "avg_volume": 0.0,
                "reason_short": "Insufficient data",
                "source": "TECHNICAL_ANALYSIS"
            }
        rsi = self.technical.calculate_rsi(price_history)
        volatility = self.technical.calculate_volatility(price_history)
        trend = self.technical.detect_trend(price_history)
        supports = self.technical.find_support_levels(price_history)
        avg_volume = sum(volume_history[-10:]) / 10 if len(volume_history) >= 10 else current_volume
        advice, confidence, reason = self._generate_market_signal(
            symbol, current_price, rsi, volatility, trend, btc_correlation, market_condition, supports, price_history,
            current_volume, avg_volume
        )
        return {
            "advice": advice,
            "confidence": confidence,
            "trend": trend,
            "rsi": rsi,
            "volatility": volatility,
            "btc_correlation": btc_correlation,
            "avg_volume": avg_volume,
            "reason_short": reason,
            "source": "TECHNICAL_ANALYSIS"
        }
    def _generate_market_signal(self, symbol: str, price: float, rsi: float,
                                volatility: float, trend: str, btc_correlation: float,
                                market_condition: str, supports: List[float],
                                price_history: Optional[List[float]] = None,
                                current_volume: float = 0.0,
                                avg_volume: float = 0.0) -> Tuple[str, float, str]:
        reasons: List[str] = []
        confidence: float = 0.0
        action = "HOLD"
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        hist = price_history or []
        if market_condition in ("bear", "extreme_bear"):
            # ====================== AGGRESSIVE DIP-BUY LOGIC ======================
            # Loosened for slow grind: catch small panic dips with mild volume
            if vol_ratio >= 1.2 and rsi < 48 and len(hist) >= 6:
                low_6 = min(hist[-6:])
                rebound_pct = (price / low_6 - 1) * 100
                if rebound_pct >= 0.3: # Tiny bounce off recent low is enough
                    confidence = 0.45 + (rebound_pct / 4.0) + (vol_ratio / 10.0)
                    confidence = min(1.0, confidence)
                    action = "BUY"
                    reasons.append(f"Dip rebound +{rebound_pct:.1f}% Vol×{vol_ratio:.1f} RSI{rsi:.0f}")
            # Deep oversold near support — strong long signal
            if rsi < 35 and len(supports) > 0:
                closest_support_dist = min(abs(price - s) / s for s in supports)
                if closest_support_dist < 0.02: # within 2%
                    confidence = max(confidence, 0.55)
                    action = "BUY"
                    reasons.append(f"Deep oversold RSI{rsi:.0f} near support")
            # ====================== AGGRESSIVE SHORT LOGIC ======================
            # Short any meaningful relief rally or FOMO spike in bear market
            pump_pct_5 = 0.0
            if len(hist) >= 5:
                pump_pct_5 = (price / hist[-5] - 1) * 100 # % gain over last ~5 candles
            pump_pct_3 = 0.0
            if len(hist) >= 3:
                pump_pct_3 = (price / hist[-3] - 1) * 100
            # Main short trigger: relief pump with volume or high RSI
            if pump_pct_5 >= 1.8 or (vol_ratio >= 1.4 and rsi > 55):
                confidence = 0.50
                if pump_pct_5 >= 3.0:
                    confidence += 0.20
                if pump_pct_5 >= 5.0:
                    confidence += 0.15
                if vol_ratio >= 1.8:
                    confidence += 0.15
                if rsi > 62:
                    confidence += 0.12
                if trend == "bearish":
                    confidence += 0.10
                confidence = min(1.0, confidence)
                action = "SELL"
                reasons.append(f"Relief rally +{pump_pct_5:.1f}% Vol×{vol_ratio:.1f} RSI{rsi:.0f}")
            # Secondary short: volume spike but price failing to hold gains (distribution)
            if rsi > 60 and vol_ratio >= 1.3 and len(hist) >= 3:
                if price < max(hist[-3:]): # failed to make new high
                    confidence = max(confidence, 0.58)
                    action = "SELL"
                    reasons.append(f"Fading pump - high RSI{rsi:.0f} + volume but rejection")
            # Bonus short: extreme overbought in bear
            if rsi > 75:
                confidence = max(confidence, 0.65)
                action = "SELL"
                reasons.append(f"Extreme overbought RSI{rsi:.0f} in bear")
        elif market_condition in ("bull", "extreme_bull"):
            # Original bull logic (unchanged - trend following)
            if rsi < 45 and trend == "bullish":
                confidence = 0.60
                action = "BUY"
                reasons.append(f"Bull dip RSI{rsi:.1f}")
            if rsi > 70:
                confidence = 0.60
                action = "SELL"
                reasons.append(f"Bull overbought RSI{rsi:.1f}")
        else: # neutral
            # Light contrarian plays
            if rsi < 35:
                confidence = 0.45
                action = "BUY"
                reasons.append(f"Neutral oversold RSI{rsi:.0f}")
            if rsi > 65:
                confidence = 0.45
                action = "SELL"
                reasons.append(f"Neutral overbought RSI{rsi:.0f}")
        # Final decision
        if confidence >= settings.CONFIDENCE_THRESHOLD:
            if not reasons:
                reasons.append("Anti-herd signal")
            return action, confidence, " | ".join(reasons)
        return "HOLD", 0.0, "Signal too weak"
class TelegramController:
    def __init__(self, bot):
        self.bot = bot
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.user_ids = settings.TELEGRAM_USER_IDS
        self.last_performance_report = 0
        self.performance_interval = 2 * 60 * 60
        self.last_update_id = 0
        self.polling_task = None
    def start_polling(self):
        if self.bot_token and self.user_ids:
            print(f"TELEGRAM: Connected to bot {self.bot_token[:10]}...")
            self.polling_task = asyncio.create_task(self.poll_telegram_commands())
        else:
            print("TELEGRAM: Missing token or user IDs")
    async def poll_telegram_commands(self):
        if not self.bot_token or not self.user_ids:
            print("TELEGRAM: Cannot start polling - missing token or user IDs")
            return
        print("Starting Telegram command polling...")
        retries = 0
        max_retries = 5
        while self.bot.running and retries < max_retries:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {
                    'offset': self.last_update_id + 1,
                    'timeout': 10,
                    'allowed_updates': ['message']
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=15) as response:
                        retries = 0
                        if response.status == 200:
                            data = await response.json()
                            if data.get('ok') and data.get('result'):
                                for update in data['result']:
                                    self.last_update_id = update['update_id']
                                    message = update.get('message', {})
                                    chat_id = message.get('chat', {}).get('id')
                                    text = message.get('text', '').strip()
                                    if (chat_id in self.user_ids and text and text.startswith('/')):
                                        print(f"Telegram command received: {text}")
                                        await self.handle_command(text)
                        else:
                            retries += 1
                await asyncio.sleep(1)
            except asyncio.TimeoutError:
                retries += 1
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Telegram polling error: {e}")
                retries += 1
                await asyncio.sleep(5)
        if retries >= max_retries:
            print("TELEGRAM: Max polling retries reached, stopping polling")
    async def send_telegram_message(self, message: str) -> bool:
        if not self.bot_token or not self.user_ids:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            for user_id in self.user_ids:
                try:
                    payload = {
                        'chat_id': user_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    async with session.post(url, json=payload, timeout=10) as response:
                        if response.status == 200:
                            print(f"Sent to {user_id}: {message[:50]}...")
                            return True
                except Exception as e:
                    print(f"Send error: {e}")
        return True
    def send_telegram_message_sync(self, message: str) -> bool:
        if not self.bot_token or not self.user_ids:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for user_id in self.user_ids:
            try:
                payload = {
                    'chat_id': user_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    print(f"Sent to {user_id}: {message[:50]}...")
                    return True
            except Exception as e:
                print(f"Sync send error: {e}")
        return True
    async def send_message(self, message: str):
        print(f"{message}")
        await self.send_telegram_message(message)
    async def handle_command(self, command: str):
        cmd = command.strip().lower()
        print(f"Processing command: {cmd}")
        if cmd == '/performance':
            await self.cmd_performance()
        elif cmd == '/status':
            await self.cmd_status()
        elif cmd == '/start':
            await self.cmd_start()
        elif cmd == '/pause':
            await self.cmd_pause()
        elif cmd == '/resume':
            await self.cmd_resume()
        elif cmd == '/help':
            await self.cmd_help()
        elif cmd == '/test':
            await self.cmd_test()
        elif cmd == '/forcesell':
            await self.cmd_force_sell()
        elif cmd == '/debug':
            await self.cmd_debug()
        elif cmd == '/ai_status':
            await self.cmd_ai_status()
        elif cmd == '/market_condition':
            await self.cmd_market_condition()
        elif cmd.startswith('/size '):
            try:
                percent = float(cmd.split()[1])
                if settings.MARKET_CONDITION == 'bull':
                    settings.TRADE_BASE_PERCENT_BULL = percent
                else:
                    settings.TRADE_BASE_PERCENT_BEAR = percent
                settings.TRADE_BASE_PERCENT = percent
                await self.send_message(
                    f"Trade size updated to {percent}% in {settings.MARKET_CONDITION.upper()} market")
            except:
                await self.send_message("Usage: /size 22")
        elif cmd == '/bull':
            settings.update_params('bull')
            await self.send_message("SWITCHED TO BULL MODE")
        elif cmd == '/bear':
            settings.update_params('bear')
            await self.send_message("SWITCHED TO BEAR MODE")
        elif cmd == '/params':
            await self.send_message(f"""PARAMS ({settings.MARKET_CONDITION.upper()})
Size: {settings.TRADE_BASE_PERCENT}%
Max Pos: {settings.MAX_POSITIONS}
Profit: {settings.PROFIT_TARGET}%
Stop: {settings.STOP_LOSS}%
Confidence: {settings.CONFIDENCE_THRESHOLD}
Timeout: {settings.POSITION_TIMEOUT}s""")
        elif cmd == '/grok':
            cooldown_left = max(0, 30 - (time.time() - self.bot.grok_analyzer.last_grok_call))
            calls = self.bot.grok_analyzer.request_count
            await self.send_message(f"Grok calls today: {calls}\nNext call in: {int(cooldown_left)}s")
        elif cmd == '/logs':
            await self.cmd_logs()
        else:
            await self.send_message(f"Unknown command: {cmd}")
    async def cmd_start(self):
        mode = "SIMULATION" if self.bot.simulation else "LIVE"
        api_status = "REAL API" if settings.CRYPTOCOM_API_KEY else "SIMULATION"
        ai_status = "ENABLED" if self.bot.grok_analyzer and self.bot.grok_analyzer.enabled else "DISABLED"
        market_condition = await self.bot.get_market_condition()
        await self.send_message(
            f"BOT STARTED\n"
            f"Mode: {mode}\n"
            f"Exchange: {api_status}\n"
            f"AI: {ai_status}\n"
            f"Market: {market_condition.upper()}\n"
            f"Balance: ${self.bot.balance:.2f}"
        )
    async def cmd_performance(self):
        try:
            performance_data = await self.bot.get_performance_data()
            message = self._format_performance_message(performance_data)
            await self.send_message(message)
        except Exception as e:
            await self.send_message(f"Error generating performance report: {str(e)}")
    async def cmd_status(self):
        active_positions = sum(1 for pos in self.bot.positions.values() if pos.qty != 0)
        api_status = "REAL API" if settings.CRYPTOCOM_API_KEY else "SIMULATION"
        ai_status = "ENABLED" if self.bot.grok_analyzer and self.bot.grok_analyzer.enabled else "DISABLED"
        market_condition = await self.bot.get_market_condition()
        await self.send_message(f"""BOT STATUS
Mode: {api_status}
AI Analysis: {ai_status}
Market Condition: {market_condition.upper()}
Balance: ${self.bot.balance:.2f}
Positions: {active_positions}/{settings.MAX_POSITIONS}
Trades Today: {self.bot.daily_trades}
Cycles: {self.bot.cycle_count}""")
    async def cmd_ai_status(self):
        if self.bot.grok_analyzer and self.bot.grok_analyzer.enabled:
            await self.send_message(f"GROK AI STATUS: ENABLED\nAPI Calls: {self.bot.grok_analyzer.request_count}")
        else:
            await self.send_message("GROK AI STATUS: DISABLED\nAdd GROK_API_KEY to .env to enable")
    async def cmd_market_condition(self):
        market_condition = await self.bot.get_market_condition()
        await self.send_message(f"MARKET CONDITION: {market_condition.upper()}")
    async def cmd_pause(self):
        self.bot.paused = True
        await self.send_message("TRADING PAUSED")
    async def cmd_resume(self):
        self.bot.paused = False
        await self.send_message("TRADING RESUMED")
    async def cmd_force_sell(self):
        sold_count = 0
        for symbol in list(self.bot.positions.keys()):
            if self.bot.positions[symbol].qty != 0:
                ticker = await self.bot.api.get_ticker(symbol)
                price = ticker['price']
                if price:
                    await self.bot.close_position(symbol, price, "FORCE CLOSE")
                    sold_count += 1
        await self.send_message(f"Force closed {sold_count} positions")
    async def cmd_debug(self):
        api_status = "REAL Crypto.com API" if settings.CRYPTOCOM_API_KEY else "SIMULATION MODE"
        ai_status = "ENABLED" if settings.GROK_API_KEY else "DISABLED"
        market_condition = await self.bot.get_market_condition()
        config_info = f"""BOT CONFIGURATION
Telegram: {'Connected' if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_USER_IDS else 'Missing'}
Exchange: {api_status}
Grok AI: {ai_status}
Market Condition: {market_condition.upper()}
Users: {settings.TELEGRAM_USER_IDS}
Balance: ${settings.INITIAL_CAPITAL}
Coins: {len(settings.symbols)}
Profit Target: {settings.PROFIT_TARGET}%
Stop Loss: {settings.STOP_LOSS}%"""
        await self.send_message(config_info)
    async def cmd_test(self):
        await self.send_message("Telegram test successful!")
    async def cmd_help(self):
        await self.send_message("""COMMANDS:
/start - Start bot
/performance - Performance report
/status - Bot status
/ai_status - Grok AI status
/market_condition - Current market condition
/pause - Pause trading
/resume - Resume trading
/forcesell - Close all positions
/test - Test Telegram connection
/debug - Show configuration
/size X - Set trade size to X%
/bull - Switch to bull mode
/bear - Switch to bear mode
/params - Show current params
/grok - Show Grok API status
/logs - Show recent trade logs""")
    async def cmd_logs(self):
        logs = "\n".join([f"{log['type'].upper()} {log['symbol']} @ {log['price']:.4f} - {log['reason']}" for log in
                          self.bot.trade_log[-10:]])
        await self.send_message(f"Recent Logs:\n{logs or 'No logs yet'}")
    def _format_performance_message(self, data: Dict) -> str:
        total_pnl_pct = data['total_pnl_pct']
        if total_pnl_pct > 2:
            market_condition = "STRONG BULL MARKET"
        elif total_pnl_pct > 0:
            market_condition = "BULL MARKET"
        elif total_pnl_pct > -2:
            market_condition = "BEAR MARKET"
        else:
            market_condition = "STRONG BEAR MARKET"
        uptime_minutes = data['uptime_minutes']
        if uptime_minutes < 60:
            uptime_str = f"{uptime_minutes:.0f}m"
        else:
            hours = uptime_minutes // 60
            minutes = uptime_minutes % 60
            uptime_str = f"{hours:.0f}h {minutes:.0f}m"
        positions_text = "No active positions"
        if data['active_positions']:
            positions_text = "\n".join(data['active_positions'])
        coin_performance = []
        for symbol, performance in data['coin_performance'].items():
            pnl_pct = performance['pnl_pct']
            icon = "+" if pnl_pct >= 0 else "-"
            if abs(pnl_pct) < 0.01:
                change_str = "0.0%"
            else:
                change_str = f"{pnl_pct:+.1f}%"
            coin_performance.append(f"{icon} {symbol}: {change_str}")
        coin_performance_text = "\n".join(coin_performance) if coin_performance else "No performance data yet"
        profit_factor = "N/A" if data['total_loss'] == 0 else f"{data['total_profit'] / data['total_loss']:.2f}"
        if uptime_minutes > 0:
            daily_multiplier = (24 * 60) / uptime_minutes
            projected_daily = total_pnl_pct * daily_multiplier
        else:
            projected_daily = 0
        avg_win = data['avg_win'] if 'avg_win' in data else 'N/A'
        avg_loss = data['avg_loss'] if 'avg_loss' in data else 'N/A'
        return f"""PERFORMANCE METRICS
Market Condition: {market_condition}
Uptime: {uptime_str} ({uptime_minutes:.0f} minutes)
Portfolio Value:
Initial: ${data['initial_capital']:.2f}
Current: ${data['current_value']:.2f}
PnL: ${data['total_pnl']:+.2f} ({total_pnl_pct:+.1f}%)
Active Positions:
{positions_text}
Coin Price Changes (since start):
{coin_performance_text}
Trading Stats:
Trades: {data['total_trades']} total, {data['daily_trades']} today
Win Rate: {data['win_rate']}
Profit Factor: {profit_factor}
Avg Win: {avg_win}
Avg Loss: {avg_loss}
Projected Daily: {projected_daily:+.1f}%"""
    async def check_periodic_report(self):
        current_time = time.time()
        if current_time - self.last_performance_report >= self.performance_interval:
            try:
                performance_data = await self.bot.get_performance_data()
                message = self._format_performance_message(performance_data)
                await self.send_message(f"PERIODIC REPORT (Every 2 hours)\n\n{message}")
                self.last_performance_report = current_time
            except Exception as e:
                await self.send_message(f"Error in periodic report: {str(e)}")
@dataclass
class Position:
    qty: float = 0.0 # Positive for long, negative for short
    entry: float = 0.0
    entry_time: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    partial_taken: bool = False
class AltcoinScalpBot:
    def __init__(self):
        self.api = CryptoComAPI()
        self.api.simulation = True
        self.ai = AltcoinSentimentAnalyzer()
        self.technical = TechnicalAnalyzer()
        self.btc_tracker = BitcoinCorrelationTracker(self.api)
        self.telegram = TelegramController(self)
        self.grok_analyzer = GrokAnalyzer()
        self.grok_permanently_dead = False
        self.price_api_permanently_dead = False
        self.order_failure_streak = 0
        self.MAX_ORDER_FAILURES = 3
        self.balance = settings.INITIAL_CAPITAL
        self.simulation = False
        self.positions = {s.upper(): Position() for s in settings.symbols}
        self.price_history = {s.upper(): [] for s in settings.symbols}
        self.volume_history = {s.upper(): [] for s in settings.symbols}
        self.initial_prices = {}
        self.trades = 0
        self.daily_trades = 0
        self.cycle_count = 0
        self.running = True
        self.paused = False
        self.wins = self.losses = 0
        self.win_rate = "0%"
        self.total_profit = self.total_loss = 0.0
        self.start_time = time.time()
        self.last_day_reset = self.start_time
        self.daily_trade_limit = 40
        self.console_task = None
        self.last_market_condition = settings.MARKET_CONDITION
        self.trade_log = []
        self.bear_shutdown = False
        self.start_console_handler()
        self.last_trade_time = 0.0
        self.threshold_adjust_interval = 3600
        self.last_adjust_time = time.time()
    def start_console_handler(self):
        self.console_task = asyncio.create_task(self.console_listener())
        print("Console ready - type /help for commands")
        print("Telegram commands available!")
    async def auto_tune_parameters(self):
        regime = await self.get_market_condition()
        if hasattr(self, 'current_regime') and self.current_regime == regime:
            return
        self.current_regime = regime
        if regime == "extreme_bear":
            settings.TRADE_BASE_PERCENT = 9.0
            settings.MAX_POSITIONS = 4
            settings.PROFIT_TARGET = 3.8
            settings.CONFIDENCE_THRESHOLD = 0.32
            settings.VOLUME_MULTIPLIER_REQUIRED = 1.3
            settings.MIN_REBOUND_REQUIRED = 0.5
            settings.MAX_RSI_FOR_LONG = 44
            name = "EXTREME BEAR - AGGRESSIVE GRIND MODE"
        elif regime == "bear":
            settings.TRADE_BASE_PERCENT = 8.0
            settings.MAX_POSITIONS = 4
            settings.PROFIT_TARGET = 4.2
            settings.CONFIDENCE_THRESHOLD = 0.35
            settings.VOLUME_MULTIPLIER_REQUIRED = 1.4
            settings.MIN_REBOUND_REQUIRED = 0.6
            settings.MAX_RSI_FOR_LONG = 42
            name = "BEAR - LOOSER DIP CATCHER"
        elif regime == "neutral":
            settings.TRADE_BASE_PERCENT = 7.0
            settings.MAX_POSITIONS = 4
            settings.PROFIT_TARGET = 3.1
            settings.STOP_LOSS = 1.7
            settings.CONFIDENCE_THRESHOLD = 0.52
            settings.POSITION_TIMEOUT = 4800
            settings.VOLUME_MULTIPLIER_REQUIRED = 2.1
            settings.MIN_REBOUND_REQUIRED = 0.9
            settings.MAX_RSI_FOR_LONG = 38
            name = "NEUTRAL — Balanced scalping"
        else:
            settings.TRADE_BASE_PERCENT = 14.0
            settings.MAX_POSITIONS = 6
            settings.PROFIT_TARGET = 2.6
            settings.STOP_LOSS = 2.2
            settings.CONFIDENCE_THRESHOLD = 0.58
            settings.POSITION_TIMEOUT = 3600
            settings.VOLUME_MULTIPLIER_REQUIRED = 1.6
            settings.MIN_REBOUND_REQUIRED = 0.4
            settings.MAX_RSI_FOR_LONG = 45
            name = "BULL MARKET — Trend-following mode"
        msg = f"REGIME → {name} | Size {settings.TRADE_BASE_PERCENT}% | Conf≥{settings.CONFIDENCE_THRESHOLD}"
        print(msg)
        await self.telegram.send_message(f"AUTO REGIME: {name}\n{msg}")
    async def run_cycle(self):
        self.cycle_count += 1
        if time.time() - self.last_day_reset > 86400:
            self.daily_trades = 0
            self.last_day_reset = time.time()
        await self.auto_tune_parameters()
        market_condition = await self.get_market_condition()
        if market_condition in ["bear", "extreme_bear"]:
            hours_no_trade = (time.time() - self.last_trade_time) / 3600
            if hours_no_trade > 24:
                settings.VOLUME_MULTIPLIER_REQUIRED = 1.6
                settings.MIN_REBOUND_REQUIRED = 0.7
                settings.MAX_RSI_FOR_LONG = 40
                settings.CONFIDENCE_THRESHOLD = 0.35
                if hours_no_trade > 36:
                    settings.VOLUME_MULTIPLIER_REQUIRED = 1.3
                    settings.MIN_REBOUND_REQUIRED = 0.4
                    settings.MAX_RSI_FOR_LONG = 45
        if self.paused:
            if self.cycle_count % 50 == 0:
                print("TRADING PAUSED — waiting for /resume")
            await asyncio.sleep(1)
            return
        for symbol in settings.symbols:
            try:
                ticker = await self.api.get_ticker(symbol)
                if not ticker or ticker['price'] <= 0:
                    continue
                price = ticker['price']
                volume = ticker['volume']
                symbol_upper = symbol.upper()
                self.price_history[symbol_upper].append(price)
                self.volume_history[symbol_upper].append(volume)
                if len(self.price_history[symbol_upper]) > 200:
                    self.price_history[symbol_upper].pop(0)
                    self.volume_history[symbol_upper].pop(0)
                self.btc_tracker.update_prices(symbol, price)
                tech_sentiment = await self.ai.analyze_altcoin(
                    symbol=symbol,
                    current_price=price,
                    price_history=self.price_history[symbol_upper],
                    volume_history=self.volume_history[symbol_upper],
                    current_volume=volume,
                    btc_correlation=self.btc_tracker.calculate_correlation(symbol),
                    market_condition=market_condition
                )
                final_sentiment = tech_sentiment
                if (self.grok_analyzer.enabled and
                        time.time() - self.grok_analyzer.last_grok_call > 25 and
                        tech_sentiment['confidence'] > 0.3):
                    try:
                        grok_data = await self.grok_analyzer.comprehensive_analysis(symbol, {
                            'current_price': price,
                            'rsi': tech_sentiment['rsi'],
                            'volatility': tech_sentiment['volatility'],
                            'trend': tech_sentiment['trend'],
                            'btc_correlation': tech_sentiment['btc_correlation'],
                            'supports': self.ai.technical.find_support_levels(self.price_history[symbol_upper]),
                            'market_condition': market_condition
                        })
                        if grok_data['confidence'] > tech_sentiment['confidence']:
                            final_sentiment = grok_data
                            final_sentiment['source'] = 'GROK_AI'
                    except Exception as e:
                        print(f"Grok failed for {symbol}: {e}")
                await self.display_altcoin_analysis(symbol, price, final_sentiment)
                await self.execute_market_logic(symbol, price, volume, final_sentiment)
            except Exception as e:
                print(f"Error in cycle for {symbol}: {e}")
        await self.telegram.check_periodic_report()
        if time.time() - self.last_adjust_time > self.threshold_adjust_interval:
            time_since_last_trade = time.time() - self.last_trade_time if self.last_trade_time > 0 else time.time() - self.start_time
            if time_since_last_trade > self.threshold_adjust_interval:
                current_threshold = settings.CONFIDENCE_THRESHOLD
                new_threshold = max(0.1, current_threshold - 0.05)
                if new_threshold < current_threshold:
                    settings.CONFIDENCE_THRESHOLD = new_threshold
                    msg = f"No trades for {time_since_last_trade / 3600:.1f} hours → Lowered confidence threshold to {new_threshold} for {market_condition.upper()} mode"
                    print(msg)
                    await self.telegram.send_message(msg)
            self.last_adjust_time = time.time()
        await asyncio.sleep(settings.CYCLE_DELAY)
    async def console_listener(self):
        while self.running:
            try:
                command = await asyncio.to_thread(input, "")
                if command and command.startswith('/'):
                    print(f"DEBUG: Console command received: {command}")
                    await self.telegram.handle_command(command.strip())
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"Console error: {e}")
                await asyncio.sleep(1)
    async def init(self):
        if self.simulation:
            self.balance = settings.SIM_BALANCE
            self._initial_total = settings.SIM_BALANCE
            print(f"SIMULATION MODE: ${self.balance:.2f}")
        else:
            try:
                balances = await self.api.get_balances()
                self.balance = balances.get("USDT", settings.INITIAL_CAPITAL)
                self._initial_total = self.balance
                positions = await self.api.get_positions()
                for symbol, pos in positions.items():
                    self.positions[symbol.upper()] = Position(qty=pos['qty'], entry=pos['entry'], entry_time=time.time())
            except Exception as e:
                print(f"Failed to fetch balances/positions: {e}")
                self.balance = settings.INITIAL_CAPITAL
                self._initial_total = settings.INITIAL_CAPITAL
        self.telegram.start_polling()
        print("Fetching REAL market data from Crypto.com Derivatives...")
        valid_symbols = []
        for symbol in settings.symbols:
            try:
                ticker = await self.api.get_ticker(symbol)
                if ticker and ticker.get('price') > 0:
                    valid_symbols.append(symbol)
                else:
                    print(f"Skipping invalid ticker: {symbol} (no data)")
            except Exception as e:
                print(f"Skipping invalid ticker: {symbol} ({e})")
        settings.TRADING_SYMBOLS = ','.join(valid_symbols)
        settings.symbols = [s.upper() for s in valid_symbols]
        successful_fetches = 0
        for i in range(100):
            if not self.running:
                break
            print(f" Loading historical data... {i + 1}/100")
            try:
                btc_price = await self.btc_tracker.get_btc_price()
                fetch_success = False
                for symbol in settings.symbols:
                    try:
                        ticker = await self.api.get_ticker(symbol)
                        if ticker['price'] > 0:
                            self.price_history[symbol].append(ticker['price'])
                            self.volume_history[symbol].append(ticker['volume'])
                            self.btc_tracker.update_prices(symbol, ticker['price'])
                            if i == 0:
                                print(f" {symbol}: {ticker['price']:.4f}")
                            fetch_success = True
                    except Exception as e:
                        print(f"Error fetching ticker for {symbol}: {e}")
                        continue
                if fetch_success:
                    successful_fetches += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Error in data fetch loop: {e}")
                continue
        await self.update_initial_prices()
        mode = "SIMULATION" if self.simulation else "LIVE"
        api_status = "REAL API" if settings.CRYPTOCOM_API_KEY else "SIMULATION"
        ai_status = "ENABLED" if self.grok_analyzer.enabled else "DISABLED"
        market_condition = await self.get_market_condition()
        await self.telegram.send_message(
            f"BOT STARTED - ANTI-HERD MODE WITH SHORTING\n"
            f"Mode: {mode}\n"
            f"Exchange: {api_status}\n"
            f"AI: {ai_status}\n"
            f"Market: {market_condition.upper()}\n"
            f"Balance: ${self.balance:.2f}"
        )
        print(f"\nBOT READY | Balance: ${self.balance:.2f}")
        print(f"Using: {api_status}")
        print(f"Grok AI: {ai_status}")
        print(f"Market Condition: {market_condition.upper()}")
        print(f"OPTIMIZED: 15 TRADES/DAY, {settings.TRADE_BASE_PERCENT}% SIZING, ANTI-HERD POWER WITH SHORTS")
        print("Telegram notifications enabled")
        print("Watching for panic dips to long and FOMO spikes to short...")
        print("=" * 60)
    async def update_initial_prices(self):
        for symbol in settings.symbols:
            try:
                ticker = await self.api.get_ticker(symbol)
                if ticker['price']:
                    self.initial_prices[symbol] = ticker['price']
            except Exception as e:
                print(f"Error updating initial price for {symbol}: {e}")
    async def get_market_condition(self) -> str:
        if len(self.btc_tracker.btc_prices) < 20:
            return "bear"
        prices = self.btc_tracker.btc_prices
        p2h = prices[-120:] if len(prices) >= 120 else prices
        p6h = prices[-360:] if len(prices) >= 360 else prices
        p24h = prices[-1440:] if len(prices) >= 1440 else prices
        change_2h = (p2h[-1] - p2h[0]) / p2h[0] * 100
        change_6h = (p6h[-1] - p6h[0]) / p6h[0] * 100
        change_24h = (p24h[-1] - p24h[0]) / p24h[0] * 100
        green_alts = 0
        for symbol in settings.symbols:
            hist = self.price_history[symbol]
            if len(hist) >= 20:
                if hist[-1] > hist[-20] * 1.008:
                    green_alts += 1
        breadth = green_alts / len(settings.symbols)
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get("https://api.alternative.me/fng/?limit=2") as r:
                    if r.status == 200:
                        fng = int((await r.json())["data"][0]["value"])
                    else:
                        fng = 50
        except:
            fng = 50
        if (change_2h < -3.5 or change_6h < -6 or fng < 25 or change_24h < -15):
            return "extreme_bear"
        if (change_2h < -1.2 or change_6h < -3 or fng < 38 or breadth < 0.25):
            return "bear"
        if (change_2h > 3 or change_6h > 7 or fng > 72 or breadth > 0.65):
            return "extreme_bull"
        if (change_2h > 1.0 or change_6h > 2.5 or fng > 62):
            return "bull"
        return "neutral"
    async def enhanced_analysis(self, symbol: str, price: float, technical_sentiment: Dict,
                                market_condition: str) -> Dict:
        if not self.grok_analyzer.enabled:
            if not self.grok_permanently_dead:
                self.grok_permanently_dead = True
                await self.telegram.send_message(
                    "GROK API IS PERMANENTLY DEAD (404/ERROR)\n"
                    "BOT STOPPED FOR SAFETY\n"
                    "Fix GROK_API_KEY or remove Grok dependency"
                )
                print("GROK API DEAD → EMERGENCY SHUTDOWN INITIATED")
                self.running = False
            return technical_sentiment
        confidence = 0.0
        reasons = ["ANTI-HERD OVERRIDE — GROK DEAD"]
        price_hist = self.price_history[symbol.upper()]
        rsi = technical_sentiment['rsi']
        if rsi < 36 and len(price_hist) >= 6:
            if price > min(price_hist[-6:]) * 1.007:
                confidence = 0.92
                reasons.append("BLOOD IN THE STREETS +0.7% off low")
            elif price > min(price_hist[-4:]) * 1.005:
                confidence = 0.85
                reasons.append("Strong micro-rebound")
        if len(price_hist) >= 5:
            recent = (price - price_hist[-2]) / price_hist[-2]
            if recent < -0.008:
                confidence += 0.3
                reasons.append(f"PANIC DUMP {recent*100:+.2f}%")
        technical_sentiment['confidence'] = confidence
        technical_sentiment['reason_short'] = " | ".join(reasons)
        technical_sentiment['advice'] = "Buy" if confidence > 0.5 else "Hold"
        return technical_sentiment
    async def display_altcoin_analysis(self, symbol: str, price: float, sentiment: Dict):
        pos = self.positions[symbol.upper()]
        has_position = pos.qty != 0
        change_since_start = 0.0
        if symbol.upper() in self.initial_prices:
            initial_price = self.initial_prices[symbol.upper()]
            change_since_start = ((price - initial_price) / initial_price * 100) if initial_price > 0 else 0
        icon = "+" if sentiment["advice"] == "BUY" else "-" if sentiment["advice"] == "SELL" else "o"
        source_icon = "G" if sentiment.get('source') == 'GROK_AI' else "T"
        if has_position or sentiment["confidence"] > 0.5:
            print(
                f"{source_icon} {symbol}: {price:.4f} ({change_since_start:+.1f}%) {icon} {sentiment['advice']} | Conf: {sentiment['confidence']:.1%} | RSI: {sentiment['rsi']:.1f}")
    async def execute_market_logic(self, symbol: str, price: float, current_volume: float, sentiment: Dict):
        symbol_upper = symbol.upper()
        pos = self.positions[symbol_upper]
        has_position = pos.qty != 0
        if has_position:
            if pos.qty > 0: # Long
                pnl_pct = (price - pos.entry) / pos.entry * 100
            else: # Short
                pnl_pct = (pos.entry - price) / pos.entry * 100
            time_in_position = time.time() - pos.entry_time
            if pnl_pct <= -settings.MAX_DRAWDOWN_PER_TRADE:
                await self.close_position(symbol, price, f"MAX DRAWDOWN -{settings.MAX_DRAWDOWN_PER_TRADE}%")
                return
            if pos.qty > 0:
                pos.highest_price = max(pos.highest_price, price)
            else:
                pos.lowest_price = min(pos.lowest_price, price) if pos.lowest_price else price
            adjusted_stop = settings.STOP_LOSS + (sentiment['volatility'] / 100 * 0.4)
            exit_reasons = []
            if pnl_pct >= settings.PROFIT_TARGET:
                exit_reasons.append(f"Target +{settings.PROFIT_TARGET}%")
            if pnl_pct <= -adjusted_stop:
                exit_reasons.append(f"Stop loss ({pnl_pct:+.2f}%)")
            if time_in_position > settings.POSITION_TIMEOUT:
                exit_reasons.append("Timeout")
            if exit_reasons:
                await self.close_position(symbol, price, " | ".join(exit_reasons))
                return
        elif self.get_active_positions_count() < settings.MAX_POSITIONS and self.balance >= 60:
            hist = self.price_history[symbol_upper]
            if len(hist) < 10:
                return
            if sentiment['advice'] == "BUY" and sentiment['confidence'] >= settings.CONFIDENCE_THRESHOLD:
                await self.open_long(symbol, price, sentiment['reason_short'])
            elif sentiment['advice'] == "SELL" and sentiment['confidence'] >= settings.CONFIDENCE_THRESHOLD:
                await self.open_short(symbol, price, sentiment['reason_short'])
    async def get_performance_data(self) -> Dict:
        current_time = time.time()
        uptime_minutes = (current_time - self.start_time) / 60
        portfolio_value = self.balance
        active_positions = []
        for symbol, pos in self.positions.items():
            if pos.qty != 0:
                current_price = self.price_history[symbol][-1] if self.price_history.get(symbol) else pos.entry
                if pos.qty > 0:
                    pnl_dollar = (current_price - pos.entry) * pos.qty
                else:
                    pnl_dollar = (pos.entry - current_price) * abs(pos.qty)
                pnl_pct = pnl_dollar / (pos.entry * abs(pos.qty)) * 100
                portfolio_value += pnl_dollar
                active_positions.append(f"{symbol}: ${pnl_dollar:+.2f} ({pnl_pct:+.1f}%) {'Long' if pos.qty >0 else 'Short'}")
        total_pnl = portfolio_value - getattr(self, '_initial_total', self.balance)
        total_pnl_pct = (total_pnl / self._initial_total) * 100 if hasattr(self, '_initial_total') and self._initial_total > 0 else 0.0
        coin_performance = {}
        for symbol in settings.symbols:
            if symbol in self.initial_prices and self.initial_prices[symbol] > 0:
                if self.price_history.get(symbol) and len(self.price_history[symbol]) > 0:
                    current_price = self.price_history[symbol][-1]
                else:
                    current_price = self.initial_prices[symbol]
                pnl_pct = ((current_price - self.initial_prices[symbol]) / self.initial_prices[symbol]) * 100
                if abs(pnl_pct) < 0.01:
                    pnl_pct = 0.0
                coin_performance[symbol] = {'pnl_pct': pnl_pct}
        avg_win = self.total_profit / self.wins if self.wins > 0 else 0
        avg_loss = self.total_loss / self.losses if self.losses > 0 else 0
        return {
            'market_condition': 'bull' if total_pnl_pct > 0 else 'bear',
            'uptime_minutes': uptime_minutes,
            'initial_capital': getattr(self, '_initial_total', self.balance),
            'current_value': portfolio_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'active_positions': active_positions,
            'coin_performance': coin_performance,
            'total_trades': self.trades,
            'daily_trades': self.daily_trades,
            'win_rate': self.win_rate,
            'total_profit': self.total_profit,
            'total_loss': self.total_loss,
            'avg_win': f"${avg_win:.2f}",
            'avg_loss': f"${avg_loss:.2f}"
        }
    def get_active_positions_count(self):
        return sum(1 for pos in self.positions.values() if pos.qty != 0)
    async def open_long(self, symbol: str, price: float, reason: str):
        if self.balance < 60:
            print(f"Insufficient balance for {symbol}")
            return False
        cost = self.balance * (settings.TRADE_BASE_PERCENT / 100)
        cost = max(cost, 40)
        fee = cost * settings.FEE_RATE
        cost += fee
        if cost > self.balance:
            print(f"Insufficient balance after fee for {symbol}")
            return False
        qty = (cost - fee) / price
        self.balance -= cost
        self.positions[symbol.upper()] = Position(qty=qty, entry=price, entry_time=time.time(), highest_price=price)
        self.trades += 1
        self.daily_trades += 1
        self.last_trade_time = time.time()
        self.trade_log.append(
            {'type': 'open_long', 'symbol': symbol, 'price': price, 'qty': qty, 'cost': cost, 'reason': reason})
        print(f"OPEN LONG {symbol} {qty:.4f} @ {price:.4f} | {cost:.0f} ({settings.TRADE_BASE_PERCENT}%) | {reason}")
        await self.telegram.send_message(
            f"OPEN LONG {symbol} @ {price:.4f}\n"
            f"Size: {cost:.0f} ({settings.TRADE_BASE_PERCENT}% of balance)\n"
            f"Reason: {reason}"
        )
        success, filled_qty = await self.api.place_order(symbol, "BUY", cost)
        if not success:
            self.order_failure_streak += 1
            if self.order_failure_streak >= self.MAX_ORDER_FAILURES:
                await self.telegram.send_message("3 CONSECUTIVE ORDER FAILURES → EMERGENCY SHUTDOWN")
                self.running = False
            return False
        else:
            self.order_failure_streak = 0
        return True
    async def open_short(self, symbol: str, price: float, reason: str):
        if self.balance < 60:
            print(f"Insufficient balance for {symbol}")
            return False
        cost = self.balance * (settings.TRADE_BASE_PERCENT / 100)
        cost = max(cost, 40)
        fee = cost * settings.FEE_RATE
        cost += fee
        if cost > self.balance:
            print(f"Insufficient balance after fee for {symbol}")
            return False
        qty = (cost - fee) / price
        self.balance -= cost
        self.positions[symbol.upper()] = Position(qty=-qty, entry=price, entry_time=time.time(), lowest_price=price)
        self.trades += 1
        self.daily_trades += 1
        self.last_trade_time = time.time()
        self.trade_log.append(
            {'type': 'open_short', 'symbol': symbol, 'price': price, 'qty': qty, 'cost': cost, 'reason': reason})
        print(f"OPEN SHORT {symbol} {qty:.4f} @ {price:.4f} | {cost:.0f} ({settings.TRADE_BASE_PERCENT}%) | {reason}")
        await self.telegram.send_message(
            f"OPEN SHORT {symbol} @ {price:.4f}\n"
            f"Size: {cost:.0f} ({settings.TRADE_BASE_PERCENT}% of balance)\n"
            f"Reason: {reason}"
        )
        success, filled_qty = await self.api.place_order(symbol, "SELL", cost)
        if not success:
            self.order_failure_streak += 1
            if self.order_failure_streak >= self.MAX_ORDER_FAILURES:
                await self.telegram.send_message("3 CONSECUTIVE ORDER FAILURES → EMERGENCY SHUTDOWN")
                self.running = False
            return False
        else:
            self.order_failure_streak = 0
        return True
    async def close_position(self, symbol: str, price: float, reason: str, partial: bool = False):
        pos = self.positions[symbol.upper()]
        if pos.qty == 0:
            print(f"No position to close for {symbol}")
            return False
        close_qty = abs(pos.qty) / 2 if partial else abs(pos.qty)
        side = "SELL" if pos.qty > 0 else "BUY"
        proceeds = close_qty * price
        fee = proceeds * settings.FEE_RATE
        proceeds -= fee
        if pos.qty > 0:
            profit = (price - pos.entry) * close_qty
        else:
            profit = (pos.entry - price) * close_qty
        self.balance += proceeds
        self.trades += 1 if not partial else 0
        self.daily_trades += 1 if not partial else 0
        self.last_trade_time = time.time()
        if profit > 0:
            self.wins += 1 if not partial else 0
            self.total_profit += profit
        else:
            self.losses += 1 if not partial else 0
            self.total_loss += abs(profit)
        total_trades = self.wins + self.losses
        if total_trades > 0:
            self.win_rate = f"{(self.wins / total_trades * 100):.1f}%"
        profit_str = f"+{profit:.2f}" if profit >= 0 else f"-{abs(profit):.2f}"
        print(f"CLOSE {side} {symbol} @ ${price:.4f} | PnL: {profit_str} | Reason: {reason}")
        self.trade_log.append({
            'type': 'close',
            'symbol': symbol,
            'price': price,
            'qty': close_qty,
            'proceeds': proceeds,
            'profit': profit,
            'reason': reason
        })
        if partial:
            pos.qty = pos.qty / 2 if pos.qty > 0 else pos.qty / 2
        else:
            self.positions[symbol.upper()] = Position()
        success, _ = await self.api.place_order(symbol, side, proceeds, close_position=True)
        if not success:
            self.order_failure_streak += 1
            if self.order_failure_streak >= self.MAX_ORDER_FAILURES:
                await self.telegram.send_message("3 CONSECUTIVE ORDER FAILURES → EMERGENCY SHUTDOWN")
                self.running = False
            return False
        else:
            self.order_failure_streak = 0
        return True
    async def stop(self):
        self.running = False
        if self.console_task:
            self.console_task.cancel()
            try:
                await self.console_task
            except asyncio.CancelledError:
                pass
        if self.telegram.polling_task:
            self.telegram.polling_task.cancel()
            try:
                await self.telegram.polling_task
            except asyncio.CancelledError:
                pass
        self.telegram.send_telegram_message_sync("BOT STOPPED")
        print("Bot shutdown complete")
async def trading_loop(bot: AltcoinScalpBot):
    print("\nTRADING LOOP STARTED — Anti-Herd Bear Scalper with Shorting ACTIVE")
    print("=" * 70)
    while bot.running:
        try:
            await bot.run_cycle()
        except asyncio.CancelledError:
            print("\nTrading loop cancelled — shutting down gracefully...")
            break
        except Exception as e:
            error_msg = f"UNHANDLED ERROR in trading loop: {type(e).__name__}: {e}"
            print(f"\n{error_msg}")
            import traceback
            traceback.print_exc()
            await bot.telegram.send_message(f"LOOP CRASH: {type(e).__name__}\n{e}\nBot auto-restarting in 15s...")
            await asyncio.sleep(15)
    print("Trading loop ended.")
async def main():
    bot = AltcoinScalpBot()
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", action="store_true", help="Simulation mode (ignores API keys)")
    parser.add_argument("--real", action="store_true", help="Real trading mode (uses API keys)")
    args = parser.parse_args()
    bot.simulation = args.sim or not (settings.CRYPTOCOM_API_KEY and settings.CRYPTOCOM_SECRET_KEY)
    if args.real and settings.CRYPTOCOM_API_KEY:
        print("STARTING WITH REAL CRYPTO.COM DERIVATIVES API!")
        print(f"API Key: {settings.CRYPTOCOM_API_KEY[:10]}...")
    else:
        print("STARTING IN SIMULATION MODE")
        if not settings.CRYPTOCOM_API_KEY:
            print("Tip: Add your Crypto.com API keys to .env for real prices!")
    if settings.GROK_API_KEY:
        print("GROK AI: ENABLED - AI-powered analysis active (30-sec calls)")
    else:
        print("GROK AI: DISABLED - Add GROK_API_KEY to .env for AI analysis")
    print(f"OPTIMIZED: 15 TRADES/DAY, 1% RISK SIZING")
    print("TELEGRAM: Notifications enabled")
    try:
        await bot.init()
        await trading_loop(bot)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await bot.stop()
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped")
    except Exception as e:
        print(f"Startup error: {e}")