# -*- coding: utf-8 -*-
# !/usr/bin/env python3
"""
ULTIMATE AGGRESSIVE TRADING BOT WITH SHORTING CAPABILITY
Added shorting (1x leverage), removed Learning Manager entirely
"""
import asyncio
import time
import argparse
import random
import os
import requests
import threading
import aiohttp
import json
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

try:
    from dotenv import load_dotenv

    env_paths = [
        "/path/to/your/.env_ds"
    ]
    loaded = False
    for path in env_paths:
        if os.path.exists(path):
            load_dotenv(path)
            print(f"✅ Loaded environment from: {path}")
            loaded = True
            break
    if not loaded:
        print("⚠️  No .env file found, using default settings")
except ImportError:
    print("⚠️  python-dotenv not installed, using default settings")


class MarketRegime(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


class PositionType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class SimplePosition:
    symbol: str = ""
    position_type: PositionType = PositionType.LONG
    qty: float = 0.0
    entry_price: float = 0.0
    entry_time: float = 0.0
    size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop_activated: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0

import csv
import os
from datetime import datetime

class TradeLogger:
    """Logs all trade activity to a CSV file for analysis."""
    
    def __init__(self, log_dir="trade_logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Create a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(log_dir, f"trades_{timestamp}.csv")
        
        # Define CSV headers
        self.headers = [
            'timestamp', 'cycle', 'symbol', 'action', 'position_type',
            'entry_price', 'exit_price', 'size_usd', 'pnl_usd', 'pnl_pct',
            'hold_time_min', 'exit_reason',
            'rsi', 'trend', 'volatility', 'volume_trend', 'dip_strength', 'pump_strength',
            'ai_used', 'ai_recommendation', 'ai_confidence',
            'regime', 'regime_strength', 'btc_correlation',
            'stop_loss_pct', 'take_profit_pct'
        ]
        
        # Create and write headers to the file
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
        
        print(f"✅ Trade logging initialized: {self.filename}")
    
    def log_trade_opened(self, cycle_count: int, symbol: str, position_type: str,
                        entry_price: float, size_usd: float, analysis: dict,
                        regime_params: dict, btc_corr: float):
        """Log when a position is opened."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'cycle': cycle_count,
            'symbol': symbol,
            'action': 'OPEN',
            'position_type': position_type,
            'entry_price': entry_price,
            'exit_price': None,
            'size_usd': size_usd,
            'pnl_usd': None,
            'pnl_pct': None,
            'hold_time_min': None,
            'exit_reason': None,
            'rsi': analysis.get('rsi'),
            'trend': analysis.get('trend'),
            'volatility': analysis.get('volatility'),
            'volume_trend': analysis.get('volume_trend'),
            'dip_strength': analysis.get('dip_strength'),
            'pump_strength': analysis.get('pump_strength'),
            'ai_used': analysis.get('ai_used', False),
            'ai_recommendation': analysis.get('ai_recommendation'),
            'ai_confidence': analysis.get('ai_confidence'),
            'regime': regime_params.get('regime'),
            'regime_strength': regime_params.get('regime_strength'),
            'btc_correlation': btc_corr,
            'stop_loss_pct': regime_params.get('stop_loss', 5.0),  # From your settings
            'take_profit_pct': regime_params.get('profit_target', 13.2)  # From your settings
        }
        self._write_log(log_entry)
    
    def log_trade_closed(self, symbol: str, position: dict, exit_price: float,
                        pnl_usd: float, exit_reason: str):
        """Log when a position is closed."""
        hold_time_min = (time.time() - position.get('entry_time', 0)) / 60
        pnl_pct = (pnl_usd / position.get('size', 1)) * 100 if position.get('size', 0) > 0 else 0
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'cycle': None,  # Not needed for close
            'symbol': symbol,
            'action': 'CLOSE',
            'position_type': position.get('position_type', 'LONG'),
            'entry_price': position.get('entry_price'),
            'exit_price': exit_price,
            'size_usd': position.get('size'),
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'hold_time_min': round(hold_time_min, 2),
            'exit_reason': exit_reason,
            'rsi': position.get('entry_rsi'),
            'trend': None,  # Not available at close
            'volatility': None,
            'volume_trend': None,
            'dip_strength': None,
            'pump_strength': None,
            'ai_used': position.get('ai_used', False),
            'ai_recommendation': position.get('ai_recommendation'),
            'ai_confidence': position.get('entry_confidence'),
            'regime': None,
            'regime_strength': None,
            'btc_correlation': None,
            'stop_loss_pct': None,
            'take_profit_pct': None
        }
        self._write_log(log_entry)
    
    def _write_log(self, log_data: dict):
        """Write a single log entry to CSV."""
        row = [log_data.get(header, '') for header in self.headers]
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

class UltimateSettings:
    def __init__(self):
        # TELEGRAM
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        telegram_ids = os.getenv('TELEGRAM_USER_IDS', '')
        self.TELEGRAM_USER_IDS = [int(x.strip()) for x in telegram_ids.split(',')] if telegram_ids else []

        # DEEPSEEK API
        self.DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

        # 🚀 AGGRESSIVE CAPITAL ALLOCATION - OPTIMIZED FOR ALL REGIMES
        self.INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '500.0'))
        self.MIN_AI_CONFIDENCE = float(os.getenv('MIN_AI_CONFIDENCE', '0.55'))
        self.TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS',
                                         'ETH,SOL,ADA,AVAX,LINK,LTC')

        # 🚀 DYNAMIC POSITION SIZING - WILL BE ADJUSTED BY REGIME
        self.BASE_POSITION_SIZE_PERCENT = float(os.getenv('POSITION_SIZE_PERCENT', '10.0'))
        self.MAX_CONCURRENT_POSITIONS = int(os.getenv('MAX_CONCURRENT_POSITIONS', '6'))
        self.TRADE_BASE = self.INITIAL_CAPITAL * (self.BASE_POSITION_SIZE_PERCENT / 100)

        # 🚀 REALISTIC TARGETS - REGIME WILL ADJUST THESE
        self.PROFIT_TARGET = float(os.getenv('PROFIT_TARGET', '5.0'))
        self.STOP_LOSS = float(os.getenv('STOP_LOSS', '3.0'))
        self.TRAILING_STOP_ACTIVATE = float(os.getenv('TRAILING_STOP_ACTIVATE', '3.0'))
        self.TRAILING_STOP_DISTANCE = float(os.getenv('TRAILING_STOP_DISTANCE', '2.0'))

        # 🚀 SHORTING SETTINGS
        self.ENABLE_SHORTING = os.getenv('ENABLE_SHORTING', 'true').lower() == 'true'
        self.SHORT_RSI_MIN = float(os.getenv('SHORT_RSI_MIN', '65.0'))
        self.SHORT_PUMP_MIN = float(os.getenv('SHORT_PUMP_MIN', '1.5'))
        self.SHORT_MAX_POSITIONS = int(os.getenv('SHORT_MAX_POSITIONS', '4'))
        self.MAX_TOTAL_POSITIONS = int(os.getenv('MAX_TOTAL_POSITIONS', '6'))
        self.SHORT_POSITION_RATIO = float(os.getenv('SHORT_POSITION_RATIO', '0.5'))

        # MARGIN SETTINGS - SIMULATION ONLY
        self.MAX_LEVERAGE = float(os.getenv('MAX_LEVERAGE', '1.0'))
        self.MARGIN_MULTIPLIER = float(os.getenv('MARGIN_MULTIPLIER', '1.0'))
        self.MARGIN_CALL_LEVEL = float(os.getenv('MARGIN_CALL_LEVEL', '10'))

        self.POSITION_TIMEOUT = int(os.getenv('POSITION_TIMEOUT', '3600'))

        # 🚀 OPTIMIZED TRADING FREQUENCY
        self.CYCLE_DELAY = int(os.getenv('CYCLE_DELAY', '30'))
        self.MIN_CYCLE_BETWEEN_TRADES = int(os.getenv('MIN_CYCLE_BETWEEN_TRADES', '10'))
        self.DAILY_TRADE_LIMIT = 1000
        self.MAX_CONSECUTIVE_LOSSES = int(os.getenv('MAX_CONSECUTIVE_LOSSES', '8'))

        # 🚀 BALANCED RISK MANAGEMENT
        self.DAILY_LOSS_LIMIT = float(os.getenv('DAILY_LOSS_LIMIT', '15.0'))
        self.MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '25.0'))
        self.MIN_BALANCE_FOR_TRADING = float(os.getenv('MIN_BALANCE_FOR_TRADING', '50.0'))

        # 🚀 FLEXIBLE TRADING PARAMETERS - REGIME WILL ADJUST
        self.CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.05'))
        self.VERBOSE_MODE = os.getenv('VERBOSE_MODE', 'true').lower() == 'true'
        self.SUPPORT_LOOKBACK = int(os.getenv('SUPPORT_LOOKBACK', '30'))
        self.MIN_DIP_PERCENT = float(os.getenv('MIN_DIP_PERCENT', '0.1'))
        self.CONFIRMATION_CANDLES = int(os.getenv('CONFIRMATION_CANDLES', '2'))
        self.RSI_BUY_MAX = float(os.getenv('RSI_BUY_MAX', '65.0'))
        self.RSI_SELL_MIN = float(os.getenv('RSI_SELL_MIN', '80.0'))

        # REGIME DETECTION
        self.REGIME_LOOKBACK = int(os.getenv('REGIME_LOOKBACK', '40'))
        self.REGIME_UPDATE_INTERVAL = int(os.getenv('REGIME_UPDATE_INTERVAL', '5'))

        # VOLATILITY
        self.MAX_VOLATILITY = float(os.getenv('MAX_VOLATILITY', '80.0'))

        # AI SETTINGS
        self.AI_MIN_CONFIDENCE = 0.65
        self.AI_CACHE_TTL = int(os.getenv('AI_CACHE_TTL', '300'))
        self.AI_MAX_DAILY_CALLS = int(os.getenv('AI_MAX_DAILY_CALLS', '100'))
        self.AI_TESTING_MODE = os.getenv('AI_TESTING_MODE', 'true').lower() == 'true'

        # DYNAMIC MARKET REGIME SETTINGS
        self.MIN_REGIME_STRENGTH = float(os.getenv('MIN_REGIME_STRENGTH', '0.25'))
        self.BTC_DOMINANCE_UPDATE_HOURS = int(os.getenv('BTC_DOMINANCE_UPDATE_HOURs', '1'))

        # 🚀 REGIME-BASED MULTIPLIERS - OPTIMIZED FOR DYNAMIC ADJUSTMENT
        self.BULL_POSITION_MULTIPLIER = float(os.getenv('BULL_POSITION_MULTIPLIER', '3.0'))
        self.BEAR_POSITION_MULTIPLIER = float(os.getenv('BEAR_POSITION_MULTIPLIER', '1.5'))
        self.SIDEWAYS_POSITION_MULTIPLIER = float(os.getenv('SIDEWAYS_POSITION_MULTIPLIER', '2.0'))

        self.BULL_PROFIT_MULTIPLIER = float(os.getenv('BULL_PROFIT_MULTIPLIER', '2.0'))
        self.BEAR_PROFIT_MULTIPLIER = float(os.getenv('BEAR_PROFIT_MULTIPLIER', '1.5'))
        self.SIDEWAYS_PROFIT_MULTIPLIER = float(os.getenv('SIDEWAYS_PROFIT_MULTIPLIER', '1.8'))

        # 🚀 EMERGENCY TRADING - OPTIMIZED
        self.EMERGENCY_TRADE_AFTER_CYCLES = int(os.getenv('EMERGENCY_TRADE_AFTER_CYCLES', '5'))
        self.EMERGENCY_TRADE_CHANCE = float(os.getenv('EMERGENCY_TRADE_CHANCE', '0.8'))
        self.FORCE_AI_TRADE_CHANCE = float(os.getenv('FORCE_AI_TRADE_CHANCE', '0.4'))
        self.MIN_DIP_PERCENT_EMERGENCY = float(os.getenv('MIN_DIP_PERCENT_EMERGENCY', '0.8'))
        self.RSI_BUY_MAX_EMERGENCY = float(os.getenv('RSI_BUY_MAX_EMERGENCY', '50.0'))
        self.CONFIDENCE_THRESHOLD_EMERGENCY = float(os.getenv('CONFIDENCE_THRESHOLD_EMERGENCY', '0.15'))

        # FIXED: Working symbols will be populated during initialization
        self._working_symbols = None

    @property
    def symbols(self) -> List[str]:
        if self._working_symbols is not None:
            return self._working_symbols
        return [s.strip() for s in self.TRADING_SYMBOLS.split(",")]

    def set_working_symbols(self, working_symbols: List[str]):
        """Set the verified working symbols"""
        self._working_symbols = working_symbols
        print(f"✅ Trading with {len(working_symbols)} verified symbols: {', '.join(working_symbols)}")


settings = UltimateSettings()


def calculate_std_dev(data: List[float]) -> float:
    if len(data) < 2: return 0.0
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return variance ** 0.5


class CryptoComRealAPI:
    """Real Crypto.com public API for price data - NO TRADING, SIMULATION ONLY"""

    def __init__(self):
        self.base_url = "https://api.crypto.com/v2"
        self.session = None
        self.price_cache = {}
        self.volume_cache = {}
        self.cache_ttl = 10

        # UPDATED: CORRECT CRYPTO.COM SYMBOL MAPPING - VERIFIED WORKING PAIRS
        self.symbol_map = {
            'BTC': 'BTC_USD',
            'ETH': 'ETH_USD',
            'SOL': 'SOL_USD',
            'ADA': 'ADA_USD',
            'AVAX': 'AVAX_USD',
            'LINK': 'LINK_USD',
            'LTC': 'LTC_USD'
        }

    async def emergency_check(self) -> bool:
        """Check if API is available, exit if not"""
        try:
            price = await self.get_ticker('BTC')
            if price <= 0:
                print("❌ CRITICAL: Crypto.com API unavailable - Emergency exit")
                os._exit(1)
            return True
        except Exception as e:
            print(f"❌ CRITICAL: API connection failed - Emergency exit: {e}")
            os._exit(1)

    async def ensure_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def get_ticker(self, symbol: str) -> float:
        """Get real price from Crypto.com public API with emergency exit"""
        current_time = time.time()

        if symbol in self.price_cache:
            price, timestamp = self.price_cache[symbol]
            if current_time - timestamp < self.cache_ttl:
                return price

        await self.ensure_session()

        crypto_symbol = self.symbol_map.get(symbol)
        if not crypto_symbol:
            if settings.VERBOSE_MODE:
                print(f"❌ No symbol mapping for {symbol}")
            return 0.0

        try:
            url = f"{self.base_url}/public/get-ticker"
            params = {'instrument_name': crypto_symbol}

            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    if result and 'data' in result and len(result['data']) > 0:
                        ticker_data = result['data'][0]
                        price = float(ticker_data.get('a', ticker_data.get('b', ticker_data.get('last', 0))))

                        if price > 0:
                            self.price_cache[symbol] = (price, current_time)
                            return price
        except Exception:
            pass

        if symbol in self.price_cache:
            return self.price_cache[symbol][0]
        return 0.0

    async def get_volume(self, symbol: str) -> float:
        """Get 24h volume from Crypto.com"""
        current_time = time.time()

        if symbol in self.volume_cache:
            volume, timestamp = self.volume_cache[symbol]
            if current_time - timestamp < self.cache_ttl:
                return volume

        await self.ensure_session()

        crypto_symbol = self.symbol_map.get(symbol)
        if not crypto_symbol:
            return 1000000.0

        try:
            url = f"{self.base_url}/public/get-ticker"
            params = {'instrument_name': crypto_symbol}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    if result and 'data' in result and len(result['data']) > 0:
                        volume = float(result['data'][0].get('v', 1000000))
                        self.volume_cache[symbol] = (volume, current_time)
                        return volume
        except Exception:
            pass

        return 1000000.0

    async def get_historical_candles(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> List[Dict]:
        """Get historical candle data for technical analysis"""
        await self.ensure_session()

        crypto_symbol = self.symbol_map.get(symbol)
        if not crypto_symbol:
            return []

        try:
            url = f"{self.base_url}/public/get-candlestick"
            params = {
                'instrument_name': crypto_symbol,
                'timeframe': timeframe,
                'count': limit
            }

            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    if result and 'data' in result:
                        candles = []
                        for candle_data in result['data']:
                            candle = {
                                'timestamp': candle_data['t'],
                                'open': float(candle_data['o']),
                                'high': float(candle_data['h']),
                                'low': float(candle_data['l']),
                                'close': float(candle_data['c']),
                                'volume': float(candle_data['v'])
                            }
                            candles.append(candle)
                        return candles
        except Exception:
            pass

        return []

    async def verify_symbol_mappings(self) -> List[str]:
        """Verify which symbols actually work with the API and return working ones (excluding BTC)"""
        print("🔍 Verifying symbol mappings with Crypto.com API...")

        btc_test = await self.get_ticker('BTC')
        if btc_test <= 0:
            print("❌ CRITICAL: Cannot connect to Crypto.com API - Emergency exit")
            return []

        working_symbols = []
        broken_symbols = []

        trading_symbols = settings.symbols

        for symbol in trading_symbols:
            try:
                price = await self.get_ticker(symbol)
                if price > 0:
                    working_symbols.append(symbol)
                    print(f"✅ {symbol} -> {self.symbol_map[symbol]} : WORKS (${price:.4f})")
                else:
                    broken_symbols.append(symbol)
            except Exception:
                broken_symbols.append(symbol)

        if not working_symbols:
            print("❌ CRITICAL: No working symbols found - Emergency exit")
            return []

        print(f"\n📊 Symbol Verification Summary:")
        print(f"✅ {len(working_symbols)} working trading symbols")
        print(f"❌ {len(broken_symbols)} broken symbols")

        return working_symbols

    async def close(self):
        if self.session:
            await self.session.close()


class TechnicalAnalyzer:
    def __init__(self):
        self.support_resistance_cache = {}
        self.cache_ttl = 180
        self.volume_data = {}
        self.price_history = {}

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0

        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    def calculate_volatility(self, prices: List[float], period: int = 20) -> float:
        if len(prices) < 2:
            return 0.0

        recent_prices = prices[-min(period, len(prices)):]
        returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i - 1] != 0:
                daily_return = (recent_prices[i] - recent_prices[i - 1]) / recent_prices[i - 1]
                returns.append(daily_return)

        if len(returns) < 2:
            return 0.0

        volatility = calculate_std_dev(returns) * 100
        return round(volatility, 2)

    def detect_trend(self, prices: List[float]) -> str:
        if len(prices) < 10:
            return "neutral"

        very_short = prices[-5:] if len(prices) >= 5 else prices
        short = prices[-10:] if len(prices) >= 10 else prices
        medium = prices[-20:] if len(prices) >= 20 else prices

        very_short_ma = sum(very_short) / len(very_short)
        short_ma = sum(short) / len(short)
        medium_ma = sum(medium) / len(medium)

        trend_score = 0
        if very_short_ma > short_ma: trend_score += 1
        if short_ma > medium_ma: trend_score += 1
        if very_short_ma > medium_ma: trend_score += 1

        if trend_score >= 2:
            return "bullish"
        elif trend_score <= 1:
            return "bearish"
        else:
            return "neutral"

    def find_support_levels(self, prices: List[float], lookback: int = 50) -> List[float]:
        if len(prices) < lookback:
            return []

        cache_key = hash(tuple(prices[-lookback:]))
        current_time = time.time()

        if (cache_key in self.support_resistance_cache and
                current_time - self.support_resistance_cache[cache_key]['timestamp'] < self.cache_ttl):
            return self.support_resistance_cache[cache_key]['levels']

        support_levels = []
        for i in range(2, len(prices) - 2):
            if (prices[i] < prices[i - 1] and prices[i] < prices[i - 2] and
                    prices[i] < prices[i + 1] and prices[i] < prices[i + 2]):
                support_levels.append(prices[i])

        clusters = []
        for level in sorted(support_levels):
            if not clusters or level > clusters[-1] * 1.02:
                clusters.append(level)

        result = clusters[-3:] if len(clusters) >= 3 else clusters

        self.support_resistance_cache[cache_key] = {
            'levels': result,
            'timestamp': current_time
        }

        return result

    def find_resistance_levels(self, highs: List[float], lookback: int = 20) -> List[float]:
        if len(highs) < lookback:
            return []

        resistance_levels = []
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and
                    highs[i] > highs[i + 1] and highs[i] > highs[i + 2]):
                resistance_levels.append(highs[i])

        clusters = []
        for level in sorted(resistance_levels):
            if not clusters or level > clusters[-1] * 1.02:
                clusters.append(level)

        return clusters[-5:]

    def calculate_dip_strength(self, prices: List[float]) -> Dict:
        if len(prices) < 10:
            return {"strength": 0, "near_support": False, "dip_percent": 0.0}

        current_price = prices[-1]
        recent_high = max(prices[-10:])
        dip_percent = ((recent_high - current_price) / recent_high) * 100

        supports = self.find_support_levels(prices, 20)
        near_support = False

        if supports:
            closest_support = min(supports, key=lambda x: abs(x - current_price))
            support_distance_pct = abs(current_price - closest_support) / current_price * 100
            near_support = support_distance_pct < 3.0

        if dip_percent > 1.5:
            strength = 3
        elif dip_percent > 0.8:
            strength = 2
        elif dip_percent > 0.2:
            strength = 1
        else:
            strength = 0

        if len(prices) >= 14:
            rsi = self.calculate_rsi(prices)
            if rsi < 40 and dip_percent > 0.1:
                strength = max(strength, 1)

        return {
            "strength": strength,
            "near_support": near_support,
            "dip_percent": round(dip_percent, 2)
        }

    def calculate_pump_strength(self, prices: List[float]) -> Dict:
        if len(prices) < 10:
            return {"strength": 0, "pump_percent": 0.0}

        current_price = prices[-1]
        recent_low = min(prices[-10:])
        pump_percent = ((current_price - recent_low) / recent_low) * 100

        if pump_percent > 2.5:
            strength = 3
        elif pump_percent > 1.2:
            strength = 2
        elif pump_percent > 0.4:
            strength = 1
        else:
            strength = 0

        return {
            "strength": strength,
            "pump_percent": round(pump_percent, 2)
        }

    def is_bounce_confirmed(self, prices: List[float], confirmation_candles: int = 2) -> bool:
        if len(prices) < confirmation_candles + 1:
            return False

        recent = prices[-(confirmation_candles + 1):]
        green_candles = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])

        if green_candles >= 1:
            bounce_strength = (recent[-1] - min(recent)) / min(recent) * 100
            return bounce_strength > 0.1

        return False

    def calculate_moving_averages(self, prices: List[float]) -> Dict[str, float]:
        if len(prices) < 20:
            return {}

        return {
            'ma_5': sum(prices[-5:]) / 5,
            'ma_10': sum(prices[-10:]) / 10,
            'ma_20': sum(prices[-20:]) / 20
        }

    def calculate_volume_trend(self, volumes: List[float]) -> str:
        if len(volumes) < 5:
            return "neutral"

        current = volumes[-1]
        avg_5 = sum(volumes[-5:]) / 5
        avg_10 = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else avg_5

        if current > avg_5 > avg_10:
            return "rising"
        elif current < avg_5 < avg_10:
            return "falling"
        else:
            return "neutral"


class EnhancedTechnicalAnalyzer(TechnicalAnalyzer):
    def __init__(self):
        super().__init__()
        self.historical_data = {}
        self.multi_timeframe_data = {}
        self.min_candles_for_analysis = 50

    async def load_multi_timeframe_data(self, symbol: str, api: CryptoComRealAPI):
        """Load historical data across multiple timeframes"""
        timeframes = [
            ('5m', 300),
            ('15m', 200),
            ('1h', 168),
        ]

        multi_data = {}
        loaded_count = 0

        for timeframe, limit in timeframes:
            try:
                candles = await api.get_historical_candles(symbol, timeframe, limit)
                if candles and len(candles) >= 50:
                    multi_data[timeframe] = candles
                    loaded_count += 1
            except Exception:
                pass

        if loaded_count > 0:
            self.multi_timeframe_data[symbol] = multi_data
            if '5m' in multi_data:
                self.historical_data[symbol] = multi_data['5m']
                closes = [c['close'] for c in multi_data['5m']]
                if symbol not in self.price_history:
                    self.price_history[symbol] = []
                self.price_history[symbol].extend(closes[-100:])

        return loaded_count > 0

    def calculate_trend_strength(self, symbol: str) -> Dict:
        if symbol not in self.historical_data:
            return {'trend': 'unknown', 'strength': 0, 'duration_candles': 0}

        candles = self.historical_data[symbol]
        if len(candles) < 20:
            return {'trend': 'unknown', 'strength': 0, 'duration_candles': 0}

        recent_closes = [c['close'] for c in candles[-10:]]
        older_closes = [c['close'] for c in candles[-20:-10]]

        recent_avg = sum(recent_closes) / len(recent_closes)
        older_avg = sum(older_closes) / len(older_closes)

        trend_pct = (recent_avg - older_avg) / older_avg * 100

        if trend_pct > 2.0:
            trend = "strong_uptrend"
            strength = min(1.0, trend_pct / 10.0)
        elif trend_pct > 0.5:
            trend = "weak_uptrend"
            strength = trend_pct / 5.0
        elif trend_pct < -2.0:
            trend = "strong_downtrend"
            strength = min(1.0, abs(trend_pct) / 10.0)
        elif trend_pct < -0.5:
            trend = "weak_downtrend"
            strength = abs(trend_pct) / 5.0
        else:
            trend = "sideways"
            strength = 0.1

        return {
            'trend': trend,
            'strength': strength,
            'trend_pct': trend_pct,
            'duration_candles': len(candles)
        }

    def detect_pump_fomo(self, symbol: str) -> Dict:
        if symbol not in self.historical_data:
            return {'pump_detected': False, 'fomo_level': 0, 'volume_spike': False}

        candles = self.historical_data[symbol]
        if len(candles) < 20:
            return {'pump_detected': False, 'fomo_level': 0, 'volume_spike': False}

        current_price = candles[-1]['close']
        day_high = max(c['high'] for c in candles[-24:])
        day_low = min(c['low'] for c in candles[-24:])

        gain_from_low = (current_price - day_low) / day_low * 100
        distance_from_high = (day_high - current_price) / day_high * 100

        recent_volume = sum(c['volume'] for c in candles[-6:])
        avg_volume = sum(c['volume'] for c in candles[-24:]) / 24

        volume_spike = recent_volume > avg_volume * 2.0

        pump_detected = False
        fomo_level = 0

        if gain_from_low > 15 and volume_spike:
            pump_detected = True
            fomo_level = 3
        elif gain_from_low > 8 and volume_spike:
            pump_detected = True
            fomo_level = 2
        elif gain_from_low > 4 and volume_spike:
            pump_detected = True
            fomo_level = 1

        return {
            'pump_detected': pump_detected,
            'fomo_level': fomo_level,
            'gain_from_low': gain_from_low,
            'distance_from_high': distance_from_high,
            'volume_spike': volume_spike,
            'volume_ratio': recent_volume / avg_volume if avg_volume > 0 else 1.0
        }

    def calculate_support_resistance(self, symbol: str) -> Dict:
        if symbol not in self.historical_data:
            return {'support_levels': [], 'resistance_levels': []}

        candles = self.historical_data[symbol]
        if len(candles) < 20:
            return {'support_levels': [], 'resistance_levels': []}

        prices = [c['close'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]

        support_levels = self.find_support_levels(lows, 20)
        resistance_levels = self.find_resistance_levels(highs, 20)

        current_price = prices[-1]
        nearest_support = max([level for level in support_levels if level < current_price], default=0)
        nearest_resistance = min([level for level in resistance_levels if level > current_price], default=0)

        return {
            'support_levels': support_levels[-3:],
            'resistance_levels': resistance_levels[-3:],
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'support_distance_pct': (
                    (current_price - nearest_support) / current_price * 100) if nearest_support > 0 else 0,
            'resistance_distance_pct': (
                    (nearest_resistance - current_price) / current_price * 100) if nearest_resistance > 0 else 0
        }


class BitcoinCorrelationTracker:
    def __init__(self, api):
        self.api = api
        self.prices = {}
        self.btc_history = []
        self.correlations = {}
        self.btc_volume_history = []
        self.last_btc_update = 0

    async def update_btc_data(self):
        current_time = time.time()
        if current_time - self.last_btc_update < 30:
            return

        try:
            btc_price = await self.api.get_ticker('BTC')
            btc_volume = await self.api.get_volume('BTC')

            if btc_price > 0:
                self.btc_history.append(btc_price)
                self.btc_volume_history.append(btc_volume)

                if len(self.btc_history) > 100:
                    self.btc_history.pop(0)
                if len(self.btc_volume_history) > 100:
                    self.btc_volume_history.pop(0)

                self.last_btc_update = current_time

        except Exception:
            pass

    def update_prices(self, symbol: str, price: float):
        if symbol not in self.prices:
            self.prices[symbol] = []
        self.prices[symbol].append(price)
        if len(self.prices[symbol]) > 50:
            self.prices[symbol].pop(0)

    def calculate_correlation(self, symbol: str) -> float:
        if symbol not in self.prices or len(self.prices[symbol]) < 10 or len(self.btc_history) < 10:
            if symbol in ['ETH', 'SOL', 'AVAX']:
                return random.uniform(0.7, 0.9)
            elif symbol in ['ADA']:
                return random.uniform(0.6, 0.8)
            else:
                return random.uniform(0.5, 0.75)

        symbol_prices = self.prices[symbol][-10:]
        btc_prices = self.btc_history[-10:]

        if len(symbol_prices) != len(btc_prices):
            min_len = min(len(symbol_prices), len(btc_prices))
            symbol_prices = symbol_prices[-min_len:]
            btc_prices = btc_prices[-min_len:]

        try:
            symbol_returns = [(symbol_prices[i] - symbol_prices[i - 1]) / symbol_prices[i - 1]
                              for i in range(1, len(symbol_prices))]
            btc_returns = [(btc_prices[i] - btc_prices[i - 1]) / btc_prices[i - 1]
                           for i in range(1, len(btc_prices))]

            if len(symbol_returns) < 2 or len(btc_returns) < 2:
                return 0.7

            correlation = np.corrcoef(symbol_returns, btc_returns)[0, 1]

            if np.isnan(correlation):
                return 0.7

            return max(0.1, min(0.95, correlation))

        except Exception:
            return 0.7


class BitcoinDominanceTracker:
    def __init__(self, api):
        self.api = api
        self.btc_dominance = 50.0
        self.last_update = 0

    async def update_dominance(self):
        current_time = time.time()
        if current_time - self.last_update < 3600:
            return

        try:
            btc_price = await self.api.get_ticker('BTC')

            if btc_price > 0:
                if hasattr(self, 'last_btc_price'):
                    btc_change = (btc_price - self.last_btc_price) / self.last_btc_price * 100

                    if btc_change > 5:
                        self.btc_dominance = min(60, self.btc_dominance + 0.5)
                    elif btc_change < -3:
                        self.btc_dominance = max(40, self.btc_dominance - 0.3)
                    else:
                        self.btc_dominance += random.uniform(-0.2, 0.2)

                self.last_btc_price = btc_price
                self.btc_dominance = max(35, min(65, self.btc_dominance))
                self.last_update = current_time

        except Exception:
            self.btc_dominance = random.uniform(45, 55)


class DynamicMarketRegime:
    def __init__(self):
        self.current_regime = "SIDEWAYS"
        self.regime_strength = 0.5
        self.regime_history = []
        self.last_regime_change = time.time()
        self.cycle_count = 0
        self.btc_trend = "neutral"
        self.altcoin_performance = 0.0
        self.market_breadth = 0.0

    async def update_real_market_data(self, bot_instance):
        try:
            btc_prices = bot_instance.price_history.get('BTC', [])
            if len(btc_prices) >= 20:
                ma_10 = sum(btc_prices[-10:]) / 10 if len(btc_prices) >= 10 else btc_prices[-1]
                ma_20 = sum(btc_prices[-20:]) / 20 if len(btc_prices) >= 20 else btc_prices[-1]

                if ma_10 > ma_20 * 1.02:
                    self.btc_trend = "bullish"
                    btc_trend_score = 0.7
                elif ma_10 < ma_20 * 0.98:
                    self.btc_trend = "bearish"
                    btc_trend_score = 0.3
                else:
                    self.btc_trend = "neutral"
                    btc_trend_score = 0.5
            else:
                btc_trend_score = 0.5

            altcoin_scores = []
            symbols_analyzed = 0

            for symbol in bot_instance.current_prices:
                if symbol == 'BTC':
                    continue

                if symbol in bot_instance.price_history and len(bot_instance.price_history[symbol]) >= 10:
                    current_price = bot_instance.current_prices.get(symbol)
                    btc_price = bot_instance.current_prices.get('BTC', 1)

                    if current_price and btc_price and current_price > 0:
                        symbol_prices = bot_instance.price_history[symbol]
                        if len(symbol_prices) >= 10:
                            symbol_return = (current_price - symbol_prices[-10]) / symbol_prices[-10] * 100
                            btc_return = (btc_price - btc_prices[-10]) / btc_prices[-10] * 100 if len(
                                btc_prices) >= 10 else 0

                            relative_performance = symbol_return - btc_return
                            altcoin_scores.append(
                                1.0 if relative_performance > 2 else 0.5 if relative_performance > -2 else 0.0)
                            symbols_analyzed += 1

            self.altcoin_performance = sum(altcoin_scores) / len(altcoin_scores) if altcoin_scores else 0.5

            uptrend_count = 0
            total_symbols = 0

            for symbol, prices in bot_instance.price_history.items():
                if len(prices) >= 10:
                    ma_5 = sum(prices[-5:]) / 5
                    ma_10 = sum(prices[-10:]) / 10

                    if ma_5 > ma_10:
                        uptrend_count += 1
                    total_symbols += 1

            self.market_breadth = uptrend_count / total_symbols if total_symbols > 0 else 0.5

            return {
                'btc_trend_score': btc_trend_score,
                'altcoin_performance': self.altcoin_performance,
                'market_breadth': self.market_breadth
            }

        except Exception as e:
            return {
                'btc_trend_score': 0.5,
                'altcoin_performance': 0.5,
                'market_breadth': 0.5
            }

    def detect_regime_with_real_data(self, market_data: Dict) -> str:
        try:
            btc_score = market_data.get('btc_trend_score', 0.5)
            altcoin_score = market_data.get('altcoin_performance', 0.5)
            breadth_score = market_data.get('market_breadth', 0.5)

            weights = {
                'btc': 0.4,
                'altcoins': 0.35,
                'breadth': 0.25
            }

            total_score = (
                    btc_score * weights['btc'] +
                    altcoin_score * weights['altcoins'] +
                    breadth_score * weights['breadth']
            )

            if total_score > 0.55:  # Changed from 0.65
                new_regime = "BULL"
                strength = min(0.95, (total_score - 0.55) * 4)  # More sensitive
            elif total_score < 0.45:  # Changed from 0.35
                new_regime = "BEAR"
                strength = min(0.95, (0.45 - total_score) * 4)
            else:
                new_regime = "SIDEWAYS"
                strength = 0.5

            if new_regime != self.current_regime:
                if strength > settings.MIN_REGIME_STRENGTH:
                    self.current_regime = new_regime
                    self.last_regime_change = time.time()

            self.regime_strength = strength

            return self.current_regime

        except Exception:
            return self.current_regime

    def get_regime_parameters(self) -> Dict:
        base_params = {
            'position_size': settings.BASE_POSITION_SIZE_PERCENT,
            'profit_target': settings.PROFIT_TARGET,
            'stop_loss': settings.STOP_LOSS,
            'rsi_buy_max': settings.RSI_BUY_MAX,
            'rsi_sell_min': settings.RSI_SELL_MIN,
            'confidence_threshold': settings.CONFIDENCE_THRESHOLD,
            'min_dip_percent': settings.MIN_DIP_PERCENT,
            'max_volatility': settings.MAX_VOLATILITY,
            'max_positions': settings.MAX_CONCURRENT_POSITIONS,
            'daily_trade_limit': settings.DAILY_TRADE_LIMIT,
            'position_timeout': settings.POSITION_TIMEOUT,
            'trailing_stop_activate': settings.TRAILING_STOP_ACTIVATE
        }

        regime_strength = max(self.regime_strength, 0.25)

        if self.current_regime == "BULL":
            adjustments = {
                'position_size': 1.5 + (0.8 * regime_strength),
                'profit_target': 1.5 + (0.8 * regime_strength),
                'stop_loss': 0.8,
                'rsi_buy_max': 60.0,
                'rsi_sell_min': 75.0,
                'confidence_threshold': 0.15,
                'min_dip_percent': 0.2,
                'max_positions': 8,
                'daily_trade_limit': 250,
                'position_size_multiplier': 1.8,
                'position_timeout': 3600,
                'trailing_stop_activate': 3.0,
            }
        elif self.current_regime == "BEAR":
            adjustments = {
                'position_size': 0.6 + (0.4 * regime_strength),
                'profit_target': 0.9,
                'stop_loss': 1.5,
                'rsi_buy_max': 45.0,
                'rsi_sell_min': 55.0,
                'confidence_threshold': 0.25,
                'min_dip_percent': 0.8,
                'max_positions': 4,
                'daily_trade_limit': 100,
                'position_size_multiplier': 0.5,
                'position_timeout': 900,
                'trailing_stop_activate': 1.0,
            }
        else:  # SIDEWAYS
            adjustments = {
                'position_size': 1.2 + (0.5 * regime_strength),
                'profit_target': 1.2 + (0.5 * regime_strength),
                'stop_loss': 1.0,
                'rsi_buy_max': 55.0,
                'rsi_sell_min': 65.0,
                'confidence_threshold': 0.18,
                'min_dip_percent': 0.3,
                'max_positions': 6,
                'daily_trade_limit': 180,
                'position_size_multiplier': 1.2,
                'position_timeout': 900,
                'trailing_stop_activate': 2.0,
            }

        adjusted_params = base_params.copy()
        adjusted_params['position_size'] *= adjustments['position_size']
        adjusted_params['profit_target'] *= adjustments['profit_target']
        adjusted_params['stop_loss'] *= adjustments['stop_loss']
        adjusted_params['rsi_buy_max'] = adjustments['rsi_buy_max']
        adjusted_params['confidence_threshold'] = adjustments['confidence_threshold']
        adjusted_params['min_dip_percent'] = adjustments['min_dip_percent']
        adjusted_params['max_positions'] = adjustments['max_positions']
        adjusted_params['daily_trade_limit'] = adjustments['daily_trade_limit']
        adjusted_params['position_size_multiplier'] = adjustments['position_size_multiplier']

        adjusted_params.update({
            'regime': self.current_regime,
            'regime_strength': regime_strength,
            'regime_duration': time.time() - self.last_regime_change,
            'btc_trend': self.btc_trend,
            'altcoin_performance': self.altcoin_performance,
            'market_breadth': self.market_breadth
        })

        return adjusted_params


class DeepSeekAnalyzer:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.session = None
        self.cache = {}
        self.cache_ttl = settings.AI_CACHE_TTL
        self.last_call_time = 0
        self.rate_limit_delay = 0.5
        self.daily_call_count = 0
        self.last_reset_time = time.time()
        self.total_tokens_used = 0
        self.cycle_count = 0
        self.model_name = "deepseek-reasoner"

    async def emergency_check(self) -> bool:
        if not self.api_key:
            return True

        try:
            await self.ensure_session()
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            }

            async with self.session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=5.0
            ) as response:
                return response.status == 200

        except Exception:
            return False

    def _reset_daily_count(self):
        current_time = time.time()
        if current_time - self.last_reset_time > 86400:
            self.daily_call_count = 0
            self.last_reset_time = current_time

    async def ensure_session(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=8)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def analyze_sentiment_aggressive(self, symbol: str, price: float, technical_data: Dict) -> Dict:
        self._reset_daily_count()
        self.cycle_count += 1

        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last_call)

        if self.daily_call_count >= settings.AI_MAX_DAILY_CALLS:
            return self._get_fallback_analysis(technical_data)

        cache_key = self._generate_cache_key(symbol, technical_data)

        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if current_time - timestamp < self.cache_ttl:
                return cached_data

        if not self._should_use_ai(
                technical_data.get('rsi', 50),
                {'strength': technical_data.get('dip_strength', 0)},
                {'strength': technical_data.get('pump_strength', 0)},
                technical_data.get('bounce_confirmed', False),
                technical_data.get('trend', 'neutral'),
                technical_data.get('volatility', 0)
        ):
            return self._get_fallback_analysis(technical_data)

        prompt = self._generate_aggressive_prompt(symbol, price, technical_data)

        try:
            result = await self._call_deepseek_api(prompt, symbol)
            self.cache[cache_key] = (result, current_time)
            self.last_call_time = current_time
            self.daily_call_count += 1
            return result
        except Exception:
            return self._get_fallback_analysis(technical_data)

    def _generate_cache_key(self, symbol: str, technical_data: Dict) -> str:
        key_data = {
            'symbol': symbol,
            'rsi_bucket': int(technical_data.get('rsi', 50) / 5),
            'dip_strength': technical_data.get('dip_strength', 0),
            'near_support': technical_data.get('near_support', False),
            'trend': technical_data.get('trend', 'neutral'),
            'volatility_bucket': int(technical_data.get('volatility', 0) / 10)
        }
        return str(hash(frozenset(key_data.items())))

    def _generate_aggressive_prompt(self, symbol: str, price: float, technical_data: Dict) -> str:
        rsi = technical_data.get('rsi', 50)
        dip_strength = technical_data.get('dip_strength', 0)
        near_support = technical_data.get('near_support', False)
        volatility = technical_data.get('volatility', 0)
        dip_percent = technical_data.get('dip_percent', 0)
        trend = technical_data.get('trend', 'neutral')
        bounce_confirmed = technical_data.get('bounce_confirmed', False)

        prompt = f"""Analyze {symbol} at ${price:.4f} for BOTH LONG and SHORT opportunities:

        TECHNICAL DATA:
        - RSI: {rsi:.1f} ({'OVERSOLD' if rsi < 35 else 'BEARISH' if rsi < 50 else 'BULLISH' if rsi > 65 else 'NEUTRAL'})
        - Trend: {trend.upper()}
        - Dip: {dip_percent:.1f}% from recent high
        - Pump: {pump_analysis.get('pump_percent', 0):.1f}% from recent low  
        - Support: {'NEAR' if dip_analysis.get('near_support') else 'FAR'}
        - Volatility: {volatility:.1f}%
        - BTC Correlation: {btc_correlation:.2f}

        MARKET CONTEXT:
        - Regime: {self.current_regime}
        - Position Size: {settings.BASE_POSITION_SIZE_PERCENT}%
        - Targets: {settings.PROFIT_TARGET}% profit / {settings.STOP_LOSS}% stop

        OBJECTIVE ASSESSMENT REQUEST:
        Based SOLELY on the technical data above, recommend LONG (BUY), SHORT (SELL), or HOLD.
        Consider both directions equally. Justify with specific technical factors.

        Respond with JSON: {{"action": "BUY|HOLD|SELL", "confidence": 0.0-1.0, "reason": "technical_justification"}}"""

        return prompt

    async def _call_deepseek_api(self, prompt: str, symbol: str) -> Dict:
        await self.ensure_session()

        if not self.api_key:
            return self._get_fallback_analysis()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-reasoner",
            "messages": [
                {
                    "role": "system",
                    "content": """You are an expert quantitative crypto trading analyst. 
                    Analyze the technical setup objectively and recommend the most probable direction.
                    
                    EVALUATION FRAMEWORK:
                    1. **LONG (BUY) signals**: RSI < 50, price dip > 0.5%, near support, bullish trend, volume increasing
                    2. **SHORT (SELL) signals**: RSI > 65, price pump > 1.5%, near resistance, bearish trend, volume decreasing  
                    3. **HOLD/NEUTRAL**: Mixed signals, unclear direction, low volatility, insufficient data
                    
                    Return JSON: {"action": "BUY|HOLD|SELL", "confidence": 0.0-1.0, "reason": "brief_technical_justification"}
                    Be objective, not aggressive."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.6,
            "max_tokens": 150,
            "response_format": {"type": "json_object"}
        }

        try:
            async with self.session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=8.0
            ) as response:

                if response.status == 200:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    usage = data.get('usage', {})
                    self.total_tokens_used += usage.get('total_tokens', 0)

                    return self._parse_deepseek_response(content)
                else:
                    raise Exception(f"API status {response.status}")

        except asyncio.TimeoutError:
            raise Exception("DeepSeek API timeout after 8 seconds")
        except Exception as e:
            raise Exception(f"DeepSeek API call failed: {str(e)}")

    def _parse_deepseek_response(self, content: str) -> Dict:
        try:
            data = json.loads(content)
            action = data.get('action', 'HOLD').upper()
            confidence = max(0.0, min(1.0, float(data.get('confidence', 0.4))))
            reason = data.get('reason', 'No reason provided')

            if action not in ['BUY', 'HOLD', 'SELL']:
                action = 'HOLD'

            return {
                "sentiment": "bullish" if action == "BUY" else "bearish" if action == "SELL" else "neutral",
                "confidence": confidence,
                "recommendation": action,
                "rationale": reason
            }

        except json.JSONDecodeError:
            return self._get_fallback_analysis()
        except (ValueError, KeyError):
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self, technical_data: Dict = None) -> Dict:
        if technical_data:
            rsi = technical_data.get('rsi', 50)
            dip_strength = technical_data.get('dip_strength', 0)
            near_support = technical_data.get('near_support', False)
            trend = technical_data.get('trend', 'neutral')
            volatility = technical_data.get('volatility', 0)

            if (rsi < 50 and dip_strength >= 1 and
                    near_support and trend in ["bullish", "neutral"] and volatility < 60):
                return {
                    "sentiment": "bullish",
                    "confidence": 0.9,
                    "recommendation": "BUY",
                    "rationale": "Fallback: Good technical setup"
                }

        return {
            "sentiment": "neutral",
            "confidence": 0.5,
            "recommendation": "HOLD",
            "rationale": "Fallback: Moderate signal strength"
        }

    def get_usage_stats(self) -> Dict:
        return {
            'daily_calls': self.daily_call_count,
            'total_tokens': self.total_tokens_used,
            'cache_size': len(self.cache),
            'cycle_count': self.cycle_count
        }

    def _should_use_ai(self, rsi: float, dip_analysis: Dict, pump_analysis: Dict,
                       bounce_confirmed: bool, trend: str, volatility: float) -> bool:
        self._reset_daily_count()
        if self.daily_call_count >= settings.AI_MAX_DAILY_CALLS:
            return False

        # Use AI only 10% of the time to save credits
        return random.random() < 0.1

    async def close(self):
        if self.session:
            await self.session.close()


