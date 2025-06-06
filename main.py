import sys
import time
import json
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, TrailingStopOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime, timezone, timedelta
#import numpy as np
import pandas as pd
from typing import Optional, List, Dict
import pytz

API_KEY = "PK80Z6093CKJBMXM7KJ0"
API_SECRET = "7kg7hXyH16QQe7XsY0Q5Li3EEN2KZhxqTjTc2GxS"
API_DELAY = 1

def get_account(trading_client, max_retries=3, delay=5):
    for attempt in range(1, max_retries+1):
        try:
            account=trading_client.get_account()
            return account
        except Exception as e:
            if attempt < max_retries:
                time.sleep(delay)
            else:
                print(f"Failed to get account info. Exiting.")
                sys.exit(1)

def check_daytrades(daytrade_count:Optional[int]):
    if daytrade_count is None:
        print(f"Day trade count is unavailable.")
        sys.exit(1)
    if daytrade_count != 0:
        print(f"Day trade(s) made within the past 5 business days. Exiting to avoid PDT risk.")
        sys.exit(1)

def get_full_watchlist(trading_client) -> dict:
    # Manually defined watchlist
    watchlist = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "TSLA",
        "META",
        "AMD",
        "NFLX",
        "XOM"
    ]

    position_data = {}
    try:
        positions = trading_client.get_all_positions()
        for pos in positions:
            symbol = pos.symbol
            qty = int(float(pos.qty))
            unrealized_plpc = float(pos.unrealized_plpc)
            position_data[symbol] = {
                "qty": qty,
                "unrealized_plpc": unrealized_plpc
            }
    except Exception as e:
        print(f"Failed to fetch positions: {e}")

    full_watchlist = {}
    all_symbols = set(watchlist) | set(position_data.keys())
    for symbol in all_symbols:
        full_watchlist[symbol] = {
            "qty": position_data.get(symbol, {}).get("qty", 0),
            "unrealized_plpc": position_data.get(symbol, {}).get("unrealized_plpc", 0.0)
        }

    return full_watchlist

def market_closing_soon(threshold_minutes=10):
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return (market_close - now) <= timedelta(minutes=threshold_minutes)

def trade_status(symbol:str, trading_client):
    today = datetime.now(timezone.utc).date()

    try:
        request = GetOrdersRequest(status=QueryOrderStatus.ALL)
        recent_orders = trading_client.get_orders(request)

        for order in recent_orders:
            if order.symbol != symbol:
                continue

            if order.status == "open":
                return "open_order"

            if (
                order.side == "buy" and
                order.submitted_at.date() == today
            ):
                return "bought_today"
        return "clear"

    except Exception as e:
        print(f"Error checking recent orders for {symbol}: {e}")
        return "error"

def set_support_resistance(close_prices: pd.Series, window:int=5) -> Optional[Dict[str, List[float]]]:
    if len(close_prices) < (window * 2+1):
        return None
    support_levels = []
    resistance_levels = []

    for i in range(window, len(close_prices) - window):
        low_range = close_prices[i - window:i + 1]
        high_range = close_prices[i:i + window + 1]

        current_price = close_prices[i]
        if current_price == low_range.min() and current_price not in support_levels:
            support_levels.append(round(current_price, 2))
        if current_price == high_range.max() and current_price not in resistance_levels:
            resistance_levels.append(round(current_price, 2))

    return {
        "support": sorted(support_levels),
        "resistance": sorted(resistance_levels)
    }

