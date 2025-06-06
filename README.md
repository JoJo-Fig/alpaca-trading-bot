# 🧠 AlpacaTradeBot

**An adaptive, modular trading bot built with Python and Alpaca's API — designed to reflect the trading logic of a cautious, swing-focused investor.**

---

## 📌 Overview

AlpacaTradeBot is a personal project and ongoing challenge: to automate my ideal trading style, free up my time, and stay active in the stock market without needing to manually analyze trends or place orders throughout the day.

This bot evaluates technical indicators in real-time and places smart buy/sell orders based on my swing trading strategy. It handles key risk factors like day trading flags and overexposure — all while maintaining clean, modular code for future expansion into deeper financial analysis.

---

## 🛠️ Features

- 📈 Gathers **historical and real-time** stock data using Alpaca's API  
- 🤖 Places **market, limit, stop-loss, and trailing stop** orders  
- 🧮 Evaluates trades using **EMA, RSI, ATR** indicators  
- 🧠 Avoids day-trading flags, double-buys, and position conflicts  
- 📓 Logs all trades to a structured JSON file  
- 🔄 Designed with **modularity and scalability** in mind for future improvements  

---

## 📊 Technical Indicators

This version uses a multi-condition strategy to determine high-quality trades:
- **Exponential Moving Average (EMA)** – for identifying price trends  
- **Relative Strength Index (RSI)** – for detecting overbought/oversold conditions  
- **Average True Range (ATR)** – for measuring market volatility  

Only when all criteria are met will a buy order be considered — adding discipline to trade entries.

---

## 🔧 Tech Stack

- **Language:** Python  
- **API:** [Alpaca-py](https://github.com/alpacahq/alpaca-py)  
- **Storage:** JSON for order receipts and log keeping  
- **Future Enhancements:** Text file-based watchlist input, push notifications

---

## 🧱 Project Structure
project/
├── trading_bot.py          # Full bot logic and strategy in one file
├── trade_receipts.json     # Stores order receipts (created after bot run)

---

## 🧪 Setup & Usage

1. **Install Dependencies**
   ```bash
   pip install alpaca-py pandas numpy
2. **Add your Alpaca API keys directly to the main.py file.**
   API_KEY = "---"
   API_SECRET = "---"

(Note: .env support will be added in future versions.)

3. **Manually input your watchlist by symbol in get_full_watchlist().**
   
4. **Run the bot in paper trading mode.**
⚠️ Warning: This bot is for educational and paper trading purposes only.
A basic understanding of trading mechanics is highly recommended before using with real funds.

---

## 🚀 Current Limitations
No GUI or dashboard (yet).

Relies on free-tier Alpaca data, which may have real-time delays.

Watchlist must currently be edited manually in code.

---

## 🌱 Future Plans
✅ Load watchlist from a .txt or .csv file

✅ Add push notification system (email/text) for trade confirmations

🚧 Integrate financial indicators (e.g., earnings reports, P/E ratios)

🚧 Backtesting module for evaluating strategies on past data

🚧 Auto portfolio rebalancing and strategy rotation logic

---

## 🎯 What This Project Demonstrates
My ability to write clean, reusable Python code

Logical design of trading strategies based on real-world constraints

Proficiency in using APIs, data analysis, and state management

Focus on risk management and real-world trade mechanics

---

## 📬 Contact & Feedback
This bot is actively being improved. If you have feedback, questions, or want to collaborate, feel free to open an issue or connect with me.

---

## 🌐 Live Site [🚧UNDER CONSTRUCTION🚧]

Visit: [My GitHub Pages Portfolio](https://your-username.github.io/alpaca-trading-bot/)