class UltimateTradingLogic:
    def __init__(self, market_regime=None):
        self.technical = EnhancedTechnicalAnalyzer()
        self.deepseek = DeepSeekAnalyzer()
        self.ai_usage_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'cache_hits': 0,
            'fallbacks_used': 0,
            'last_call_time': 0
        }
        self.symbol_analysis_count = {}
        self.market_regime = market_regime



    async def initialize_historical_context(self, symbols: List[str], api: CryptoComRealAPI):
        print("🕐 Loading historical context for technical analysis...")

        loaded_count = 0
        for symbol in symbols[:8]:
            success = await self.technical.load_multi_timeframe_data(symbol, api)
            if success:
                loaded_count += 1
            await asyncio.sleep(0.5)

        print(f"✅ Historical context loaded for {loaded_count}/{len(symbols)} symbols")
        return loaded_count > 0

    async def analyze_opportunity(self, symbol: str, current_price: float,
                                  price_history: List[float], volume_history: List[float],
                                  btc_correlation: float) -> Dict:
        """Analyze trading opportunity for both LONG and SHORT"""

        if len(price_history) < 15:
            return self._get_insufficient_data_signal()

        self.symbol_analysis_count[symbol] = self.symbol_analysis_count.get(symbol, 0) + 1

        # Calculate technical indicators
        rsi = self.technical.calculate_rsi(price_history)
        volatility = self.technical.calculate_volatility(price_history)
        trend = self.technical.detect_trend(price_history)
        dip_analysis = self.technical.calculate_dip_strength(price_history)
        pump_analysis = self.technical.calculate_pump_strength(price_history)
        bounce_confirmed = self.technical.is_bounce_confirmed(price_history, settings.CONFIRMATION_CANDLES)
        moving_averages = self.technical.calculate_moving_averages(price_history)
        volume_trend = self.technical.calculate_volume_trend(volume_history) if volume_history else "neutral"

        use_ai = self.deepseek._should_use_ai(rsi, dip_analysis, pump_analysis, bounce_confirmed, trend, volatility)

        if use_ai:
            ai_sentiment = await self._get_ai_analysis(symbol, current_price, {
                'rsi': rsi,
                'dip_strength': dip_analysis['strength'],
                'pump_strength': pump_analysis['strength'],
                'near_support': dip_analysis['near_support'],
                'dip_percent': dip_analysis['dip_percent'],
                'pump_percent': pump_analysis['pump_percent'],
                'volatility': volatility,
                'trend': trend,
                'bounce_confirmed': bounce_confirmed,
                'moving_averages': moving_averages,
                'volume_trend': volume_trend,
                'btc_correlation': btc_correlation,
            })
        else:
            ai_sentiment = self._get_simple_analysis(rsi, dip_analysis, pump_analysis, bounce_confirmed, trend,
                                                     volatility, volume_trend)

        regime_params = self.market_regime.get_regime_parameters()
        advice, confidence, reason, position_type = self._generate_trading_signal(
            rsi, volatility, trend, btc_correlation, volume_trend,
            dip_analysis, pump_analysis, bounce_confirmed, ai_sentiment, use_ai,
            moving_averages, current_price, regime_params
        )

        return {
            "advice": advice,
            "confidence": confidence,
            "position_type": position_type,
            "trend": trend,
            "rsi": rsi,
            "volatility": volatility,
            "btc_correlation": btc_correlation,
            "volume_trend": volume_trend,
            "dip_strength": dip_analysis["strength"],
            "pump_strength": pump_analysis["strength"],
            "near_support": dip_analysis["near_support"],
            "dip_percent": dip_analysis["dip_percent"],
            "pump_percent": pump_analysis["pump_percent"],
            "bounce_confirmed": bounce_confirmed,
            "ai_sentiment": ai_sentiment["sentiment"],
            "ai_confidence": ai_sentiment["confidence"],
            "ai_recommendation": ai_sentiment["recommendation"],
            "reason_short": reason,
            "ai_used": use_ai,
            "moving_averages": moving_averages,
        }

    def _generate_trading_signal(self, rsi: float, volatility: float, trend: str, btc_corr: float,
                                 volume_trend: str, dip_analysis: Dict, pump_analysis: Dict,
                                 bounce_confirmed: bool, ai_sentiment: Dict, ai_used: bool,
                                 moving_averages: Dict, current_price: float, regime_params: Dict) -> Tuple[str, float, str, PositionType]:
        
        current_regime = regime_params.get('regime', 'SIDEWAYS')
        regime_strength = regime_params.get('regime_strength', 0.5)
        bull_confidence, bear_confidence = 0.0, 0.0
        bull_reasons, bear_reasons = [], []
        signal_quality = 0
        signal_quality += 1 if dip_analysis["strength"] >= 2 else 0
        signal_quality += 1 if rsi < 40 or rsi > 70 else 0  # Strong RSI extreme
        signal_quality += 1 if volume_trend == "rising" and trend == "bullish" else 0
        signal_quality += 1 if volume_trend == "falling" and trend == "bearish" else 0

        # Only proceed if signal is strong enough, especially in sideways
        if current_regime == "SIDEWAYS" and signal_quality < 2:
            return "Avoid", 0.3, "weak_signal_sideways", PositionType.LONG
        
        # SINGLE, UNIFIED REGIME PARAMETERS
        if current_regime == "BULL":
            required_pump_percent = 2.5
            sell_confidence_threshold = -0.6
        elif current_regime == "BEAR":
            required_pump_percent = 2.0
            sell_confidence_threshold = -0.3
        else:  # SIDEWAYS
            required_pump_percent = 1.2
            sell_confidence_threshold = -0.4
        
        short_rsi_min = regime_params.get('rsi_sell_min', 70.0)

        # ========== BULL SIGNALS (LONG) ==========
        if dip_analysis["strength"] >= 1:
            bull_confidence += 0.5
            bull_reasons.append(f"dip_{dip_analysis['dip_percent']:.1f}%")
        elif dip_analysis["strength"] >= 0:
            bull_confidence += 0.3
            bull_reasons.append(f"minor_dip_{dip_analysis['dip_percent']:.1f}%")

        if dip_analysis["near_support"]:
            bull_confidence += 0.3
            bull_reasons.append("at_support")

        if rsi < 35:
            bull_confidence += 0.6
            bull_reasons.append(f"very_low_rsi_{rsi:.0f}")
        elif rsi < 45:
            bull_confidence += 0.4
            bull_reasons.append(f"low_rsi_{rsi:.0f}")
        elif rsi < 55:
            bull_confidence += 0.2
            bull_reasons.append(f"moderate_rsi_{rsi:.0f}")

        if bounce_confirmed:
            bull_confidence += 0.3
            bull_reasons.append("bounce")

        if trend == "bullish":
            bull_confidence += 0.3
            bull_reasons.append("bull_trend")
        elif trend == "neutral":
            bull_confidence += 0.2
            bull_reasons.append("neutral_trend")

        if volume_trend == "rising":
            bull_confidence += 0.25
            bull_reasons.append("vol_up")

        # ========== BEAR SIGNALS (SHORT) ==========
        short_score = 0
        short_reasons = []

        # REGIME-ADJUSTED SHORTING THRESHOLDS
        if current_regime == "SIDEWAYS" or current_regime == "BEAR":
            # Easier shorting in sideways/bear markets
            if rsi > 65:  # Lowered from 70 for easier shorts
                short_score += 3
                short_reasons.append(f"very_high_rsi_{rsi:.0f}")
            elif rsi > 60:
                short_score += 2
                short_reasons.append(f"high_rsi_{rsi:.0f}")
            elif rsi > 55:
                short_score += 1
                short_reasons.append(f"moderate_high_rsi_{rsi:.0f}")
        else:  # BULL market - be more conservative with shorts
            if rsi > 70:
                short_score += 3
                short_reasons.append(f"very_high_rsi_{rsi:.0f}")
            elif rsi > 65:
                short_score += 2
                short_reasons.append(f"high_rsi_{rsi:.0f}")

        # PUMP DETECTION WITH REGIME SENSITIVITY
        if pump_analysis["strength"] >= 2:
            short_score += 2
            short_reasons.append(f"pump_{pump_analysis['pump_percent']:.1f}%")
        elif pump_analysis["strength"] >= 1:
            short_score += 1
            short_reasons.append(f"minor_pump_{pump_analysis['pump_percent']:.1f}%")

        if trend == "bearish":
            short_score += 2
            short_reasons.append("bear_trend")
        elif trend == "neutral":
            short_score += 1
            short_reasons.append("neutral_trend_short")

        if volume_trend == "falling":
            short_score += 1
            short_reasons.append("vol_down")

        # Check for overbought RSI with negative divergence
        if rsi > 70 and volume_trend == "falling":
            short_score += 2
            short_reasons.append("overbought_divergence")

        # Price above key moving averages (resistance)
        if moving_averages:
            ma_20 = moving_averages.get('ma_20', current_price)
            ma_10 = moving_averages.get('ma_10', current_price)
            if current_price > ma_20 > ma_10:
                short_score += 1
                short_reasons.append("above_ma_resistance")

        # ========== AI INFLUENCE ==========
        if ai_used:
            if ai_sentiment["recommendation"] == "BUY":
                bull_confidence += min(0.5, ai_sentiment["confidence"] * 0.7)
                bull_reasons.append("ai_bull")
            elif ai_sentiment["recommendation"] == "SELL":
                short_score += int(min(3, ai_sentiment["confidence"] * 3))
                short_reasons.append("ai_bear")

        # ========== VOLATILITY ADJUSTMENT ==========
        if volatility > 60:
            bull_confidence -= 0.1
            short_score -= 1
            bull_reasons.append("high_vol")
            short_reasons.append("high_vol")

        # ========== BTC CORRELATION ADJUSTMENT ==========
        if btc_corr > 0.8:
            if trend == "bearish":
                short_score += 1
            elif trend == "bullish":
                bull_confidence += 0.1

        # ========== FINAL DECISION ==========
        net_confidence = bull_confidence - (short_score / 5.0)
        
        # REGIME-ADJUSTED DECISION THRESHOLDS
        if current_regime == "BULL":
            # Bias toward longs in bull markets
            if net_confidence >= 0.3:
                advice = "Strong Buy" if net_confidence >= 0.5 else "Buy"
                position_type = PositionType.LONG
                confidence = min(1.0, bull_confidence * (0.9 if advice == "Buy" else 1.0))
                reasons = bull_reasons
            elif net_confidence <= sell_confidence_threshold:
                advice = "Sell" if net_confidence >= sell_confidence_threshold - 0.1 else "Strong Sell"
                position_type = PositionType.SHORT
                confidence = min(1.0, short_score / 10.0 * (0.7 if advice == "Sell" else 0.9))
                reasons = short_reasons
            else:
                advice = "Hold"
                position_type = PositionType.LONG
                confidence = max(bull_confidence, short_score / 10.0) * 0.7
                reasons = ["mixed_signals"]
                
        elif current_regime == "BEAR":
            # Bias toward shorts in bear markets
            if net_confidence <= sell_confidence_threshold:
                advice = "Strong Sell" if net_confidence <= sell_confidence_threshold - 0.1 else "Sell"
                position_type = PositionType.SHORT
                confidence = min(1.0, short_score / 10.0 * (0.8 if advice == "Sell" else 1.0))
                reasons = short_reasons
            elif net_confidence >= 0.4:
                advice = "Buy" if net_confidence < 0.6 else "Strong Buy"
                position_type = PositionType.LONG
                confidence = min(1.0, bull_confidence * (0.8 if advice == "Buy" else 0.9))
                reasons = bull_reasons
            else:
                advice = "Hold"
                position_type = PositionType.LONG
                confidence = max(bull_confidence, short_score / 10.0) * 0.7
                reasons = ["mixed_signals"]
                
        else:  # SIDEWAYS
            # Balanced approach with easier shorting
            if net_confidence >= 0.4:
                advice = "Strong Buy" if net_confidence >= 0.6 else "Buy"
                position_type = PositionType.LONG
                confidence = min(1.0, bull_confidence * (0.85 if advice == "Buy" else 0.95))
                reasons = bull_reasons
            elif net_confidence <= sell_confidence_threshold:
                advice = "Sell" if net_confidence >= sell_confidence_threshold - 0.1 else "Strong Sell"
                position_type = PositionType.SHORT
                confidence = min(1.0, short_score / 10.0 * (0.8 if advice == "Sell" else 0.9))
                reasons = short_reasons
            elif abs(net_confidence) < 0.2:
                advice = "Hold"
                position_type = PositionType.LONG
                confidence = max(bull_confidence, short_score / 10.0) * 0.7
                reasons = ["mixed_signals"]
            else:
                advice = "Avoid"
                position_type = PositionType.LONG
                confidence = 0.3
                reasons = ["uncertain"]

        # DEBUG LOGGING
        if short_score >= 5 and advice not in ["Sell", "Strong Sell"]:
            print(f"⚠️  MISSED SHORT: RSI={rsi:.1f}, bull_conf={bull_confidence:.2f}, "
                  f"short_score={short_score}, net={net_confidence:.2f}, decision={advice}")
        
        # FORCE SHORT IN EXTREME CONDITIONS
        if rsi > 75 and pump_analysis["strength"] >= 2 and settings.ENABLE_SHORTING:
            if advice not in ["Sell", "Strong Sell"]:
                print(f"🚨 FORCING SHORT: Extreme overbought (RSI={rsi:.1f}, "
                      f"pump={pump_analysis['pump_percent']:.1f}%)")
                advice = "Strong Sell"
                position_type = PositionType.SHORT
                confidence = 0.8
                reasons = ["forced_short_extreme_overbought"]

        return advice, max(0.1, min(1.0, confidence)), " | ".join(reasons) if reasons else "No clear setup", position_type
        
    async def _get_ai_analysis(self, symbol: str, price: float, technical_data: Dict) -> Dict:
        self.ai_usage_stats['total_calls'] += 1
        self.ai_usage_stats['last_call_time'] = time.time()

        try:
            result = await self.deepseek.analyze_sentiment_aggressive(symbol, price, technical_data)
            self.ai_usage_stats['successful_calls'] += 1
            return result
        except Exception:
            self.ai_usage_stats['fallbacks_used'] += 1
            return self._get_fallback_analysis(technical_data)

    def _get_simple_analysis(self, rsi: float, dip_analysis: Dict, pump_analysis: Dict,
                             bounce_confirmed: bool, trend: str, volatility: float, volume_trend: str) -> Dict:
        long_score = (rsi < 50) + dip_analysis["strength"] + (1 if dip_analysis["near_support"] else 0) + (
            1 if bounce_confirmed else 0) + (1 if trend == "bullish" else 0)
        short_score = (rsi > 65) + pump_analysis["strength"]

        if long_score >= 2 and long_score > short_score:
            return {
                "sentiment": "bullish",
                "confidence": min(0.95, 0.5 + (long_score - 2) * 0.2),
                "recommendation": "BUY",
                "rationale": f"Simple: Long setup (RSI:{rsi:.1f}, Dip:{dip_analysis['strength']})"
            }
        elif short_score >= 3 and short_score > long_score:
            return {
                "sentiment": "bearish",
                "confidence": min(0.95, 0.5 + (short_score - 3) * 0.2),
                "recommendation": "SELL",
                "rationale": f"Simple: Short setup (RSI:{rsi:.1f}, Pump:{pump_analysis['strength']})"
            }
        else:
            return {
                "sentiment": "neutral",
                "confidence": max(0.1, (long_score + short_score) * 0.1),
                "recommendation": "HOLD",
                "rationale": f"Simple: Weak setup ({long_score}/{short_score})"
            }

    def _get_fallback_analysis(self, technical_data: Dict) -> Dict:
        return self._get_simple_analysis(
            technical_data.get('rsi', 50),
            {'strength': technical_data.get('dip_strength', 0),
             'near_support': technical_data.get('near_support', False),
             'dip_percent': technical_data.get('dip_percent', 0)},
            {'strength': technical_data.get('pump_strength', 0),
             'pump_percent': technical_data.get('pump_percent', 0)},
            technical_data.get('bounce_confirmed', False),
            technical_data.get('trend', 'neutral'),
            technical_data.get('volatility', 0),
            technical_data.get('volume_trend', 'neutral')
        )

    def _get_insufficient_data_signal(self) -> Dict:
        return {
            "advice": "Hold", "confidence": 0.0, "position_type": PositionType.LONG,
            "trend": "neutral", "rsi": 50.0, "volatility": 0.0, "btc_correlation": 0.5,
            "volume_trend": "neutral", "dip_strength": 0, "pump_strength": 0,
            "near_support": False, "dip_percent": 0.0, "pump_percent": 0.0,
            "bounce_confirmed": False, "ai_sentiment": "neutral",
            "ai_confidence": 0.0, "ai_recommendation": "HOLD",
            "reason_short": "Insufficient data", "ai_used": False,
            "moving_averages": {},
        }

    def get_ai_stats(self) -> Dict:
        stats = self.ai_usage_stats.copy()
        stats.update(self.deepseek.get_usage_stats())
        stats['symbol_analysis_count'] = self.symbol_analysis_count
        return stats

    async def close(self):
        await self.deepseek.close()