def get_symbol_data(symbol:str, data_client, timeframe: TimeFrame = TimeFrame(1, TimeFrameUnit.Day), lookback_days: int=30) -> Optional[dict]:
    end = pd.Timestamp.now(tz='UTC')
    start = end - pd.Timedelta(days=lookback_days)
    
    try:
        get_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end
        )
        bars_df = data_client.get_stock_bars(get_params).df
        time.sleep(API_DELAY)
    except Exception as e:
        print(f"Failed to get historical data for {symbol}: {e}")
        return None

    if bars_df.empty or symbol not in bars_df.index.get_level_values(0):
        return None
    bars = bars_df.loc[symbol].copy()

    bars["ema"] = bars["close"].ewm(span=10).mean()
    delta = bars["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    bars['rsi'] = 100 - (100 / (1 + rs))

    bars["high_low"] = bars["high"] - bars["low"]
    bars["high_close"] = (bars["high"] - bars["close"].shift()).abs()
    bars["low_close"] = (bars["low"] - bars["close"].shift()).abs()
    tr = bars[["high_low", "high_close", "low_close"]].max(axis=1)
    bars["atr"] = tr.rolling(window=14).mean()

    latest = bars.iloc[-1]
    if pd.isna(latest["rsi"]) or pd.isna(latest["ema"]) or pd.isna(latest["atr"]):
        print(f"Insufficient indicator data for {symbol}. Skipping.")
        return None
    levels = set_support_resistance(bars["close"])
    if levels is None:
        print(f"Could not calculate support/resistance for {symbol}")
        return None

    return {
        "latest_close": latest["close"],
        "ema": latest["ema"],
        "rsi": latest["rsi"],
        "atr": latest["atr"],
        "support_resistance": levels
    }

def set_buy_qty(account:dict, price:float, qty_held:float, cap_pct:float=.10) -> Optional[int]:
    portfolio_value = float(account["portfolio_value"])
    max_alloc = portfolio_value * cap_pct
    current_position_value = price * qty_held
    
    available_to_invest = max_alloc - current_position_value
    if available_to_invest <= 0:
        return None
    qty_to_buy = int(available_to_invest // price)
    return qty_to_buy if qty_to_buy >= 1 else None

def set_limit_order(symbol:str,data:dict, qty_held:float, account) -> Optional[dict]:
    price = data["latest_close"]
    ema = data["ema"]
    rsi = data["rsi"]
    levels = data["support_resistance"]

    # SELL LOGIC
    if qty_held > 0:
        if rsi < 30:
            return None

        resistance_levels = levels["resistance"]
        nearest_resistance = next((level for level in resistance_levels if level > price), None)
        if nearest_resistance is None or price < ema:
            return None

        limit_price = round(nearest_resistance * 0.99, 2)

        return {
            'symbol': symbol,
            'qty': qty_held,
            'side': 'sell',
            'type': 'limit',
            'limit_price': limit_price,
            'time_in_force': "day"
        }

    # BUY LOGIC
    buy_qty = set_buy_qty(account, price, qty_held)
    if buy_qty:
        if rsi > 60:
            return None

        support_levels = levels["support"]
        nearest_support = next((level for level in support_levels if level < price), None)
        if nearest_support is None or price > ema:
            return None

        limit_price = round(nearest_support * 1.01, 2)

        return {
            'symbol': symbol,
            'qty': buy_qty,
            'side': 'buy',
            'type': 'limit',
            'limit_price': limit_price,
            'time_in_force': "day"
        }

    return None

def set_stop_order(symbol: str, data: dict, qty_held: float) -> Optional[dict]:
    if qty_held <= 0:
        return None

    price = data["latest_close"]
    levels = data["support_resistance"]
    support_levels = levels["support"]
    atr = data.get("atr")
    atr_multiplier = 1.5

    if atr is None:
        return None

    nearest_support = next((level for level in support_levels if level < price), None)
    if nearest_support is None:
        return None
    
    buffer = atr*atr_multiplier
    raw_stop = nearest_support*.99
    stop_price = round(min(price-buffer, raw_stop),2)

    if (price - stop_price) / price < 0.02:
        return None

    return {
        'symbol': symbol,
        'qty': qty_held,
        'side': "sell",
        'type': "stop",
        'stop_price': stop_price,
        'time_in_force': "gtc"
    }

def set_trailing_stop_order(symbol:str, data:dict, qty_held:float, unrealized_plpc:float) -> Optional[dict]:
    price = data["latest_close"]
    atr = data.get("atr")    
    rsi = data.get("rsi")

    if qty_held <= 0:
        return None
    if price is None or atr is None or rsi is None:
        return None
    if unrealized_plpc is not None and unrealized_plpc >= 0.10:
        return None
    if rsi < 60:
        return None
    
    atr_multiplier = 1.5
    trail_percent = round((atr*atr_multiplier/price)*100,2)
    if trail_percent < 2.0:
        return None
    return {
        'symbol': symbol,
        'qty': qty_held,
        'side': "sell",
        'type': "trailing_stop",
        'trail_percent': trail_percent,
        'time_in_force': "gtc"
    }

def set_market_order(symbol:str, data:dict, qty_held:float, account, unrealized_plpc: Optional[float]=None) -> Optional[dict]:
    price = data["latest_close"]
    rsi = data["rsi"]
    ema = data["ema"]

    if qty_held > 0:
        if unrealized_plpc is None:
            return None

        if unrealized_plpc >= 0.10:  # 10% gain
            return {
                'symbol': symbol,
                'qty': qty_held,
                'side': 'sell',
                'type': 'market',
                'time_in_force': "day"
            }
        elif unrealized_plpc <= -0.05:  # 5% loss
            return {
                'symbol': symbol,
                'qty': qty_held,
                'side': 'sell',
                'type': 'market',
                'time_in_force': "day"
            }
        return None

    if rsi < 30 and price < ema:
        buy_qty = set_buy_qty(price, qty_held, account)
        if buy_qty and buy_qty >= 1:
            return {
                'symbol': symbol,
                'qty': buy_qty,
                'side': 'buy',
                'type': 'market',
                'time_in_force': "day"
            }
    return

def submit_order(trade:dict, trading_client) -> Optional[dict]:
    ORDER_TYPE_TO_CLASS = {
        "market": MarketOrderRequest,
        "limit": LimitOrderRequest,
        "stop": StopOrderRequest,
        "trailing_stop": TrailingStopOrderRequest,
    }

    order_type = trade["order_type"]
    order_class = ORDER_TYPE_TO_CLASS.get(order_type)

    if not order_class:
        print(f"Unsupported order type: {order_type}")
        return None

    try:
        order_request = order_class(
            symbol=trade["symbol"],
            qty=trade["qty"],
            side=OrderSide(trade["side"]),
            time_in_force=TimeInForce(trade["time_in_force"]),
            **{k: trade[k] for k in ["limit_price", "stop_price", "trail_percent"] if k in trade}
        )

        order = trading_client.submit_order(order_request)
        time.sleep(API_DELAY)

    except Exception as e:
        print(f"Order failed for {trade['symbol']}: {e}")
        return None

    receipt = {
        "id": order.id,
        "symbol": order.symbol,
        "qty": order.qty,
        "side": order.side,
        "type": order.type,
        "status": order.status,
        "submitted_at": order.submitted_at.isoformat()
    }
    return receipt

def main():
    logbook = { 'receipts':[]  }
    trading_client = TradingClient(API_KEY,API_SECRET,paper=True)
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
    account = trading_client.get_account() 
    daytrade_count = getattr(account, "daytrade_count", 0)
    check_daytrades(daytrade_count)
    full_watchlist = get_full_watchlist(trading_client)

    strategies = [
        set_limit_order,
        set_stop_order,
        set_trailing_stop_order,
        set_market_order
        ]

    while full_watchlist:    
        for symbol in list(full_watchlist.keys()):
            qty_held = full_watchlist[symbol]["qty"]
            unrealized_plpc = full_watchlist[symbol].get("unrealized_plpc", 0)

            if market_closing_soon():
                if qty_held < 1:
                    print(f"Skipping {symbol} - too close to market close.")
                    full_watchlist.pop(symbol)
                    time.sleep(API_DELAY)
                    continue
            time.sleep(API_DELAY)
            status = trade_status(symbol, trading_client)
            if status in ("open_order", "error"):
                continue
            if status == "bought_today":
                full_watchlist.pop(symbol)
                time.sleep(API_DELAY)
                continue

            data = get_symbol_data(symbol, data_client)
            if not data:
                continue
            
            trade = None
            for strategy in strategies:
                trade = strategy(symbol, data, qty_held, unrealized_plpc, account)
                if trade:
                    break

            #FUNCTION CALL FOR PUSH NOTIFICATION CONFIRMATION HERE. ADD TRY/EXCEPT BLOCK TO SAID FUNCTION.
            if not trade:
                continue
            submit = submit_order(trade, trading_client)
            if submit:
                if trade["side"] == "buy":
                    full_watchlist.pop(symbol)
                logbook['receipts'].append(submit)
                account = get_account(trading_client)
    print(f"No more trades for today. Logging trades and ending run.")
    with open("trade_receipts.json", "w") as f:
        json.dump(logbook['receipts'], f, indent=4)
if __name__ == "__main__":
    main()