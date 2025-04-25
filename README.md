---

# 📈 Funding Rate Arbitrage Bot

This Telegram bot is designed to **monitor funding rates** for perpetual contracts across multiple cryptocurrency exchanges, **detect arbitrage opportunities**, and **send detailed alerts** when profitable discrepancies are found. It also provides a Telegram interface for adjusting operational thresholds and uses SQLite databases for persistent user and settings management.

## 💡 Purpose

The primary goal of this bot is to **analyze funding rates of identical assets across different exchanges**. When a significant difference (spread) is detected—combined with a minimal difference in market prices—the bot sends a notification to a specific Telegram thread based on the severity of the spread.

---

## 🔧 Features

- Real-time fetching of **funding rates and prices** from the following exchanges:
  - Bitget
  - Gate
  - MEXC
  - Ourbit
  - BingX
  - Bybit
  - Aevo
  - OKX
  - Hyperliquid
  - KuCoin
- SOCKS5 proxy support for reliable data collection
- Dynamic filtering based on:
  - Minimum spread thresholds (`spread_low`, `spread_medium`, `spread_high`)
  - Maximum price deviation (`price_diff`)
- Configurable alert channels via inline Telegram UI
- Funding history retrieval per exchange for context
- Blacklisting of symbols to prevent duplicate alerts within a 40-minute window
- Full support for `FSM` (Finite State Machine) for settings updates
- SQLite databases for:
  - Users and blacklists (`users.db`)
  - Threshold settings (`settings.db`)

---

## 🚀 Setup Instructions

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 2. Set up the bot token

Edit this line at the top of the script:

```python
TOKEN = "YOUR_BOT_TOKEN_HERE"
```

Replace it with the token you received from [@BotFather](https://t.me/BotFather).

---

### 3. Configure alert channels

Inside the `send_alert(...)` function, **replace** the placeholder values with your actual `chat_id` and `message_thread_id` for each alert level:

```python
if spread_low <= spread_value < spread_medium:
    await bot.send_message(chat_id='YOUR_CHAT_ID', text=message, message_thread_id=THREAD_ID_LOW)
elif spread_medium <= spread_value < spread_high:
    await bot.send_message(chat_id='YOUR_CHAT_ID', text=message, message_thread_id=THREAD_ID_MEDIUM)
elif spread_value >= spread_high:
    await bot.send_message(chat_id='YOUR_CHAT_ID', text=message, message_thread_id=THREAD_ID_HIGH)
```

---

### 4. Prepare required files

Ensure these files exist in the root directory:

- `coins.txt` — a list of trading symbols (e.g., `BTC_USDT`, `ETH_USDT`)
- `proxies.txt` — a list of SOCKS5 proxies (optional)
- `withdrawable_{exchange}.txt` — available withdrawal assets per exchange

---

### 5. Run the bot

```bash
python main.py
```

---

## 🧠 How It Works

1. Every 5 seconds, the bot:
   - Loads trading pairs (symbols) and excludes blacklisted ones
   - Collects funding rates and prices from all configured exchanges
   - Compares pairs of exchanges for each symbol
   - If the spread exceeds a threshold and price difference is within limits:
     - Sends a detailed alert to the appropriate chat thread
     - Adds the symbol to a blacklist (cooldown: 40 min)
     - Includes historical funding data

2. Alerts include:
   - Token name
   - Exchanges with highest spread
   - Funding rates and prices
   - Price difference %
   - Withdrawal status
   - Historical funding data (timestamps + rates)

---

## 🧩 Architecture Overview

- `main.py` — core logic, event loop, alert generation
- `bitget.py`, `bingx.py`, etc. — individual fetcher classes per exchange
- `users.db` — user registration and blacklist handling
- `settings.db` — persistent settings (spreads, thresholds, etc.)

---

## 📲 Telegram Commands

- `/start` — registers the user
- `/settings` — opens inline menu to configure thresholds

---

## 🔐 Security Notes

- Keep your **Telegram bot token private**.
- Use trusted SOCKS5 proxies.
- Ensure database files are secure and not exposed publicly.

---

## 📊 Example Alert

```
💲BTC/USDT

📊 Exchanges: Bitget ↔️ Bybit

📈 Funding Rates:

  Bitget: -0.0120%
  Bybit:  0.0280%

Spread: 0.0400

💰 Prices:

  Bitget: (62482.23000$)
  Bybit:  (62470.25000$)

⚖ Price Difference: 0.02%

🕰 Funding History:

Bitget:
-0.0100% (2024-04-24 08:00:00)
-0.0100% (2024-04-24 06:00:00)
-0.0100% (2024-04-24 04:00:00)
-0.0100% (2024-04-24 02:00:00)
Bybit:
0.0200% (2024-04-24 08:00:00)
0.0200% (2024-04-24 06:00:00)
0.0200% (2024-04-24 04:00:00)
0.0200% (2024-04-24 02:00:00)
```

---

## 👤 Author

Created by Az1m9t 
Telegram: @reqwezxc

---