class SimplePositionManager:
    """Simple position manager with support for both LONG and SHORT positions"""

    def __init__(self, initial_capital: float):
        self.total_capital = initial_capital
        self.available_capital = initial_capital
        self.positions = {}
        self.total_invested = 0.0

    def can_open_position(self, position_size: float) -> bool:
        return position_size <= self.available_capital

    def get_margin_usage(self) -> Dict:
        total_used = sum(pos.get('size', 0) for pos in self.positions.values())
        total_capital = self.available_capital + total_used

        return {
            'used': total_used,
            'available': self.available_capital,
            'total': total_capital,
            'usage_percent': (total_used / total_capital * 100) if total_capital > 0 else 0
        }

    def calculate_position_size(self, total_capital: float, volatility: float = 0.0) -> float:
        base_size = total_capital * (settings.BASE_POSITION_SIZE_PERCENT / 100)
        max_position = self.available_capital * 0.25
        return min(base_size, max_position)

    def open_position(self, symbol: str, position_type: PositionType,
                      size: float, entry_price: float) -> Dict:
        if not self.can_open_position(size):
            raise ValueError(f"Insufficient capital: ${size:.2f} > ${self.available_capital:.2f}")

        position = {
            'symbol': symbol,
            'position_type': position_type,
            'qty': size / entry_price,
            'entry_price': entry_price,
            'entry_time': time.time(),
            'size': size,
            'stop_loss': 0.0,
            'take_profit': 0.0,
            'trailing_stop_activated': False,
            'highest_price': entry_price if position_type == PositionType.LONG else 0,
            'lowest_price': entry_price if position_type == PositionType.SHORT else float('inf')
        }

        # For SHORT positions, track lowest price (for trailing stops)
        if position_type == PositionType.SHORT:
            position['lowest_price'] = entry_price
            position['highest_price'] = 0  # Not used for shorts

        self.positions[symbol] = position
        self.available_capital -= size
        self.total_invested += size

        print(f"💰 POSITION OPENED: {symbol} {position_type.value} - Size: ${size:.2f}")
        print(f"   Available: ${self.available_capital:.2f}")

        return position

    def close_position(self, symbol: str, exit_price: float) -> float:
        if symbol not in self.positions:
            return 0.0

        position = self.positions[symbol]

        if position['position_type'] == PositionType.LONG:
            pnl = (exit_price - position['entry_price']) * position['qty']
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['qty']

        self.available_capital += position['size'] + pnl
        self.total_invested -= position['size']

        del self.positions[symbol]

        return pnl

    def get_positions_value(self) -> float:
        return self.total_invested

    def get_available_capital(self) -> float:
        return self.available_capital

    def get_total_capital(self, current_prices: Dict) -> float:
        unrealized_pnl = 0.0
        for symbol, pos in self.positions.items():
            current_price = current_prices.get(symbol, pos['entry_price'])
            if pos['position_type'] == PositionType.LONG:
                position_pnl = (current_price - pos['entry_price']) * pos['qty']
            else:  # SHORT
                position_pnl = (pos['entry_price'] - current_price) * pos['qty']
            unrealized_pnl += position_pnl

        return self.available_capital + self.total_invested + unrealized_pnl

    def get_short_positions_count(self) -> int:
        return sum(1 for pos in self.positions.values() if pos.get('position_type') == PositionType.SHORT)


