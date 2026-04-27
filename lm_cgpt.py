import sqlite3
import time


class LearningManager:
    """
    LearningManager reads recent trades from the DB and computes
    per-symbol performance metrics. It then can adjust GPT signals
    based on how good/bad the bot has historically performed on
    that symbol and in bad regimes (e.g. high volatility).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.last_update = 0.0
        self.cache = {}

    def load(self):
        """
        Load learning state, caching results for 30 seconds
        to avoid hammering SQLite.
        """
        now = time.time()
        if now - self.last_update < 30:
            return self.cache

        self.cache = self._compute_learning_state()
        self.last_update = now
        return self.cache

    def _compute_learning_state(self):
        """
        Compute per-symbol:
        - win_rate
        - loss_rate
        - avg_pnl
        - best/worst pnl
        - max loss streak
        - recommendation: aggressive / neutral / avoid_or_cautious
        """

        stats = {}

        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            # last 500 trades is enough to get a behavior profile
            cur.execute("""
                SELECT symbol, side, entry_price, exit_price, pnl, entry_time
                FROM trades
                ORDER BY id DESC
                LIMIT 500
            """)
            rows = cur.fetchall()
            con.close()
        except Exception as e:
            # if DB missing or locked, just return empty; bot will still run
            return {}

        if not rows:
            return {}

        for sym, side, entry_price, exit_price, pnl, entry_time in rows:
            if sym not in stats:
                stats[sym] = {
                    "total": 0,
                    "wins": 0,
                    "losses": 0,
                    "streak_loss": 0,
                    "max_streak_loss": 0,
                    "pnls": []
                }

            s = stats[sym]
            s["total"] += 1
            s["pnls"].append(pnl if pnl is not None else 0.0)

            if pnl is not None and pnl > 0:
                s["wins"] += 1
                s["streak_loss"] = 0
            else:
                s["losses"] += 1
                s["streak_loss"] += 1
                if s["streak_loss"] > s["max_streak_loss"]:
                    s["max_streak_loss"] = s["streak_loss"]

        out = {}
        for sym, s in stats.items():
            total = s["total"]
            wins = s["wins"]
            losses = s["losses"]
            win_rate = wins / total if total else 0.0
            loss_rate = losses / total if total else 0.0
            pnls = s["pnls"]
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0
            pnl_best = max(pnls) if pnls else 0.0
            pnl_worst = min(pnls) if pnls else 0.0

            if win_rate > 0.65:
                recommendation = "aggressive"
            elif win_rate < 0.40:
                recommendation = "avoid_or_cautious"
            else:
                recommendation = "neutral"

            out[sym] = {
                "win_rate": round(win_rate, 3),
                "loss_rate": round(loss_rate, 3),
                "avg_pnl": round(avg_pnl, 6),
                "pnl_best": pnl_best,
                "pnl_worst": pnl_worst,
                "max_loss_streak": s["max_streak_loss"],
                "recommendation": recommendation,
            }

        return out

    def adjust_signal(self, symbol: str, gpt_signal: str, volatility: float, trend_strength: float) -> str:
        """
        Adjust GPT signal based on learned behavior.

        - If symbol is bad historically, be more conservative
        - If long loss streak, require stronger trend to BUY
        - If high volatility & low win rate, avoid trading
        """

        state = self.cache.get(symbol)
        if not state:
            # no learning data yet for this symbol
            return gpt_signal

        sig = gpt_signal

        # Rule 1: if we historically suck on this coin, avoid BUY
        if state["recommendation"] == "avoid_or_cautious":
            if sig == "BUY":
                # 50%: either turn into HOLD or SELL;
                # here we choose HOLD (just avoid trading it)
                return "HOLD"

        # Rule 2: if we have a long loss streak, require strong trend
        if state["max_loss_streak"] >= 5:
            if sig == "BUY" and trend_strength < 0.5:
                return "HOLD"

        # Rule 3: high volatility + poor win rate -> be defensive
        if volatility > 0.8 and state["win_rate"] < 0.45:
            if sig == "BUY":
                return "HOLD"

        return sig
