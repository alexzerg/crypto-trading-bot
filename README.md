# crypto-trading-bot

> ⚠️ **Disclaimer:** This is an experimental personal trading bot. Cryptocurrency trading carries substantial risk and you can lose all of your capital. **Do not run this with real funds unless you fully understand the code and the risks.** No warranty — see [LICENSE](LICENSE).

A multi-strategy crypto scalper for the [Crypto.com Exchange](https://crypto.com/exchange) with pluggable AI decision engines (OpenAI / DeepSeek / Grok), Telegram bot interface, and regime-aware position sizing.

---

## Variants

The repo ships several bot variants, each backed by a different AI provider. They share the same overall architecture but differ in tuning and the model they call.

| Script         | AI provider     | Env file              | Notes                                |
|----------------|-----------------|-----------------------|--------------------------------------|
| `chatgpt.py`   | OpenAI (GPT)    | `.env_chatgpt`        | The original variant                 |
| `ds.py`        | DeepSeek        | `.env_ds`             | Current main DeepSeek build          |
| `grok.py`      | xAI / Grok      | `.env_grok`           | Grok variant                         |
| `lm_cgpt.py`   | —               | —                     | Local DB monitor for the GPT variant |
| `lm_ds.py`     | —               | —                     | Local DB monitor for the DS variant  |

---

## Features

- 🤖 **Multiple AI engines** — OpenAI, DeepSeek, Grok (xAI) for trade decisioning
- 📈 **Crypto.com Exchange API** — REST + WebSocket for market data and order placement
- 💬 **Telegram bot** — push notifications + interactive commands (status, stats, halt)
- 📊 **Market regime detection** — bull / bear / sideways with per-regime multipliers
- 🎯 **Long & short positions** with separate profit / stop-loss / trailing-stop tuning
- ⚖️ **Risk management** — daily loss limit, max drawdown, max concurrent positions, consecutive-loss cap
- 💾 **SQLite-backed state** — local DB for trade journal and AI decisions
- 🚨 **Emergency / forced-trade modes** for stagnant markets

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/alexzerg/crypto-trading-bot.git
cd crypto-trading-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

For each variant you want to run, copy the matching `.example` file and fill in real values:

```bash
cp .env_ds.example      .env_ds
cp .env_chatgpt.example .env_chatgpt
cp .env_grok.example    .env_grok
```

Then edit each one and replace every `XXXX...` placeholder with your real credentials.

### 3. Get your API keys

| Service     | Where to create the key                                                  |
|-------------|--------------------------------------------------------------------------|
| OpenAI      | <https://platform.openai.com/api-keys>                                   |
| DeepSeek    | <https://platform.deepseek.com>                                          |
| Grok / xAI  | <https://console.x.ai>                                                   |
| Crypto.com  | Exchange → Settings → **API Keys** (enable trading scope, restrict IP!)  |
| Telegram    | Message [@BotFather](https://t.me/BotFather) → `/newbot`                 |

To get your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

> 🔒 **Security:** Never commit real `.env_*` files. The `.gitignore` already excludes them; only `.env_*.example` templates are tracked.

### 4. Adjust the env path inside the script (if needed)

Each variant looks for its env file at a hardcoded path — by default a placeholder like `/path/to/your/.env_ds`. Edit the `env_path` / `env_paths` list near the top of the script to point at your local file, or just place the env file alongside the script.

---

## Usage

### DeepSeek variant

```bash
python ds.py
```

### OpenAI / GPT variant

```bash
python chatgpt.py
```

### Grok variant

```bash
python grok.py
```

### Local DB monitor (read-only stats from the SQLite journal)

```bash
python lm_ds.py     # for the DeepSeek bot
python lm_cgpt.py   # for the GPT bot
```

Press `Ctrl+C` to stop any bot. Open positions are tracked in the SQLite DB and will be picked up on next launch.

---

## Configuration reference

All trading parameters live in the `.env_*` files. The most important knobs:

| Variable                       | What it does                                            |
|--------------------------------|---------------------------------------------------------|
| `INITIAL_CAPITAL`              | Starting capital in USD                                 |
| `POSITION_SIZE_PERCENT`        | % of capital per position                               |
| `MAX_CONCURRENT_POSITIONS`     | Hard cap on simultaneous positions                      |
| `TRADING_SYMBOLS`              | Comma-separated list, e.g. `ETH,SOL,AVAX`               |
| `PROFIT_TARGET` / `STOP_LOSS`  | Long-position TP/SL in %                                |
| `SHORT_PROFIT_TARGET` / `SHORT_STOP_LOSS` | Same, for shorts                             |
| `TRAILING_STOP_ACTIVATE` / `_DISTANCE` | Trailing-stop tuning                            |
| `DAILY_LOSS_LIMIT`             | Bot halts trading after this % loss in a day           |
| `MAX_DRAWDOWN`                 | Bot halts when account drawdown exceeds this %         |
| `RSI_BUY_MAX` / `RSI_SELL_MIN` | RSI gates for entries / exits                          |
| `CONFIDENCE_THRESHOLD`         | Minimum AI confidence to act on a signal               |
| `AI_CACHE_TTL`                 | Cache lifetime for AI calls (seconds)                  |
| `AI_MAX_DAILY_CALLS`           | Spend cap on the AI provider                           |
| `VERBOSE_MODE`                 | Extra logging                                           |

See the `.env_*.example` files for the full list with sensible defaults.

---

## Project structure

```
crypto-trading-bot/
├── chatgpt.py              # OpenAI / GPT bot
├── ds.py                   # DeepSeek bot (current)
├── new_ds.py               # DeepSeek bot (experimental)
├── grok.py                 # Grok / xAI bot
├── lm_cgpt.py              # SQLite monitor for GPT bot
├── lm_ds.py                # SQLite monitor for DeepSeek bot
├── .env_chatgpt.example    # OpenAI + Telegram config template
├── .env_ds.example         # DeepSeek + Crypto.com + Telegram template
├── .env_grok.example       # Grok + Crypto.com + Telegram template
├── requirements.txt
├── .gitignore
├── LICENSE                 # MIT
└── README.md
```

---

## License

[MIT](LICENSE) — © 2026 alexzerg