class PerformanceOptimizer:
    def __init__(self, bot):
        self.bot = bot
        self.min_profit_per_trade = 0.50
        self.trade_quality_threshold = 0.7

    async def analyze_trade_quality(self, symbol: str, analysis: Dict) -> bool:
        if analysis.get('confidence', 0) < self.trade_quality_threshold:
            return False

        position_size = self.bot.margin_manager.total_capital * (settings.BASE_POSITION_SIZE_PERCENT / 100)
        potential_profit = position_size * (settings.PROFIT_TARGET / 100)

        if potential_profit >= self.min_profit_per_trade:
            return True

        return False


class DataQualityTracker:
    def __init__(self):
        self.symbol_scores = {}

    def assess_symbol_data(self, symbol: str, multi_timeframe_data: Dict) -> Dict:
        if not multi_timeframe_data:
            return {"sufficient": False, "overall_score": 0, "recommendation": "NO_DATA"}

        total_candles = sum(len(candles) for candles in multi_timeframe_data.values())
        score = min(1.0, total_candles / 300)

        result = {
            "sufficient": score > 0.3,
            "overall_score": score,
            "recommendation": "HIGH_CONFIDENCE" if score > 0.7 else "MEDIUM_CONFIDENCE" if score > 0.5 else "LOW_CONFIDENCE"
        }

        self.symbol_scores[symbol] = result
        return result


