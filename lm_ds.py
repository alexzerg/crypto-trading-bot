import sqlite3
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os
import numpy as np


# =========================
# DATA CLASSES
# =========================

@dataclass
class TradeRecord:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    position_type: str  # "LONG" or "SHORT"
    size: float
    pnl: float
    pnl_percent: float
    exit_reason: str
    hold_time_seconds: float
    market_regime: str
    rsi_at_entry: Optional[float] = None
    dip_percent_at_entry: Optional[float] = None
    confidence_at_entry: Optional[float] = None
    volume_trend: Optional[str] = None
    btc_correlation: Optional[float] = None
    ai_used: bool = False
    ai_confidence: Optional[float] = None
    ai_recommendation: Optional[str] = None
    technical_indicators: Optional[Dict] = None


@dataclass
class SignalRecord:
    timestamp: datetime
    symbol: str
    price: float
    advice: str
    enhanced_advice: str
    confidence: float
    rsi: Optional[float] = None
    dip_percent: Optional[float] = None
    dip_strength: Optional[int] = None
    trend: Optional[str] = None
    volume_trend: Optional[str] = None
    market_regime: Optional[str] = None
    ai_used: bool = False
    ai_recommendation: Optional[str] = None
    ai_confidence: Optional[float] = None
    trade_taken: bool = False
    trade_id: Optional[int] = None
    signal_type: str = "BOT"
    ai_signal_id: Optional[int] = None


@dataclass
class AIAnalysis:
    symbol: str
    timestamp: datetime
    price: float
    recommendation: str
    confidence: float
    rationale: str
    technical_context: Dict


# =========================
# LEARNING MANAGER
# =========================

class LearningManager:
    """
    Enhanced Learning Manager
    DB PATH IS MANDATORY AND CONTROLLED BY WRAPPER
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.getcwd(), "trading_bot_enhanced.db")

        self.db_path = db_path
        self.conn = None

        # CRITICAL FIX: Create connection and initialize tables
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            print(f"✅ SQLite connected to: {db_path}")

            # FORCE table creation
            self._initialize_database()

            print(f"🧠 ENHANCED Learning Manager initialized: {db_path}")

        except Exception as e:
            print(f"❌ Learning Manager initialization failed: {e}")
            import traceback
            traceback.print_exc()
            # Create minimal connection
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

    def _initialize_database(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = [t[0] for t in cursor.fetchall()]
            print(f"📊 Existing tables in database: {existing_tables}")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                entry_time TEXT,
                exit_time TEXT,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                position_type TEXT NOT NULL,
                size REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_percent REAL NOT NULL,
                win BOOLEAN NOT NULL,
                exit_reason TEXT,
                hold_time_seconds REAL,
                market_regime TEXT,
                rsi_entry REAL,
                dip_percent REAL,
                confidence_at_entry REAL,
                volume_trend TEXT,
                btc_correlation REAL,
                ai_used BOOLEAN DEFAULT FALSE,
                ai_confidence REAL,
                ai_recommendation TEXT,
                technical_indicators TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parameter_name TEXT NOT NULL,
                parameter_value REAL NOT NULL,
                success_rate REAL NOT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                advice TEXT NOT NULL,
                confidence REAL NOT NULL,
                rsi REAL,
                dip_percent REAL,
                trade_taken BOOLEAN DEFAULT FALSE,
                trade_id INTEGER
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                recommendation TEXT NOT NULL,
                confidence REAL NOT NULL,
                rationale TEXT,
                rsi REAL,
                dip_percent REAL,
                trend TEXT,
                volatility REAL,
                market_regime TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                advice TEXT NOT NULL,
                confidence REAL NOT NULL,
                rsi REAL,
                dip_percent REAL,
                ai_signal_id INTEGER
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                ai_signal_id INTEGER,
                bot_signal_id INTEGER,
                ai_recommendation TEXT,
                bot_advice TEXT,
                price_at_signal REAL,
                price_5min_later REAL,
                price_15min_later REAL,
                price_30min_later REAL,
                price_60min_later REAL,
                ai_was_correct_5min INTEGER,
                ai_was_correct_15min INTEGER,
                ai_was_correct_30min INTEGER,
                ai_was_correct_60min INTEGER,
                bot_was_correct_5min INTEGER,
                bot_was_correct_15min INTEGER,
                bot_was_correct_30min INTEGER,
                bot_was_correct_60min INTEGER
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                error_type TEXT NOT NULL,
                description TEXT,
                price_at_error REAL,
                price_later REAL,
                time_diff_minutes REAL,
                pnl_lost REAL,
                ai_recommendation TEXT,
                bot_action TEXT,
                market_regime TEXT
            )
            """)

            self.conn.commit()
            print("✅ Enhanced database tables ensured")

        except Exception as e:
            print(f"❌ Error initializing enhanced database: {e}")
            raise

    # =========================
    # CLEAN SHUTDOWN
    # =========================

    def close(self):
        try:
            if self.conn:
                self.conn.close()
                print("🔒 LearningManager DB closed")
        except Exception as e:
            print(f"❌ Error closing DB: {e}")