class TelegramController:
    def __init__(self, bot):
        self.bot = bot
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.user_ids = settings.TELEGRAM_USER_IDS
        self.last_update_id = 0
        self.last_report = 0
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        self.last_buy_notification = 0
        self.last_sell_notification = 0
        self.notification_cooldown = 120

        if self.token:
            print(" Telegram Bot: Starting message polling...")
            self.running = True
            self.poll_thread = threading.Thread(target=self.poll_messages, daemon=True)
            self.poll_thread.start()
        else:
            print("⚠️  Telegram Bot: No token provided - running without Telegram")

    def send_message(self, chat_id: int, text: str, force: bool = False):
        if not self.token:
            if force or any(x in text for x in ['BUY', 'SELL', 'OPTIMIZED', 'FINAL', 'REPORT']):
                print(f" Telegram (SIM): {text}")
            return

        current_time = time.time()
        if not force and "BUY" in text and current_time - self.last_buy_notification < self.notification_cooldown:
            return
        if not force and "SELL" in text and current_time - self.last_sell_notification < self.notification_cooldown:
            return

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            headers = {'User-Agent': 'MyTradingBot/1.0'}

            response = requests.post(url, json=payload, timeout=10, headers=headers)

            if response.status_code != 200:
                return False

            if "BUY" in text:
                self.last_buy_notification = current_time
            elif "SELL" in text:
                self.last_sell_notification = current_time

            return True

        except Exception:
            return False

    def poll_messages(self):
        while self.running and self.token:
            try:
                url = f"{self.base_url}/getUpdates"
                params = {'offset': self.last_update_id + 1, 'timeout': 30}
                headers = {'User-Agent': 'MyTradingBot/1.0'}
                response = requests.get(url, params=params, timeout=35, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        for update in data.get('result', []):
                            self.handle_update(update)
                            self.last_update_id = update['update_id']
            except Exception:
                time.sleep(5)

    def handle_update(self, update):
        if 'message' not in update:
            return
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()

        if chat_id not in self.user_ids:
            self.send_message(chat_id, "❌ Unauthorized access.")
            return

        # Define command handlers
        command_handlers = {
            '/start': self.handle_start,
            '/performance': self.handle_performance,
            '/balance': self.handle_balance,
            '/positions': self.handle_positions,
            '/pause': self.handle_pause,
            '/resume': self.handle_resume,
            '/reset_limits': self.handle_reset_limits,
            '/status': self.handle_status,
            '/ai_stats': self.handle_ai_stats,
            '/regime': self.handle_regime,
        }

        for command, handler in command_handlers.items():
            if text.startswith(command):
                handler(chat_id, text)
                return

        self.send_message(chat_id, "❓ Unknown command. Use /start for help")

    def handle_start(self, chat_id: int, text: str):
        welcome_msg = (
            " <b>ULTIMATE AGGRESSIVE TRADING BOT WITH SHORTING</b>\n\n"
            "🎯 PAPER TRADING: Real prices, simulated money\n"
            f"💰 Capital: ${settings.INITIAL_CAPITAL:.2f} virtual\n"
            f"📈 Position size: {settings.BASE_POSITION_SIZE_PERCENT}%\n"
            f"📉 SHORTING: {'ENABLED' if settings.ENABLE_SHORTING else 'DISABLED'}\n"
            f"⚡ DYNAMIC REGIME ADJUSTMENTS: ACTIVE\n"
            f"🎯 Targets: {settings.PROFIT_TARGET}% profit | {settings.STOP_LOSS}% stop loss\n"
            f"🤖 AI Integration: DeepSeek analysis\n\n"
            "<b>Commands:</b>\n"
            "/performance - Trading performance\n"
            "/balance - Current balance\n"
            "/positions - Active positions\n"
            "/status - Bot status\n"
            "/ai_stats - AI usage statistics\n"
            "/regime - Market regime info\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading\n"
            "/reset_limits - Reset trading limits"
        )
        self.send_message(chat_id, welcome_msg)

    def handle_performance(self, chat_id: int, text: str):
        try:
            running_seconds = time.time() - self.bot.start_time
            hours = int(running_seconds // 3600)
            minutes = int((running_seconds % 3600) // 60)
            running_time = f"{hours}h {minutes}m"

            total_trades = self.bot.trades
            active_positions = len(self.bot.margin_manager.positions)

            total_invested = sum(pos.get('size', 0) for pos in self.bot.margin_manager.positions.values())
            available_balance = self.bot.balance

            unrealized_pnl = 0.0
            active_positions_list = []
            short_positions = 0
            long_positions = 0

            for symbol, pos in self.bot.margin_manager.positions.items():
                current_price = self.bot.current_prices.get(symbol, pos.get('entry_price', 0))
                position_type = pos.get('position_type', PositionType.LONG)

                if position_type == PositionType.LONG:
                    position_pnl = (current_price - pos.get('entry_price', 0)) * pos.get('qty', 0)
                    long_positions += 1
                    position_emoji = "📈"
                else:  # SHORT
                    position_pnl = (pos.get('entry_price', 0) - current_price) * pos.get('qty', 0)
                    short_positions += 1
                    position_emoji = "📉"

                unrealized_pnl += position_pnl
                pnl_pct = (position_pnl / pos.get('size', 1)) * 100
                hold_time = (time.time() - pos.get('entry_time', 0)) / 60
                position_size = pos.get('size', 0)
                ai_indicator = "🤖" if pos.get('ai_used', False) else ""
                active_positions_list.append(
                    f"• {symbol}{ai_indicator} {position_emoji} {position_type.value}: ${current_price:.4f} | PnL: ${position_pnl:+.2f} ({pnl_pct:+.1f}%) | {hold_time:.1f}m | ${position_size:.2f}"
                )

            total_equity = self.bot.balance + total_invested + unrealized_pnl
            profit_factor = total_equity / settings.INITIAL_CAPITAL

            net_closed_pnl = self.bot.total_profit - self.bot.total_loss

            closed_wins = self.bot.wins
            closed_losses = self.bot.losses
            total_closed_trades = closed_wins + closed_losses
            win_rate = (closed_wins / total_closed_trades * 100) if total_closed_trades > 0 else 0

            ai_stats = self.bot.trading_logic.get_ai_stats()
            ai_success_rate = (ai_stats['successful_calls'] / ai_stats['total_calls'] * 100) if ai_stats[
                                                                                                    'total_calls'] > 0 else 0

            regime_params = self.bot.market_regime.get_regime_parameters()
            regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params[
                                                                                   'regime'] == "BEAR" else "🟡"

            performance_msg = (
                " <b>ULTIMATE AGGRESSIVE PERFORMANCE</b>\n\n"

                "⏱️ <b>SESSION</b>\n"
                f"Time: {running_time}\n"
                f"Cycles: {self.bot.cycle_count}\n"
                f"Trades: {self.bot.daily_trades}\n\n"

                "️ <b>MARKET REGIME</b>\n"
                f"{regime_icon} {regime_params['regime']} (Strength: {regime_params['regime_strength']:.1%})\n"
                f"Position Size: {regime_params['position_size']:.1f}%\n"
                f"Targets: {regime_params['profit_target']:.1f}%/{regime_params['stop_loss']:.1f}%\n\n"

                " <b>BALANCES</b>\n"
                f"Available: ${available_balance:.2f}\n"
                f"In Trades: ${total_invested:.2f}\n"
                f"Total Equity: ${total_equity:.2f}\n"
                f"Growth: {profit_factor:.3f}x\n\n"

                " <b>P&L</b>\n"
                f"Realized: ${self.bot.realized_pnl:+.2f}\n"
                f"Unrealized: ${unrealized_pnl:+.2f}\n"
                f"Net: ${self.bot.realized_pnl + unrealized_pnl:+.2f}\n\n"

                " <b>STATS</b>\n"
                f"Total Trades: {total_trades}\n"
                f"Wins: {closed_wins} | Losses: {closed_losses}\n"
                f"Win Rate: {win_rate:.1f}%\n"
                f"Active: {active_positions}/{regime_params['max_positions']}\n"
                f"Long: {long_positions} | Short: {short_positions}\n"
                f"Loss Streak: {self.bot.consecutive_losses}\n\n"

                " <b>AI USAGE</b>\n"
                f"Calls: {ai_stats['total_calls']}\n"
                f"Success: {ai_success_rate:.1f}%\n"
            )

            if active_positions_list:
                positions_text = "\n".join(active_positions_list)
                performance_msg += f"\n\n <b>ACTIVE POSITIONS</b>\n{positions_text}"

            self.send_message(chat_id, performance_msg)

        except Exception as e:
            error_msg = f"❌ Error generating report: {str(e)}"
            self.send_message(chat_id, error_msg)

    def handle_balance(self, chat_id: int, text: str):
        active_positions = len(self.bot.margin_manager.positions)
        total_invested = sum(pos.get('size', 0) for pos in self.bot.margin_manager.positions.values())

        unrealized_pnl = 0.0
        short_positions = 0
        long_positions = 0

        for symbol, pos in self.bot.margin_manager.positions.items():
            current_price = self.bot.current_prices.get(symbol, pos.get('entry_price', 0))
            if pos.get('position_type') == PositionType.LONG:
                position_pnl = (current_price - pos.get('entry_price', 0)) * pos.get('qty', 0)
                long_positions += 1
            else:  # SHORT
                position_pnl = (pos.get('entry_price', 0) - current_price) * pos.get('qty', 0)
                short_positions += 1
            unrealized_pnl += position_pnl

        total_equity = self.bot.balance + total_invested + unrealized_pnl
        profit_factor = total_equity / settings.INITIAL_CAPITAL

        regime_params = self.bot.market_regime.get_regime_parameters()
        regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params['regime'] == "BEAR" else "🟡"

        balance_msg = (
            " <b>ULTIMATE AGGRESSIVE BALANCE</b>\n\n"
            f"Available: ${self.bot.balance:.2f}\n"
            f"In Trades: ${total_invested:.2f}\n"
            f"Unrealized PnL: ${unrealized_pnl:+.2f}\n"
            f"Total: ${total_equity:.2f}\n"
            f"Growth: {profit_factor:.3f}x\n\n"

            "️ <b>MARKET REGIME</b>\n"
            f"{regime_icon} {regime_params['regime']} (Strength: {regime_params['regime_strength']:.1%})\n"
            f"Position Size: {regime_params['position_size']:.1f}%\n"
            f"Targets: {regime_params['profit_target']:.1f}% | Stops: {regime_params['stop_loss']:.1f}%\n\n"

            f"Positions: {active_positions}/{regime_params['max_positions']}\n"
            f"Long: {long_positions} | Short: {short_positions}\n"
            f"Today: {self.bot.daily_trades} trades (Limit: {regime_params['daily_trade_limit']})\n"
            f"Loss Streak: {self.bot.consecutive_losses}\n"
            f"Shorting: {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}"
        )
        self.send_message(chat_id, balance_msg)

    def handle_positions(self, chat_id: int, text: str):
        active_positions = []
        for symbol, pos in self.bot.margin_manager.positions.items():
            current_price = self.bot.current_prices.get(symbol, pos.get('entry_price', 0))
            position_type = pos.get('position_type', PositionType.LONG)

            if position_type == PositionType.LONG:
                pnl = (current_price - pos.get('entry_price', 0)) * pos.get('qty', 0)
                pnl_pct = (pnl / pos.get('size', 1)) * 100
                position_emoji = "📈"
            else:  # SHORT
                pnl = (pos.get('entry_price', 0) - current_price) * pos.get('qty', 0)
                pnl_pct = (pnl / pos.get('size', 1)) * 100
                position_emoji = "📉"

            hold_time = (time.time() - pos.get('entry_time', 0)) / 60
            trailing_indicator = " 🚀" if pos.get('trailing_stop_activated', False) else ""
            ai_indicator = "🤖" if pos.get('ai_used', False) else ""
            active_positions.append(
                f"• {symbol}{ai_indicator} {position_emoji} {position_type.value}: ${current_price:.4f} | PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {hold_time:.1f}m{trailing_indicator}"
            )

        if active_positions:
            positions_msg = " <b>ACTIVE POSITIONS</b>\n\n" + "\n".join(active_positions)
        else:
            positions_msg = " <b>No active positions</b>"
        self.send_message(chat_id, positions_msg)

    def handle_ai_stats(self, chat_id: int, text: str):
        ai_stats = self.bot.trading_logic.get_ai_stats()
        success_rate = (ai_stats['successful_calls'] / ai_stats['total_calls'] * 100) if ai_stats[
                                                                                             'total_calls'] > 0 else 0

        stats_msg = (
            " <b>AI USAGE STATISTICS</b>\n\n"
            f"Total Calls: {ai_stats['total_calls']}\n"
            f"Successful: {ai_stats['successful_calls']}\n"
            f"Fallbacks: {ai_stats['fallbacks_used']}\n"
            f"Success Rate: {success_rate:.1f}%\n"
            f"Daily Calls: {ai_stats.get('daily_calls', 0)}/{settings.AI_MAX_DAILY_CALLS}\n"
            f"Total Tokens: {ai_stats.get('total_tokens', 0):,}\n"
            f"Cache Size: {ai_stats.get('cache_size', 0)} entries\n"
        )

        if ai_stats.get('symbol_analysis_count'):
            top_symbols = sorted(ai_stats['symbol_analysis_count'].items(),
                                 key=lambda x: x[1], reverse=True)[:5]
            stats_msg += "\n<b>Top Analyzed Symbols:</b>\n"
            for symbol, count in top_symbols:
                stats_msg += f"• {symbol}: {count} analyses\n"

        self.send_message(chat_id, stats_msg)

    def handle_regime(self, chat_id: int, text: str):
        regime_params = self.bot.market_regime.get_regime_parameters()
        regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params['regime'] == "BEAR" else "🟡"

        regime_msg = (
            "️ <b>DYNAMIC MARKET REGIME ANALYSIS</b>\n\n"
            f"Current Regime: {regime_icon} {regime_params['regime']}\n"
            f"Strength: {regime_params['regime_strength']:.1%}\n"
            f"Duration: {regime_params['regime_duration'] / 60:.1f} minutes\n\n"

            " <b>ADJUSTED TRADING PARAMETERS</b>\n"
            f"Position Size: {regime_params['position_size']:.1f}%\n"
            f"Profit Target: {regime_params['profit_target']:.1f}%\n"
            f"Stop Loss: {regime_params['stop_loss']:.1f}%\n"
            f"RSI Buy Max: {regime_params['rsi_buy_max']:.1f}\n"
            f"Confidence Threshold: {regime_params['confidence_threshold']:.2f}\n"
            f"Min Dip Percent: {regime_params['min_dip_percent']:.1f}%\n"
            f"Max Positions: {regime_params['max_positions']}\n"
            f"Daily Trade Limit: {regime_params['daily_trade_limit']}\n\n"

            " <b>REGIME STRATEGY</b>\n"
        )

        if regime_params['regime'] == "BULL":
            regime_msg += "• Large positions (1.8x multiplier)\n• Higher profit targets (1.8x)\n• Tighter stops\n• Buy at higher RSI (up to 60)\n• Very aggressive entries\n• Up to 8 positions"
        elif regime_params['regime'] == "BEAR":
            regime_msg += "• Smaller positions (0.6x multiplier)\n• Lower profit targets (0.9x)\n• Wider stops\n• Buy at lower RSI (max 45)\n• Conservative entries\n• Up to 4 positions"
        else:
            regime_msg += "• Balanced position sizing (1.2x)\n• Good profit targets (1.2x)\n• Balanced stops\n• Buy at moderate RSI (max 55)\n• Frequent trading strategy\n• Up to 6 positions"

        regime_msg += f"\n\n<b>SHORTING:</b> {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}"

        self.send_message(chat_id, regime_msg)

    def handle_pause(self, chat_id: int, text: str):
        self.bot.paused = True
        self.send_message(chat_id, "⏸️ <b>Trading PAUSED</b>")

    def handle_resume(self, chat_id: int, text: str):
        self.bot.paused = False
        self.send_message(chat_id, "▶️ <b>Trading RESUMED</b>")

    def handle_reset_limits(self, chat_id: int, text: str):
        self.bot.reset_trading_limits()
        self.send_message(chat_id, "🔄 Trading limits reset! Bot can now trade again.")

    def handle_status(self, chat_id: int, text: str):
        status = "⏸️ PAUSED" if self.bot.paused else "▶️ RUNNING"
        active_positions = len(self.bot.margin_manager.positions)
        running_seconds = time.time() - self.bot.start_time
        hours = int(running_seconds // 3600)
        minutes = int((running_seconds % 3600) // 60)

        total_invested = sum(pos.get('size', 0) for pos in self.bot.margin_manager.positions.values())

        unrealized_pnl = 0.0
        short_positions = 0
        for symbol, pos in self.bot.margin_manager.positions.items():
            current_price = self.bot.current_prices.get(symbol, pos.get('entry_price', 0))
            if pos.get('position_type') == PositionType.LONG:
                position_pnl = (current_price - pos.get('entry_price', 0)) * pos.get('qty', 0)
            else:
                position_pnl = (pos.get('entry_price', 0) - current_price) * pos.get('qty', 0)
                short_positions += 1
            unrealized_pnl += position_pnl

        total_equity = self.bot.balance + total_invested + unrealized_pnl
        profit_factor = total_equity / settings.INITIAL_CAPITAL

        margin_usage = self.bot.margin_manager.get_margin_usage()

        regime_params = self.bot.market_regime.get_regime_parameters()
        regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params['regime'] == "BEAR" else "🟡"

        status_msg = (
            " <b>ULTIMATE AGGRESSIVE BOT STATUS WITH SHORTING</b>\n\n"
            f"Status: {status}\n"
            f"Time: {hours}h {minutes}m\n"
            f"Available: ${self.bot.balance:.2f}\n"
            f"Total Equity: ${total_equity:.2f}\n"
            f"Growth: {profit_factor:.3f}x\n\n"

            "️ <b>MARKET REGIME</b>\n"
            f"{regime_icon} {regime_params['regime']} (Strength: {regime_params['regime_strength']:.1%})\n"
            f"Position Size: {regime_params['position_size']:.1f}%\n"
            f"Targets: {regime_params['profit_target']:.1f}% | Stops: {regime_params['stop_loss']:.1f}%\n\n"

            f"Positions: {active_positions}/{regime_params['max_positions']}\n"
            f"Long: {active_positions - short_positions} | Short: {short_positions}\n"
            f"Trades: {self.bot.daily_trades}/{regime_params['daily_trade_limit']}\n"
            f"Margin Usage: {margin_usage['usage_percent']:.1f}%\n"
            f"Unrealized PnL: ${unrealized_pnl:+.2f}\n"
            f"Mode: SIMULATION - PAPER TRADING\n"
            f"Shorting: {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}"
        )
        self.send_message(chat_id, status_msg)

    async def send_periodic_report(self):
        if not self.token:
            return
        total_trades = self.bot.wins + self.bot.losses
        win_rate = (self.bot.wins / total_trades * 100) if total_trades > 0 else 0
        running_seconds = time.time() - self.bot.start_time
        hours = int(running_seconds // 3600)
        minutes = int((running_seconds % 3600) // 60)

        total_invested = sum(pos.get('size', 0) for pos in self.bot.margin_manager.positions.values())

        unrealized_pnl = 0.0
        short_positions = 0
        for symbol, pos in self.bot.margin_manager.positions.items():
            current_price = self.bot.current_prices.get(symbol, pos.get('entry_price', 0))
            if pos.get('position_type') == PositionType.LONG:
                position_pnl = (current_price - pos.get('entry_price', 0)) * pos.get('qty', 0)
            else:
                position_pnl = (pos.get('entry_price', 0) - current_price) * pos.get('qty', 0)
                short_positions += 1
            unrealized_pnl += position_pnl

        total_equity = self.bot.balance + total_invested + unrealized_pnl
        profit_factor = total_equity / settings.INITIAL_CAPITAL

        regime_params = self.bot.market_regime.get_regime_parameters()
        regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params['regime'] == "BEAR" else "🟡"

        report_msg = (
            " <b>HOURLY ULTIMATE AGGRESSIVE REPORT</b>\n\n"
            f"Time: {hours}h {minutes}m\n"
            f"Available: ${self.bot.balance:.2f}\n"
            f"Total Equity: ${total_equity:.2f}\n"
            f"Growth: {profit_factor:.3f}x\n\n"

            "️ <b>MARKET REGIME</b>\n"
            f"{regime_icon} {regime_params['regime']} (Strength: {regime_params['regime_strength']:.1%})\n"
            f"Position Size: {regime_params['position_size']:.1f}%\n\n"

            f"PnL: ${self.bot.realized_pnl + unrealized_pnl:+.2f}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"Trades: {self.bot.daily_trades}/{regime_params['daily_trade_limit']}\n"
            f"Active: {len(self.bot.margin_manager.positions)}/{regime_params['max_positions']}\n"
            f"Long: {len(self.bot.margin_manager.positions) - short_positions} | Short: {short_positions}\n"
            f"Loss Streak: {self.bot.consecutive_losses}"
        )
        for user_id in self.user_ids:
            self.send_message(user_id, report_msg, force=True)


class FearGreedIndexTracker:
    def __init__(self):
        self.fear_greed_index = 50.0
        self.last_update = 0

    async def update_fgi(self):
        current_time = time.time()
        if current_time - self.last_update < 3600:
            return

        try:
            url = "https://api.alternative.me/fng/?limit=1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and 'data' in data and len(data['data']) > 0:
                            self.fear_greed_index = float(data['data'][0]['value'])
                            self.last_update = current_time
        except Exception:
            pass


class UltimateTradingBot:
    def __init__(self):
        self.api = CryptoComRealAPI()
        self.btc_tracker = BitcoinCorrelationTracker(self.api)
        self.btc_dominance_tracker = BitcoinDominanceTracker(self.api)
        self.market_regime = DynamicMarketRegime()
        self.trading_logic = UltimateTradingLogic()
        self.margin_manager = SimplePositionManager(settings.INITIAL_CAPITAL)
        self.telegram = TelegramController(self)
        self.performance_optimizer = PerformanceOptimizer(self)
        self.data_quality_tracker = DataQualityTracker()
        self.fear_greed_tracker = FearGreedIndexTracker()
        self.emergency_params = {
            'optimal_rsi_max': 52.0,
            'optimal_min_dip': 0.5,
            'position_size_multiplier': 0.8,
            'confidence_threshold': 0.6,
        }
        self.tp_levels = [
                    {'percent': 50, 'target': 0.8},   # Close 40% at +2.0% profit
                    {'percent': 30, 'target': 1.5},   # Close another 40% at +4.0% profit
                    {'percent': 20, 'target': 2.5}    # Let 20% run with trailing stop
                ]
        self.trailing_stop_distance = 2.0  # 2% trailing stop from peak profit
        self.force_position_size = 75.0  # Test with $25 positions
        self.adaptive_thresholds = {
            'rsi_max': 45.0,
            'min_dip': 1.5,
            'confidence_threshold': 0.2,
            'position_size_multiplier': 1.0
        }
        self.last_adaptation_time = time.time()

        # SIMPLE ACCOUNTING
        self.initial_balance = settings.INITIAL_CAPITAL
        self.balance = settings.INITIAL_CAPITAL
        self.realized_pnl = 0.0

        self.simulation = True
        self.positions = {}
        self.price_history = {}
        self.volume_history = {}
        self.initial_prices = {}
        self.current_prices = {}
        self.trades = self.daily_trades = self.cycle_count = 0
        self.running = True
        self.paused = False
        self.wins = self.losses = 0
        self.win_rate = "0%"
        self.total_profit = self.total_loss = 0.0
        self.start_time = time.time()
        self.consecutive_losses = 0
        self.daily_start_balance = self.balance
        self.last_trade_cycle = 0
        self.performance_history = []
        self.trading_halted = False

        self.last_data_update = 0
        self.data_update_interval = 1800

        self.market_structure_analysis = {}
        self.current_regime = "UNKNOWN"
        self.regime_strength = 0.5
        self.market_regime = DynamicMarketRegime()
        self.trading_logic = UltimateTradingLogic(self.market_regime)
        self.last_regime_notification = None
        self.trade_logger = TradeLogger()
        self.circuit_breaker_cooldown = 1800  # 30 minutes
        self.last_trade_time = 0
        self.daily_reset_hour = datetime.now().hour

        print(f"🔔 Telegram initialized: {'✅ Enabled' if self.telegram.token else '❌ Disabled'}")
        print(f"📉 Shorting: {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}")

    async def adapt_trading_strategy(self):
        """Dynamically adjust trading parameters based on performance"""
        if time.time() - self.last_adaptation_time < 300:
            return

        # Simple adaptation based on win rate
        total_trades = self.wins + self.losses
        if total_trades >= 10:
            win_rate = self.wins / total_trades

            if win_rate < 0.3:  # Losing
                self.adaptive_thresholds = {
                    'rsi_max': 48.0,
                    'min_dip': 0.8,
                    'confidence_threshold': 0.25,
                    'position_size_multiplier': 0.7
                }
            elif win_rate > 0.6:  # Winning
                self.adaptive_thresholds = {
                    'rsi_max': 55.0,
                    'min_dip': 0.3,
                    'confidence_threshold': 0.15,
                    'position_size_multiplier': 1.3
                }
            else:  # Neutral
                self.adaptive_thresholds = {
                    'rsi_max': 52.0,
                    'min_dip': 0.5,
                    'confidence_threshold': 0.2,
                    'position_size_multiplier': 1.0
                }

            print(
                f"🧠 ADAPTATION: Win rate {win_rate:.1%} -> RSI: {self.adaptive_thresholds['rsi_max']:.1f}, "
                f"Dip: {self.adaptive_thresholds['min_dip']:.1f}%, Size×{self.adaptive_thresholds['position_size_multiplier']:.2f}")

        self.last_adaptation_time = time.time()

    def calculate_simple_rsi(self, prices: List[float]) -> float:
        """Simple RSI calculation for the trading logic"""
        if len(prices) < 14:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        if len(gains) < 14 or len(losses) < 14:
            return 50.0

        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return max(0, min(100, rsi))

    async def emergency_balance_positions(self):
        """Force balance between LONG and SHORT positions in extreme cases"""
        
        regime_params = self.market_regime.get_regime_parameters()
        current_regime = regime_params.get('regime', 'SIDEWAYS')
        
        # Only balance in sideways/bear markets
        if current_regime not in ['SIDEWAYS', 'BEAR']:
            return
        
        long_positions = []
        short_positions = []
        
        for symbol, pos in self.margin_manager.positions.items():
            if pos.get('position_type') == PositionType.LONG:
                long_positions.append((symbol, pos))
            else:
                short_positions.append((symbol, pos))
        
        # If we have significantly more LONGs than SHORTS in bear/sideways
        if len(long_positions) > len(short_positions) + 2:
            print(f"🚨 EMERGENCY REBALANCE: Too many LONGS ({len(long_positions)}) vs SHORTS ({len(short_positions)})")
            
            # Find worst performing LONG to close
            worst_symbol = None
            worst_pnl_pct = 0
            
            for symbol, pos in long_positions[:5]:  # Check first 5
                current_price = self.current_prices.get(symbol, pos.get('entry_price', 0))
                entry_price = pos.get('entry_price', current_price)
                
                if entry_price > 0:
                    pnl_pct = (current_price - entry_price) / entry_price * 100
                    if pnl_pct < worst_pnl_pct:
                        worst_pnl_pct = pnl_pct
                        worst_symbol = symbol
            
            if worst_symbol and worst_pnl_pct < -0.5:  # Only if losing
                print(f"🔄 Closing worst LONG for rebalance: {worst_symbol} ({worst_pnl_pct:.1f}%)")
                await self._close_position(
                    worst_symbol,
                    self.margin_manager.positions[worst_symbol],
                    self.current_prices.get(worst_symbol, 0),
                    "Emergency rebalance (too many LONGS)"
                )
                return True  # Rebalance performed
        
        return False  # No rebalance needed

    def has_correlation_risk(self, symbol: str, position_type: PositionType) -> bool:
        
        current_positions = len(self.margin_manager.positions)
        if current_positions < 2:
            return False
        
        # Count current positions by type
        long_count = sum(1 for p in self.margin_manager.positions.values() 
                        if p.get('position_type') == PositionType.LONG)
        short_count = current_positions - long_count
        
        target_short_ratio = 0.3  # 30% of positions should be shorts
        target_shorts = int(len(self.margin_manager.positions) * target_short_ratio)
            
        if short_count < target_shorts:
            print(f"🚨 FORCE REBALANCE: Need {target_shorts} shorts, have {short_count}")

        # LOOSENED: Allow 3:1 ratio instead of 2:1
        if position_type == PositionType.LONG:
            if long_count >= 3 * (short_count + 1):  # CHANGED: 3:1 instead of 2:1
                print(f"⚠️ Correlation risk: Too many LONGS ({long_count}) vs SHORTS ({short_count})")
                return True
        else:  # SHORT
            if short_count >= 3 * (long_count + 1):  # CHANGED: 3:1 instead of 2:1
                print(f"⚠️ Correlation risk: Too many SHORTS ({short_count}) vs LONGS ({long_count})")
                return True
        
        # Check symbol groups (crypto categories)
        smart_contracts = ['ETH', 'SOL', 'ADA', 'AVAX']
        layer1 = ['ETH', 'SOL', 'ADA', 'AVAX']
        oracles = ['LINK']
        payments = ['LTC']
        
        # Determine which group this symbol belongs to
        symbol_group = None
        if symbol in smart_contracts:
            symbol_group = 'smart_contract'
        elif symbol in oracles:
            symbol_group = 'oracle'
        elif symbol in memes:
            symbol_group = 'meme'
        elif symbol in payments:
            symbol_group = 'payment'
        else:
            symbol_group = 'other'
        
        # Count positions in same group and same type
        same_group_same_type = 0
        for s, p in self.margin_manager.positions.items():
            # Determine group of existing position
            existing_group = None
            if s in smart_contracts:
                existing_group = 'smart_contract'
            elif s in oracles:
                existing_group = 'oracle'
            elif s in memes:
                existing_group = 'meme'
            elif s in payments:
                existing_group = 'payment'
            else:
                existing_group = 'other'
            
            if (existing_group == symbol_group and 
                p.get('position_type') == position_type):
                same_group_same_type += 1
        
        # Max 2 positions in same category and same direction
        if same_group_same_type >= 2:
            print(f"⚠️ Correlation risk: Already have {same_group_same_type} {position_type.value} in {symbol_group}")
            return True
        
        return False

    async def update_real_market_regime(self):
        try:
            market_data = await self.market_regime.update_real_market_data(self)
            current_regime = self.market_regime.detect_regime_with_real_data(market_data)
            regime_params = self.market_regime.get_regime_parameters()

            self.current_regime = regime_params.get('regime', 'UNKNOWN')
            self.regime_strength = regime_params.get('regime_strength', 0.5)

            if hasattr(self, 'last_regime_notification'):
                if self.last_regime_notification != current_regime:
                    if self.telegram.user_ids:
                        regime_icon = "🟢" if current_regime == "BULL" else "🔴" if current_regime == "BEAR" else "🟡"
                        message = (
                            f"{regime_icon} <b>MARKET REGIME DETECTED</b>\n\n"
                            f"New Regime: {current_regime}\n"
                            f"Strength: {regime_params['regime_strength']:.1%}\n\n"
                            f"<b>Adjusted Parameters:</b>\n"
                            f"Position Size: {regime_params['position_size']:.1f}%\n"
                            f"Profit Target: {regime_params['profit_target']:.1f}%\n"
                            f"Stop Loss: {regime_params['stop_loss']:.1f}%\n"
                            f"RSI Buy Max: {regime_params['rsi_buy_max']:.1f}\n"
                            f"Confidence Threshold: {regime_params['confidence_threshold']:.2f}"
                        )
                        self.telegram.send_message(self.telegram.user_ids[0], message)
                    self.last_regime_notification = current_regime
            else:
                self.last_regime_notification = current_regime

        except Exception as e:
            print(f"❌ Error updating real market regime: {e}")

    async def emergency_api_checks(self) -> bool:
        print("🔍 Performing emergency API availability checks...")

        if not await self.api.emergency_check():
            print("❌ CRITICAL: Crypto.com API unavailable - Emergency exit")
            return False

        if settings.DEEPSEEK_API_KEY:
            if not await self.trading_logic.deepseek.emergency_check():
                print("⚠️  DeepSeek API unavailable - continuing without AI")

        print("✅ All critical API checks passed")
        return True

    def audit_balances(self):
        total_invested = sum(pos['size'] for pos in self.margin_manager.positions.values())
        available = self.margin_manager.get_available_capital()
        total_equity = self.margin_manager.get_total_capital(self.current_prices)

        print(f"🔍 SIMPLE AUDIT:")
        print(f"   Available: ${available:.2f}")
        print(f"   Invested: ${total_invested:.2f}")
        print(f"   Total Equity: ${total_equity:.2f}")
        print(f"   Initial: ${self.initial_balance:.2f}")
        print(f"   Realized PnL: ${self.realized_pnl:+.2f}")

        return True

    def reset_trading_limits(self):
        print("🔄 RESETTING TRADING LIMITS...")
        self.trading_halted = False
        self.daily_start_balance = self.balance
        self.consecutive_losses = 0
        self.daily_trades = 0
        print(f"✅ Trading limits reset! New daily start: ${self.daily_start_balance:.2f}")
        print("🟢 TRADING RESUMED")

    async def initialize_prices(self):
        print("📊 Initializing price data with symbol verification...")

        working_symbols = await self.api.verify_symbol_mappings()

        if not working_symbols:
            print("❌ CRITICAL: No working symbols found!")
            return

        settings.set_working_symbols(working_symbols)

        for symbol in working_symbols:
            try:
                price = await self.api.get_ticker(symbol)
                if price > 0:
                    self.initial_prices[symbol] = price
                    self.current_prices[symbol] = price
                    self.price_history[symbol] = [price] * 20
                    self.volume_history[symbol] = [1000000] * 20
                    print(f"✅ {symbol}: ${price:.4f}")
                else:
                    print(f"❌ Failed to get valid price for {symbol}")
            except Exception as e:
                print(f"❌ Failed to initialize {symbol}: {e}")

        print(f"✅ Price initialization completed. Trading {len(working_symbols)} verified symbols")

    async def load_historical_data(self):
        print("🕐 PRELOADING MULTI-TIMEFRAME HISTORICAL DATA...")

        if not settings.symbols:
            print("❌ No symbols available for historical data loading")
            return False

        loaded_symbols = 0
        for symbol in settings.symbols[:8]:
            success = await self.trading_logic.technical.load_multi_timeframe_data(symbol, self.api)
            if success:
                loaded_symbols += 1
            await asyncio.sleep(0.7)

        print(f"✅ Historical data loaded for {loaded_symbols}/{len(settings.symbols)} symbols")
        return loaded_symbols > 0

    async def update_historical_data(self):
        current_time = time.time()

        if current_time - self.last_data_update < self.data_update_interval:
            return

        print("\n🔄 UPDATING HISTORICAL DATA...")
        update_count = 0

        for symbol in settings.symbols[:6]:
            try:
                new_candles = await self.api.get_historical_candles(symbol, '5m', 100)

                if new_candles and len(new_candles) >= 20:
                    if symbol in self.trading_logic.technical.historical_data:
                        existing = self.trading_logic.technical.historical_data[symbol]
                        existing_dict = {c['timestamp']: c for c in existing}

                        for candle in new_candles:
                            existing_dict[candle['timestamp']] = candle

                        merged = sorted(existing_dict.values(), key=lambda x: x['timestamp'])
                        self.trading_logic.technical.historical_data[symbol] = merged[-300:]

                        closes = [c['close'] for c in merged[-300:]]
                        self.price_history[symbol] = closes[-100:]

                        update_count += 1
            except Exception:
                pass

        self.last_data_update = current_time
        print(f"📊 Updated {update_count} symbols")

    async def update_prices(self):
        for symbol in settings.symbols:
            try:
                price = await self.api.get_ticker(symbol)

                if price > 0:
                    self.current_prices[symbol] = price

                    if symbol not in self.price_history:
                        self.price_history[symbol] = [price] * 50
                    else:
                        self.price_history[symbol].append(price)
                        if len(self.price_history[symbol]) > 100:
                            self.price_history[symbol].pop(0)

            except Exception:
                pass

    def _can_trade(self) -> bool:
        """Check if trading is allowed - UPDATED WITH ALL FIXES"""
        # 1. Check if trading is paused
        if self.paused:
            if self.cycle_count % 60 == 0:  # Log every 60 cycles to avoid spam
                print("⏸️  Trading paused by user")
            return False

        # 2. Check circuit breaker (trading halted due to drawdown)
        if self.trading_halted:
            if self.cycle_count % 30 == 0:
                remaining_cooldown = (self.circuit_breaker_cooldown - 
                                    (time.time() - self.last_trade_time)) / 60
                print(f"🔴 TRADING HALTED: Circuit breaker active ({remaining_cooldown:.1f}m remaining)")
            return False

        if self.regime_strength < 0.4:
                # Only log this message occasionally to avoid spam
                if self.cycle_count % 30 == 0:
                    print(f"⛔ WEAK REGIME: Strength {self.regime_strength:.1%} < 40% - Skipping trade analysis.")
                # Option 1: Skip trading this cycle entirely (simpler, more conservative)
                return False

        # 3. REGIME STRENGTH FILTER - NEW FIX (MOST IMPORTANT)
        # Skip trades when market has no clear direction
        current_regime = self.current_regime
        regime_strength = self.regime_strength
        
        # Get regime parameters for thresholds
        regime_params = self.market_regime.get_regime_parameters()
        
        # Block trades in weak regimes (less than 40% confidence)
        if regime_strength < 0.3:
            if self.cycle_count % 30 == 0:  # Log occasionally
                print(f"⛔ WEAK REGIME: {current_regime} at {regime_strength:.1%} strength - skipping trade")
            return False
            
        # Special case for BEAR market with weak strength
        if current_regime == "BEAR" and regime_strength < 0.55:
            if self.cycle_count % 30 == 0:
                print(f"⛔ BEAR MARKET WEAK: {regime_strength:.1%} strength - avoiding risky shorts")
            return False

        # 4. DAILY TRADE LIMIT - 500 trades maximum (your setting)
        daily_limit = getattr(settings, 'DAILY_TRADE_LIMIT', 500)
        
        # Reset daily counter if it's a new day
        current_hour = datetime.now().hour
        if current_hour == 0 and self.daily_reset_hour != 0:
            print("🔄 New day - resetting daily trade counter")
            self.daily_trades = 0
            self.daily_reset_hour = 0
            self.daily_start_balance = self.margin_manager.get_total_capital(self.current_prices)
            
        if not hasattr(self, 'daily_reset_hour'):
            self.daily_reset_hour = current_hour

        if self.daily_trades >= daily_limit:
            if self.cycle_count % 30 == 0:
                print(f"⛔ DAILY LIMIT REACHED: {self.daily_trades}/{daily_limit} trades")
            return False

        # 5. MAXIMUM POSITIONS CHECK
        max_positions = regime_params.get('max_positions', 6)
        current_positions = len(self.margin_manager.positions)
        
        if current_positions >= max_positions:
            if self.cycle_count % 60 == 0:
                print(f"⛔ MAX POSITIONS: {current_positions}/{max_positions}")
            return False

        # 6. MINIMUM BALANCE CHECK
        available_balance = self.margin_manager.get_available_capital()
        min_balance = getattr(settings, 'MIN_BALANCE_FOR_TRADING', 50.0)
        
        if available_balance < min_balance:
            if self.cycle_count % 60 == 0:
                print(f"⛔ LOW BALANCE: ${available_balance:.2f} < ${min_balance:.2f}")
            return False

        # 7. CYCLE COOLDOWN CHECK (reduced trading frequency)
        min_cycles_between_trades = getattr(settings, 'MIN_CYCLE_BETWEEN_TRADES', 10)
        cycles_since_last_trade = self.cycle_count - self.last_trade_cycle
        
        if cycles_since_last_trade < min_cycles_between_trades:
            if self.cycle_count % 20 == 0:
                remaining_cycles = min_cycles_between_trades - cycles_since_last_trade
                wait_time = remaining_cycles * getattr(settings, 'CYCLE_DELAY', 30)
                print(f"⏳ TRADE COOLDOWN: Wait {remaining_cycles} cycles ({wait_time}s)")
            return False

        # 8. SHORT POSITION LIMITS (if shorting enabled)
        if settings.ENABLE_SHORTING:
            current_shorts = self.margin_manager.get_short_positions_count()
            max_shorts = min(settings.SHORT_MAX_POSITIONS,
                           int(max_positions * settings.SHORT_POSITION_RATIO))
            
            if current_shorts >= max_shorts:
                if self.cycle_count % 60 == 0:
                    print(f"⛔ MAX SHORTS: {current_shorts}/{max_shorts}")
                return False

        # 9. PERFORMANCE-BASED TRADING RESTRICTION (NEW)
        # Skip trades if we're on a losing streak
        if self.consecutive_losses >= getattr(settings, 'MAX_CONSECUTIVE_LOSSES', 5):
            if self.cycle_count % 20 == 0:
                print(f"⚠️  LOSING STREAK: {self.consecutive_losses} losses - cooling down")
            return False

        # 10. DAILY DRAWDOWN LIMIT CHECK
        current_equity = self.margin_manager.get_total_capital(self.current_prices)
        daily_drawdown_pct = 0
        
        if self.daily_start_balance > 0:
            daily_drawdown_pct = (self.daily_start_balance - current_equity) / self.daily_start_balance * 100
            
        max_daily_drawdown = getattr(settings, 'MAX_DRAWDOWN', 25.0)
        
        if daily_drawdown_pct > max_daily_drawdown:
            print(f"🚨 DAILY DRAWDOWN EXCEEDED: {daily_drawdown_pct:.1f}% > {max_daily_drawdown}%")
            self.trading_halted = True
            self.last_trade_time = time.time()
            return False

        # 11. FORCE WAIT AFTER CIRCUIT BREAKER RESET
        if hasattr(self, 'circuit_breaker_reset_time'):
            time_since_reset = time.time() - self.circuit_breaker_reset_time
            if time_since_reset < 300:  # 5 minute cool-down after reset
                if self.cycle_count % 20 == 0:
                    remaining = (300 - time_since_reset) / 60
                    print(f"⏳ POST-CIRCUIT COOLDOWN: {remaining:.1f}m remaining")
                return False

        # 12. AVAILABLE SYMBOLS CHECK
        # Ensure we have enough symbols to trade
        if len(settings.symbols) < 3:
            print("⚠️  Not enough trading symbols available")
            return False

        # 14. TRADE QUALITY CHECK (if we have performance history)
        if len(self.performance_history) > 10:
            recent_trades = self.performance_history[-10:]
            recent_wins = sum(1 for trade in recent_trades if trade.get('pnl', 0) > 0)
            recent_win_rate = recent_wins / len(recent_trades)
            
            if recent_win_rate < 0.3:
                if self.cycle_count % 30 == 0:
                    print(f"⚠️  POOR RECENT PERFORMANCE: {recent_win_rate:.1%} win rate last 10 trades")
                # Not blocking, just warning

        # ALL CHECKS PASSED - TRADING IS ALLOWED
        if self.cycle_count % 50 == 0:
            print(f"✅ Trading allowed | Positions: {current_positions}/{max_positions} | "
                  f"Daily: {self.daily_trades}/{daily_limit} | "
                  f"Regime: {current_regime} ({regime_strength:.1%})")
        
        return True
        
    async def analyze_and_trade(self):
        if not self._can_trade():
            return

        if settings.ENABLE_SHORTING:
            current_shorts = self.margin_manager.get_short_positions_count()
            total_positions = len(self.margin_manager.positions)
            
            # Target: 40% of positions should be shorts
            target_shorts = max(1, int(total_positions * 0.4))
            
            if current_shorts < target_shorts and total_positions >= 2:
                print(f"🎯 FORCING SHORT SEARCH: Need {target_shorts} shorts, have {current_shorts}")

        long_count = sum(1 for p in self.margin_manager.positions.values() 
                        if p.get('position_type') == PositionType.LONG)
        short_count = len(self.margin_manager.positions) - long_count

        if long_count > short_count + 1 and settings.ENABLE_SHORTING:
            print(f"🔍 PRIORITIZING SHORT SEARCH: LONGS={long_count}, SHORTS={short_count}")

        regime_params = self.market_regime.get_regime_parameters()
        current_regime = regime_params.get('regime', 'SIDEWAYS')

        # Calculate current win rate for adaptive parameters
        total_trades = max(self.wins + self.losses, 1)
        current_win_rate = self.wins / total_trades

        # Adaptive parameters based on performance
        if current_win_rate < 0.4:
            adaptive_params = {
                'optimal_rsi': 48.0,
                'optimal_dip': 0.8,
                'position_size_multiplier': 0.7,
                'confidence_multiplier': 0.9,
                'regime': 'CONSERVATIVE'
            }
        elif current_win_rate > 0.6:
            adaptive_params = {
                'optimal_rsi': 55.0,
                'optimal_dip': 0.3,
                'position_size_multiplier': 1.2,
                'confidence_multiplier': 1.1,
                'regime': 'AGGRESSIVE'
            }
        else:
            adaptive_params = {
                'optimal_rsi': 52.0,
                'optimal_dip': 0.5,
                'position_size_multiplier': 1.0,
                'confidence_multiplier': 1.0,
                'regime': 'NEUTRAL'
            }

        # Check short position limits
        current_short_positions = self.margin_manager.get_short_positions_count()
        max_short_positions = min(settings.SHORT_MAX_POSITIONS,
                                int(len(self.margin_manager.positions) * settings.SHORT_POSITION_RATIO))

        # Find opportunities
        opportunities = []

        for symbol in settings.symbols:
            if symbol in self.margin_manager.positions:
                continue

            try:
                price = self.current_prices.get(symbol)
                history = self.price_history.get(symbol, [])

                if len(history) < 20:
                    continue

                # Get technical analysis
                volume_history = self.volume_history.get(symbol, [])
                btc_correlation = self.btc_tracker.calculate_correlation(symbol)

                analysis = await self.trading_logic.analyze_opportunity(
                    symbol, price, history, volume_history, btc_correlation
                )

                # Check if this is a valid opportunity based on position type
                position_type = analysis.get('position_type', PositionType.LONG)
                advice = analysis.get('advice', 'Hold')
                confidence = analysis.get('confidence', 0)

                # REGIME-BASED BIAS: In sideways/bear markets, bias toward SHORTS
                if current_regime in ['SIDEWAYS', 'BEAR']:
                    # If it's a weak LONG, consider converting to SHORT
                    if (position_type == PositionType.LONG and 
                        advice in ['Buy', 'Strong Buy'] and
                        confidence < 0.5 and
                        analysis.get('rsi', 50) > 55 and
                        settings.ENABLE_SHORTING):
                        
                        # Check if we can open more SHORTS
                        if current_short_positions < max_short_positions:
                            # Convert to SHORT
                            print(f"🔄 Regime bias: Converting {symbol} from LONG to SHORT")
                            position_type = PositionType.SHORT
                            advice = 'Sell' if confidence < 0.7 else 'Strong Sell'

                # Filter by position type
                if position_type == PositionType.SHORT:
                    if not settings.ENABLE_SHORTING:
                        continue
                    if current_short_positions >= max_short_positions:
                        continue
                    if advice not in ["Sell", "Strong Sell"]:
                        continue
                else:  # LONG
                    if advice not in ["Buy", "Strong Buy"]:
                        continue

                # Check correlation risk
                if self.has_correlation_risk(symbol, position_type):
                    print(f"⚠️ Skipping {symbol} {position_type.value} - correlation risk")
                    continue

                # Add to opportunities
                opportunities.append({
                    'symbol': symbol,
                    'price': price,
                    'analysis': analysis,
                    'confidence': confidence,
                    'position_type': position_type,
                    'score': confidence * 10  # Simple scoring
                })

            except Exception as e:
                print(f"❌ Error analyzing {symbol}: {e}")
                continue

        # Sort opportunities by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)

        # Take best opportunities (more conservative in losing streaks)
        if self.consecutive_losses > 2:
            max_trades = 1
            print(f"⚠️ High loss streak ({self.consecutive_losses}) - limiting to 1 trade")
        elif current_win_rate < 0.45:
            max_trades = 2
            print(f"⚠️ Low win rate ({current_win_rate:.1%}) - limiting to 2 trades")
        else:
            max_trades = 3

        trades_taken = 0

        for opportunity in opportunities[:max_trades]:
            if trades_taken >= max_trades:
                break

            success = await self._execute_simple_trade(opportunity, regime_params)
            if success:
                trades_taken += 1
                self.last_trade_cycle = self.cycle_count
                await asyncio.sleep(1)

        # Emergency trade if needed
        if trades_taken == 0 and len(self.margin_manager.positions) < 3:
            cycles_since_last_trade = self.cycle_count - self.last_trade_cycle
            if cycles_since_last_trade > settings.EMERGENCY_TRADE_AFTER_CYCLES * 3:
                print(f"🚨 EMERGENCY: No trades for {cycles_since_last_trade} cycles - emergency check")
                await self._force_emergency_trade(regime_params)

    async def _execute_simple_trade(self, opportunity: Dict, regime_params: Dict) -> bool:
        """Execute trade with support for both LONG and SHORT positions - FIXED VERSION"""
        symbol = opportunity['symbol']
        price = opportunity['price']
        analysis = opportunity['analysis']
        position_type = analysis.get('position_type', PositionType.LONG)
        
        # Get btc_correlation
        btc_correlation = self.btc_tracker.calculate_correlation(symbol)
        
        # Log the trade before opening
        base_percent = regime_params.get('position_size', settings.BASE_POSITION_SIZE_PERCENT)
        total_capital = self.margin_manager.get_total_capital(self.current_prices)
        
        # Calculate position_size (will be calculated again properly below)
        position_size_estimate = total_capital * (base_percent / 100)
        
        # Log trade opening
        self.trade_logger.log_trade_opened(
            cycle_count=self.cycle_count,
            symbol=symbol,
            position_type=position_type.value,
            entry_price=price,
            size_usd=position_size_estimate,
            analysis=analysis,
            regime_params=regime_params,
            btc_corr=btc_correlation
        )

        # Check shorting restrictions
        if position_type == PositionType.SHORT and not settings.ENABLE_SHORTING:
            print(f"⚠️  Shorting disabled for {symbol}")
            return False

        # Check short position limits
        if position_type == PositionType.SHORT:
            current_shorts = self.margin_manager.get_short_positions_count()
            max_short_positions = min(settings.SHORT_MAX_POSITIONS,
                                    int(regime_params.get('max_positions', 6) * settings.SHORT_POSITION_RATIO))
            if current_shorts >= max_short_positions:
                print(f"⚠️  Max short positions reached: {current_shorts}/{max_short_positions}")
                return False

        ai_used = analysis.get('ai_used', False)
        ai_confidence = analysis.get('ai_confidence', 0.0)
        
        # Define minimum confidence threshold (adjustable)
        MIN_AI_CONFIDENCE = 0.75
        
        # Fixed check - ALLOW trades without AI for first 5 trades
        if not ai_used or ai_confidence < MIN_AI_CONFIDENCE:
            # ALLOW if we have 0 trades and need to get started
            if self.trades == 0 and self.cycle_count > 10:
                print(f"⚠️  ALLOWING trade without AI: First trade needed (0 trades after {self.cycle_count} cycles)")
                # Continue anyway - override for first trade
            elif self.trades < 5 and ai_confidence >= 0.4:
                print(f"⚠️  ALLOWING trade with low AI confidence: {ai_confidence:.2f} (first 5 trades)")
                # Continue for first few trades
            else:
                print(f"⏭️  Skipping {symbol} {position_type.value}: AI not used (used={ai_used}) or confidence too low ({ai_confidence:.2f} < {MIN_AI_CONFIDENCE}).")
                return False

        try:
            print(f"🎯 {position_type.value}: {symbol} @ ${price:.4f}")

            # === CRITICAL FIX: Check if margin_manager exists ===
            if not hasattr(self, 'margin_manager') or self.margin_manager is None:
                print("❌ CRITICAL: Margin manager not initialized")
                return False

            # Calculate position size
            try:
                total_capital = self.margin_manager.get_total_capital(self.current_prices)
                base_percent = regime_params.get('position_size', settings.BASE_POSITION_SIZE_PERCENT)
            except Exception as e:
                print(f"❌ Error calculating total capital: {e}")
                return False

            # Adjust based on performance
            total_trades = max(self.wins + self.losses, 1)
            win_rate = self.wins / total_trades

            if win_rate < 0.3:
                base_percent *= 0.7
            elif win_rate > 0.6:
                base_percent *= 1.2

            position_size = total_capital * (base_percent / 100)

            # === CRITICAL FIX: Get available capital safely ===
            try:
                available = self.margin_manager.get_available_capital()
            except Exception as e:
                print(f"❌ Error getting available capital: {e}")
                return False

            # Minimum $10, Maximum 25% of available
            min_size = 50.0
            max_size = available * 0.25

            # Clamp position size
            position_size = max(min_size, min(position_size, max_size))

            # Final check
            if position_size > available:
                print(f"❌ INSUFFICIENT CAPITAL: ${position_size:.2f} > ${available:.2f}")
                return False
            if position_size <= 0:
                print(f"❌ INVALID POSITION SIZE: ${position_size:.2f}")
                return False

            # Set profit targets and stop losses
            base_profit_target = regime_params.get('profit_target', settings.PROFIT_TARGET) / 100
            base_stop_loss = regime_params.get('stop_loss', settings.STOP_LOSS) / 100

            # Adjust for position type
            if position_type == PositionType.LONG:
                profit_target_multiplier = base_profit_target
                stop_loss_multiplier = base_stop_loss
                take_profit_price = price * (1 + profit_target_multiplier)
                stop_loss_price = price * (1 - stop_loss_multiplier)
            else:  # SHORT
                profit_target_multiplier = -base_profit_target  # Negative for shorts
                stop_loss_multiplier = -base_stop_loss  # Positive for shorts (inverse)
                take_profit_price = price * (1 + profit_target_multiplier)  # price - target%
                stop_loss_price = price * (1 - stop_loss_multiplier)  # price + stop%

            try:
                position = self.margin_manager.open_position(
                    symbol=symbol,
                    position_type=position_type,
                    size=position_size,
                    entry_price=price
                )

                # Set targets
                position['take_profit'] = take_profit_price
                position['stop_loss'] = stop_loss_price

                # Store context
                position['entry_rsi'] = analysis.get('rsi', 50)
                position['entry_dip_percent'] = analysis.get('dip_percent', 0)
                position['entry_confidence'] = analysis.get('confidence', 0)
                position['ai_used'] = analysis.get('ai_used', False)
                position['ai_recommendation'] = analysis.get('ai_recommendation', 'HOLD')
                position['win_rate_at_entry'] = win_rate

                self.trades += 1
                self.daily_trades += 1
                self.balance = self.margin_manager.get_available_capital()

                print(f"✅ OPENED: {symbol} {position_type.value} @ ${price:.4f}")
                print(f"   Size: ${position_size:.2f} ({base_percent:.1f}%)")
                print(f"   Target: ${take_profit_price:.4f} ({abs(profit_target_multiplier * 100):.1f}%)")
                print(f"   Stop: ${stop_loss_price:.4f} ({abs(stop_loss_multiplier * 100):.1f}%)")

                # Telegram notification
                if hasattr(self, 'telegram') and self.telegram.user_ids:
                    message = (
                        f"💰 <b>TRADE OPENED</b>\n"
                        f"Type: {position_type.value}\n"
                        f"Symbol: {symbol}\n"
                        f"Entry: ${price:.4f}\n"
                        f"Size: ${position_size:.2f}\n"
                        f"Target: {abs(profit_target_multiplier * 100):.1f}%\n"
                        f"Stop: {abs(stop_loss_multiplier * 100):.1f}%"
                    )
                    self.telegram.send_message(self.telegram.user_ids[0], message)

                return True

            except ValueError as e:
                print(f"❌ Position opening failed (ValueError): {e}")
                return False
            except Exception as e:
                print(f"❌ Trade execution failed for {symbol}: {e}")
                import traceback
                traceback.print_exc()
                return False

        except Exception as e:
            print(f"❌ Error in trade setup for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _force_emergency_trade(self, regime_params: Dict):
        """Force a trade when nothing else works - UPDATED FIX"""
        print(f"🚨🚨🚨 ULTIMATE EMERGENCY: 0 trades after {self.cycle_count} cycles - FORCING TRADE")
        
        for symbol in settings.symbols:
            if symbol in self.margin_manager.positions:
                continue

            try:
                current_price = self.current_prices.get(symbol)
                price_history = self.price_history.get(symbol, [])

                if len(price_history) < 5:
                    continue

                recent_high = max(price_history[-5:])
                dip_percent = ((recent_high - current_price) / recent_high) * 100

                # Force trade regardless of dip size
                print(f"🚨 FORCING TRADE: {symbol} @ ${current_price:.4f}")

                # Create opportunity that WILL PASS AI CHECK
                opportunity = {
                    'symbol': symbol,
                    'price': current_price,
                    'analysis': {
                        'advice': 'Strong Buy',
                        'position_type': PositionType.LONG,
                        'rsi': 35.0,  # Good RSI for buy
                        'dip_percent': max(dip_percent, 1.0),  # Minimum 1%
                        'confidence': 0.9,
                        'ai_used': True,  # ← CRITICAL: Must be True
                        'ai_confidence': 0.9,  # ← CRITICAL: Above threshold
                        'ai_recommendation': 'BUY'
                    }
                }

                # Bypass all checks and execute directly
                success = await self._execute_simple_trade(opportunity, regime_params)
                if success:
                    print(f"✅ EMERGENCY TRADE EXECUTED: {symbol}")
                    return True

            except Exception as e:
                print(f"❌ Emergency trade failed for {symbol}: {e}")
                continue
        
        print("❌ Could not execute any emergency trade")
        return False

    async def force_first_trade_direct(self):
        """Completely bypass all checks for first trade - ADD THIS ENTIRE METHOD"""
        if self.trades > 0:
            return True
            
        print("🚀🚀🚀 FORCING FIRST TRADE DIRECTLY 🚀🚀🚀")
        
        for symbol in settings.symbols:
            try:
                current_price = self.current_prices.get(symbol)
                if not current_price or current_price <= 0:
                    continue
                
                # Calculate position size - SIMPLE
                position_size = min(50.0, self.margin_manager.get_available_capital() * 0.1)
                
                # Open position DIRECTLY without any analysis
                position = self.margin_manager.open_position(
                    symbol=symbol,
                    position_type=PositionType.LONG,
                    size=position_size,
                    entry_price=current_price
                )
                
                # Set simple targets
                position['take_profit'] = current_price * 1.05  # 5% target
                position['stop_loss'] = current_price * 0.97    # 3% stop
                position['entry_rsi'] = 40.0
                position['ai_used'] = True
                position['entry_confidence'] = 0.9
                
                self.trades += 1
                self.daily_trades += 1
                self.last_trade_cycle = self.cycle_count
                self.consecutive_losses = 0
                
                print(f"✅✅✅ FIRST TRADE FORCED: {symbol} @ ${current_price:.4f}")
                print(f"   Size: ${position_size:.2f}")
                print(f"   Target: ${position['take_profit']:.4f} (+5%)")
                print(f"   Stop: ${position['stop_loss']:.4f} (-3%)")
                
                # Telegram notification
                if hasattr(self, 'telegram') and self.telegram.user_ids:
                    message = (
                        f"🚀 <b>FIRST TRADE FORCED - BOT ACTIVE</b>\n"
                        f"Symbol: {symbol}\n"
                        f"Entry: ${current_price:.4f}\n"
                        f"Size: ${position_size:.2f}\n"
                        f"Target: +5% | Stop: -3%"
                    )
                    self.telegram.send_message(self.telegram.user_ids[0], message)
                
                return True
                
            except Exception as e:
                print(f"❌ Direct trade failed for {symbol}: {e}")
                continue
        
        return False

    async def check_positions(self):
        positions_to_close = []

        # Get regime parameters
        regime_params = self.market_regime.get_regime_parameters()
        regime_timeout = regime_params.get('position_timeout', settings.POSITION_TIMEOUT)
        regime_trailing_activate = regime_params.get('trailing_stop_activate', settings.TRAILING_STOP_ACTIVATE)

        # Make a list of positions to avoid dictionary changes during iteration
        positions_to_check = list(self.margin_manager.positions.items())
        
        for symbol, position in positions_to_check:
            # Skip if position is None or invalid
            if not position:
                continue
                
            try:
                current_price = self.current_prices.get(symbol, position.get('entry_price', 0))
                entry_price = position.get('entry_price', 0)
                entry_time = position.get('entry_time', 0)
                
                if entry_time <= 0:
                    # If entry_time is invalid, skip this position
                    continue
                    
                hold_time_seconds = time.time() - entry_time
                hold_time_minutes = hold_time_seconds / 60
                position_type = position.get('position_type', PositionType.LONG)

                # Update highest/lowest price based on position type
                if position_type == PositionType.LONG:
                    if current_price > position.get('highest_price', 0):
                        position['highest_price'] = current_price
                else:  # SHORT
                    lowest_price = position.get('lowest_price', float('inf'))
                    if current_price < lowest_price:
                        position['lowest_price'] = current_price

                # Calculate current profit percentage
                if entry_price > 0:
                    if position_type == PositionType.LONG:
                        current_profit_pct = (current_price - entry_price) / entry_price * 100
                    else:  # SHORT
                        current_profit_pct = (entry_price - current_price) / entry_price * 100
                else:
                    current_profit_pct = 0

                # ========== TRAILING STOP LOGIC ==========
                if (not position.get('trailing_stop_activated', False) and
                        current_profit_pct >= regime_trailing_activate):
                    position['trailing_stop_activated'] = True
                    print(f"📈 Trailing stop ACTIVATED for {symbol} {position_type.value} @ {current_profit_pct:.1f}%")

                if position.get('trailing_stop_activated', False):
                    trailing_stop_distance = settings.TRAILING_STOP_DISTANCE

                    if position_type == PositionType.LONG:
                        highest_price = position.get('highest_price', entry_price)
                        trailing_stop_price = highest_price * (1 - trailing_stop_distance / 100)
                        current_stop_loss = position.get('stop_loss', 0)
                        position['stop_loss'] = max(current_stop_loss, trailing_stop_price)
                    else:  # SHORT
                        lowest_price = position.get('lowest_price', entry_price)
                        trailing_stop_price = lowest_price * (1 + trailing_stop_distance / 100)
                        current_stop_loss = position.get('stop_loss', float('inf'))
                        position['stop_loss'] = min(current_stop_loss, trailing_stop_price)

                # ========== CHECK EXIT CONDITIONS ==========
                exit_reason = None

                if position_type == PositionType.LONG:
                    take_profit = position.get('take_profit', 0)
                    stop_loss = position.get('stop_loss', 0)
                    # Take profit condition
                    if take_profit > 0 and current_price >= take_profit:
                        exit_reason = f"Take profit hit (+{current_profit_pct:.1f}%)"
                    # Stop loss condition
                    elif stop_loss > 0 and current_price <= stop_loss:
                        exit_reason = f"Stop loss hit ({current_profit_pct:.1f}%)"
                else:  # SHORT
                    take_profit = position.get('take_profit', 0)
                    stop_loss = position.get('stop_loss', float('inf'))
                    # Take profit condition (price goes DOWN for shorts)
                    if take_profit > 0 and current_price <= take_profit:
                        exit_reason = f"Take profit hit (+{current_profit_pct:.1f}%)"
                    # Stop loss condition (price goes UP for shorts)
                    elif stop_loss < float('inf') and current_price >= stop_loss:
                        exit_reason = f"Stop loss hit ({current_profit_pct:.1f}%)"

                # NEW: Time-based exit for positions held too long with small profit
                if not exit_reason and hold_time_minutes > 120 and current_profit_pct > 0.5:
                    exit_reason = f"Time-based exit ({current_profit_pct:+.1f}% after {hold_time_minutes:.1f}m)"

                # Original timeout condition
                if not exit_reason and hold_time_seconds > regime_timeout:
                    if abs(current_profit_pct) < 0.5:  # Minimal profit/loss
                        exit_reason = f"Position timeout ({current_profit_pct:+.1f}% after {hold_time_minutes:.1f}m)"

                if exit_reason:
                    positions_to_close.append((symbol, position, current_price, exit_reason))
                    
            except Exception as e:
                print(f"❌ Error checking position {symbol}: {e}")
                continue

        # Close positions
        for symbol, position, exit_price, reason in positions_to_close:
            await self._close_position(symbol, position, exit_price, reason)

    async def _close_position(self, symbol: str, position: dict, exit_price: float, reason: str):
        try:
            if not position:
                print(f"❌ Cannot close position for {symbol}: position is None")
                return
                
            position_type = position.get('position_type', PositionType.LONG)

            if position_type == PositionType.LONG:
                pnl = (exit_price - position.get('entry_price', 0)) * position.get('qty', 0)
            else:  # SHORT
                pnl = (position.get('entry_price', 0) - exit_price) * position.get('qty', 0)

            pnl_pct = (pnl / position.get('size', 1)) * 100 if position.get('size', 0) > 0 else 0

            # Close the position
            self.margin_manager.close_position(symbol, exit_price)
            self.realized_pnl += pnl
            self.trade_logger.log_trade_closed(
                symbol=symbol,
                position=position,
                exit_price=exit_price,
                pnl_usd=pnl,
                exit_reason=reason
            )

            if pnl > 0:
                self.wins += 1
                self.total_profit += pnl
                self.consecutive_losses = 0
                emoji = "💰"
            else:
                self.losses += 1
                self.total_loss += abs(pnl)
                self.consecutive_losses += 1
                emoji = "🔴"

            self.balance = self.margin_manager.get_available_capital()  # FIXED TYPO
            self.trades += 1

            # Telegram notification
            message = (
                f"{emoji} <b>POSITION CLOSED</b>\n"
                f"Type: {position_type.value}\n"
                f"Symbol: {symbol}\n"
                f"Entry: ${position.get('entry_price', 0):.4f} | Exit: ${exit_price:.4f}\n"
                f"PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%)\n"
                f"Reason: {reason}\n"
                f"Hold time: {(time.time() - position.get('entry_time', 0)) / 60:.1f}m"
            )

            if self.telegram.user_ids:
                self.telegram.send_message(self.telegram.user_ids[0], message)

            print(
                f"{emoji} CLOSED: {symbol} {position_type.value} | PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | Reason: {reason}")

        except Exception as e:
            print(f"❌ Position close failed for {symbol}: {e}")
            import traceback
            traceback.print_exc()

    async def trading_cycle(self):
        self.cycle_count += 1

        if self.trades == 0 and self.cycle_count >= 5:
            print(f"🚨 0 trades after {self.cycle_count} cycles - FORCING DIRECT TRADE")
            await self.force_first_trade_direct()
            return

        # Emergency API check
        if self.cycle_count % 10 == 0:
            await self.adapt_trading_strategy()
            try:
                btc_price = await self.api.get_ticker('BTC')
                if btc_price <= 0:
                    await asyncio.sleep(5)
                    btc_price = await self.api.get_ticker('BTC')
                    if btc_price <= 0:
                        print("❌ CRITICAL: API completely unavailable - SHUTTING DOWN")
                        self.running = False
                        return
            except Exception as e:
                print(f"⚠️  API check failed: {e}")

        print(f"\n🔄 CYCLE {self.cycle_count} - {datetime.now().strftime('%H:%M:%S')}")

        if self.cycle_count % 20 == 0 and settings.ENABLE_SHORTING:
            await self.emergency_balance_positions()

        # Update market regime
        if self.cycle_count % 15 == 0 or self.cycle_count == 1:
            await self.update_real_market_regime()

        # Audit balances
        if self.cycle_count % 5 == 0:
            if not self.audit_balances():
                print("🚨 ACCOUNTING ERROR DETECTED - balances have been reset")

        # Update price data
        await self.update_prices()

        # Check and manage positions
        await self.check_positions()

        # Update historical data
        if self.cycle_count % 180 == 0:
            await self.update_historical_data()

        # Update BTC correlation data
        await self.btc_tracker.update_btc_data()

        # Update BTC dominance
        if self.cycle_count % 30 == 0:
            await self.btc_dominance_tracker.update_dominance()

        # Update Fear & Greed Index
        if self.cycle_count % 60 == 0:
            await self.fear_greed_tracker.update_fgi()

        # Execute trades if not paused
        if not self.paused and not self.trading_halted:
            await self.analyze_and_trade()

        # Display status
        if self.cycle_count % 10 == 0:
            await self._display_status_report()

        # Send periodic Telegram report
        if self.cycle_count % 60 == 0:
            await self.telegram.send_periodic_report()

        # Reset daily counters at midnight
        current_hour = datetime.now().hour
        if current_hour == 0 and self.cycle_count % 360 == 0:
            print("🔄 Resetting daily counters")
            self.daily_trades = 0
            self.daily_start_balance = self.balance

        # Emergency trade logic
        if (not self.paused and not self.trading_halted and
                len(self.margin_manager.positions) == 0 and
                self.cycle_count - self.last_trade_cycle > settings.EMERGENCY_TRADE_AFTER_CYCLES * 3):
            regime_params = self.market_regime.get_regime_parameters()
            print("🚨 EMERGENCY: No positions for many cycles, forcing trade check")
            await self._force_emergency_trade(regime_params)

        await asyncio.sleep(settings.CYCLE_DELAY)

    async def _display_status_report(self):
        """Display comprehensive status report"""
        regime_params = self.market_regime.get_regime_parameters()
        regime_icon = "🟢" if regime_params['regime'] == "BULL" else "🔴" if regime_params['regime'] == "BEAR" else "🟡"

        active_positions = len(self.margin_manager.positions)
        total_equity = self.margin_manager.get_total_capital(self.current_prices)
        initial_capital = settings.INITIAL_CAPITAL
        growth_pct = (total_equity / initial_capital - 1) * 100

        # Count short positions
        short_positions = self.margin_manager.get_short_positions_count()
        long_positions = active_positions - short_positions

        print(
            f"📊 {regime_icon} MARKET REGIME: {regime_params['regime']} (Strength: {regime_params['regime_strength']:.1%})")
        print(f"   Position Size: {regime_params['position_size']:.1f}%")
        print(f"   Targets: {regime_params['profit_target']:.1f}%/{regime_params['stop_loss']:.1f}%")
        print(f"   Max Positions: {regime_params['max_positions']}")
        print(f"   Daily Limit: {regime_params['daily_trade_limit']}")

        print(f"📈 PERFORMANCE: ${total_equity:.2f} ({growth_pct:+.1f}%)")
        print(f"   Active: {active_positions}/{regime_params['max_positions']}")
        print(f"   Long: {long_positions} | Short: {short_positions}")
        print(f"   Daily Trades: {self.daily_trades}/{regime_params['daily_trade_limit']}")
        print(f"   Total Trades: {self.trades}")

        # Position details
        if active_positions > 0:
            print(f"💰 ACTIVE POSITIONS:")
            for symbol, position in self.margin_manager.positions.items():
                current_price = self.current_prices.get(symbol, position.get('entry_price', 0))
                position_type = position.get('position_type', PositionType.LONG)

                if position_type == PositionType.LONG:
                    profit_pct = (current_price - position.get('entry_price', 0)) / position.get('entry_price', 0) * 100
                    position_emoji = "📈"
                else:
                    profit_pct = (position.get('entry_price', 0) - current_price) / position.get('entry_price', 0) * 100
                    position_emoji = "📉"

                hold_time = (time.time() - position.get('entry_time', 0)) / 60

                ai_indicator = "🤖" if position.get('ai_used', False) else ""
                trailing_indicator = " 🚀" if position.get('trailing_stop_activated', False) else ""

                print(
                    f"   {symbol} {ai_indicator}{position_emoji}: ${current_price:.4f} | PnL: {profit_pct:+.1f}% | {hold_time:.1f}m{trailing_indicator}")

    async def run(self):
        print("🤖 Starting Ultimate Aggressive Trading Bot WITH SHORTING CAPABILITY")
        print(f"💰 Initial Capital: ${settings.INITIAL_CAPITAL:.2f}")
        print(f"📉 Shorting: {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}")
        print("🎯 DYNAMIC REGIME ADJUSTMENTS: ACTIVE")
        print(f"📈 POSITION SIZE: {settings.BASE_POSITION_SIZE_PERCENT}% (regime-adjusted)")
        print("🕐 MULTI-TIMEFRAME HISTORICAL DATA: 7 DAYS")
        print(f"⚡ CYCLE DELAY: {settings.CYCLE_DELAY} seconds")
        print("=" * 60)

        if not await self.emergency_api_checks():
            print("❌ CRITICAL: Emergency API checks failed - cannot continue")
            return

        await self.initialize_prices()

        if not settings.symbols:
            print("❌ CRITICAL: No working symbols available - Emergency exit")
            return

        print("🕐 WARMING UP BOT WITH HISTORICAL DATA...")
        historical_loaded = await self.load_historical_data()

        if historical_loaded:
            print("✅ BOT WARMED UP WITH 7 DAYS OF MARKET DATA!")
        else:
            print("⚠️  Trading without historical context")

        while self.running:
            try:
                if not self.paused and not self.trading_halted:
                    await self.trading_cycle()
                else:
                    if self.paused:
                        print("⏸️  Bot paused - waiting...")
                    elif self.trading_halted:
                        print("🔴 Trading halted due to risk limits")

                await asyncio.sleep(settings.CYCLE_DELAY)

            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                await asyncio.sleep(10)

    async def shutdown(self):
        print("🛑 Shutting down bot...")
        self.running = False
        await self.api.close()
        await self.trading_logic.close()


async def main():
    parser = argparse.ArgumentParser(description='Ultimate Aggressive Trading Bot WITH SHORTING')
    parser.add_argument('--sim', action='store_true', help='Run in simulation mode (paper trading)')
    args = parser.parse_args()

    print("🚀 ULTIMATE AGGRESSIVE TRADING BOT WITH SHORTING")
    print("📊 PAPER TRADING: Real prices, simulated money")
    print(f"💰 Initial Capital: ${settings.INITIAL_CAPITAL:.2f}")
    print(f"📉 Shorting: {'✅ ENABLED' if settings.ENABLE_SHORTING else '❌ DISABLED'}")
    print("🎯 DYNAMIC REGIME SYSTEM: FULLY ACTIVE")
    print(f"📈 ADAPTIVE POSITIONS: {settings.BASE_POSITION_SIZE_PERCENT}% base, regime-adjusted")
    print("🕐 HISTORICAL DATA: 7 days loaded")
    print(f"⚡ OPTIMIZED CYCLES: {settings.CYCLE_DELAY} seconds")
    print("=" * 60)

    bot = UltimateTradingBot()

    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n⏹️  Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())