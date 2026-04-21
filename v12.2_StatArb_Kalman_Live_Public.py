"""
Note: Parameters, credentials, and assets have been modified for intellectual property protection. 
The core logic, including stateful memory management and the daily killswitch, remains intact for architectural review.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from collections import deque

# ==========================================
# 1. VPS CREDENTIALS (SANITIZED)
# ==========================================
ACCOUNT_NUMBER = 123456789  
ACCOUNT_PASSWORD = "YOUR_PASSWORD" 
SERVER_NAME = "YOUR_BROKER_SERVER"

# ==========================================
# 2. BROKER EXECUTION FUNCTIONS 
# ==========================================
def calculate_volume(symbol):
    """Calculates volume dynamically based on equity tiers (Asymmetric Compounding)"""
    account_info = mt5.account_info()
    if account_info is None:
        print("     [ERROR] Unable to read balance. Safety measure: applying minimum volume.")
        return mt5.symbol_info(symbol).volume_min
        
    equity = account_info.equity
    
    # Tiered risk management
    if equity < 101000:
        multiplier = 0.03  
    elif 101000 <= equity < 106500:
        multiplier = 0.05  
    else:
        multiplier = 0.08  

    theoretical_vol = (equity / 1000) * multiplier
    symbol_info = mt5.symbol_info(symbol)
    step = symbol_info.volume_step
    min_vol = symbol_info.volume_min
    max_vol = symbol_info.volume_max
    
    final_volume = round(theoretical_vol / step) * step
    return max(min_vol, min(max_vol, final_volume))

def get_filling_mode(symbol):
    """Queries the broker using raw numerical values to bypass Python library bugs"""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return mt5.ORDER_FILLING_FOK
    
    filling_modes = symbol_info.filling_mode
    if filling_modes & 1:
        return mt5.ORDER_FILLING_FOK
    elif filling_modes & 2:
        return mt5.ORDER_FILLING_IOC
    else:
        return mt5.ORDER_FILLING_RETURN

def send_order(symbol, order_type):
    """Sends the live market order with dynamic filling mode"""
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    volume = calculate_volume(symbol)
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": 10,
        "magic": 999999, # Sanitized Magic Number
        "comment": "V12.2 StatArb Entry",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_mode(symbol),
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"     [ERROR] Order {symbol} failed: {result.comment}")
        return False
    return True

def close_symbol_positions(symbol):
    """Closes all open positions associated with the strategy"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None: return
    for pos in positions:
        if pos.magic == 999999: 
            inverse_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": symbol,
                "volume": pos.volume,
                "type": inverse_type,
                "price": price,
                "deviation": 10,
                "magic": 999999,
                "comment": "V12.2 Exit",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": get_filling_mode(symbol),
            }
            mt5.order_send(request)

# ==========================================
# 2.5 INSTITUTIONAL SHIELD & FILTERS
# ==========================================
midnight_equity = None
current_date = None

def killswitch_check():
    """Hardware-level shield: Triggers total liquidation if floating equity drops 4.5% from midnight."""
    global midnight_equity, current_date
    
    info = mt5.account_info()
    if info is None: return False
    
    today = datetime.now().date()
    
    if current_date != today or midnight_equity is None:
        midnight_equity = info.equity
        current_date = today
        print(f"\n[RISK MANAGEMENT] New trading session. Reference Equity: ${midnight_equity}")
        
    current_drawdown = ((info.equity - midnight_equity) / midnight_equity) * 100
    
    if current_drawdown <= -4.5:
        print(f"\n [RED ALERT] MAX DAILY DRAWDOWN REACHED ({current_drawdown:.2f}%).")
        print("KILLSWITCH ACTIVATED: EXECUTING TOTAL LIQUIDATION...")
        
        for pos in mt5.positions_get():
            close_symbol_positions(pos.symbol)
            
        print("System locked. Engine entering sleep mode until next session.")
        
        tomorrow = datetime.now() + timedelta(days=1)
        midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 1)
        wait_seconds = (midnight - datetime.now()).total_seconds()
        time.sleep(wait_seconds)
        return True 
        
    return False

def is_toxic_market():
    """Institutional Filter: Blocks entries during high-manipulation hours (UTC)."""
    now = datetime.utcnow()
    day = now.weekday() 
    hour = now.hour
    
    if day == 5: return True # Saturday
    if day == 4 and hour >= 20: return True # Friday close
    if day == 6 and hour < 23: return True # Sunday open
    return False

# ==========================================
# 3. INITIALIZATION 
# ==========================================
print("Starting V12.2 Engine: Connecting to broker server...")
if not mt5.initialize(login=ACCOUNT_NUMBER, password=ACCOUNT_PASSWORD, server=SERVER_NAME):
    print(f"Initialization failed. MT5 Error: {mt5.last_error()}")
    quit()

account_info = mt5.account_info()
if account_info is None or account_info.login != ACCOUNT_NUMBER:
    print("CRITICAL ERROR: Connected account does not match. Shutting down.")
    mt5.shutdown()
    quit()

print(f"AUTHORIZATION GRANTED: Connected to account [{account_info.login}]")
print(f"Detected Equity: ${account_info.equity} (LIVE execution enabled)\n")

# ==========================================
# 4. PORTFOLIO CONFIGURATION (SANITIZED)
# ==========================================
PORTFOLIO = [
    ("ASSET_A", "ASSET_B")
]

TIMEFRAME = mt5.TIMEFRAME_M5 
LOOKBACK = 500 
ENTRY_Z = 0.0  # Sanitized Threshold
EXIT_Z = 0.0   # Sanitized Threshold

engaged_currencies = set() 
active_spreads = {}       

def extract_currencies(symbol1, symbol2):
    """Extracts base and quote currencies to manage orthogonal correlation"""
    return {symbol1[:3], symbol1[3:], symbol2[:3], symbol2[3:]}

print(f"Radar active on {len(PORTFOLIO)} spreads. Correlation Management: ACTIVE.")
print("-" * 70)

# ==========================================
# 5. CORE ENGINE (STATEFUL KALMAN FILTER)
# ==========================================
print("Booting Institutional Engine...")
kalman_states = {} 

try:
    while True:
        if killswitch_check(): 
            continue 

        for asset1, asset2 in PORTFOLIO:
            spread_name = f"{asset1}_{asset2}"
            
            # --- INITIAL WARM-UP ---
            if spread_name not in kalman_states:
                rates1 = mt5.copy_rates_from_pos(asset1, TIMEFRAME, 0, LOOKBACK)
                rates2 = mt5.copy_rates_from_pos(asset2, TIMEFRAME, 0, LOOKBACK)
                if rates1 is None or rates2 is None: continue
                
                Y_hist = pd.DataFrame(rates1)['close'].values
                X_hist = pd.DataFrame(rates2)['close'].values
                
                delta = 1e-2 # Sanitized for IP protection
                wt = delta / (1 - delta) * np.eye(2)
                vt = 1e-3
                theta = np.zeros(2)
                P = np.zeros((2, 2))
                spread_history = deque(maxlen=LOOKBACK)
                
                print(f"[{time.strftime('%H:%M:%S')}] Kalman Filter warm-up for {spread_name}...")
                for i in range(len(X_hist)):
                    F = np.array([X_hist[i], 1.0])
                    R = P + wt
                    yhat = F.dot(theta)
                    et = Y_hist[i] - yhat
                    Qt = F.dot(R).dot(F) + vt
                    At = R.dot(F) / Qt
                    theta = theta + At * et
                    P = R - np.outer(At, F).dot(R)
                    
                    current_spread = Y_hist[i] - (theta[0] * X_hist[i])
                    spread_history.append(current_spread)
                
                kalman_states[spread_name] = {
                    'theta': theta, 'P': P, 'wt': wt, 'vt': vt, 
                    'spread_history': spread_history,
                    'last_time': rates1[-1]['time']
                }
            
            # --- LIVE UPDATE (Tick-by-Tick) ---
            state = kalman_states[spread_name]
            
            rates1 = mt5.copy_rates_from_pos(asset1, TIMEFRAME, 0, 1)
            rates2 = mt5.copy_rates_from_pos(asset2, TIMEFRAME, 0, 1)
            if rates1 is None or rates2 is None: continue
            
            y_live = rates1[0]['close']
            x_live = rates2[0]['close']
            t_live = rates1[0]['time']
            
            theta, P, wt, vt = state['theta'], state['P'], state['wt'], state['vt']
            
            if t_live != state['last_time']:
                F = np.array([x_live, 1.0])
                R = P + wt
                yhat = F.dot(theta)
                et = y_live - yhat
                Qt = F.dot(R).dot(F) + vt
                At = R.dot(F) / Qt
                
                theta = theta + At * et
                P = R - np.outer(At, F).dot(R)
                
                live_spread = y_live - (theta[0] * x_live)
                state['spread_history'].append(live_spread)
                
                state['theta'], state['P'], state['last_time'] = theta, P, t_live
            else:
                live_spread = y_live - (theta[0] * x_live)
            
            spread_array = np.array(state['spread_history'])
            if len(spread_array) < 2: continue
                
            spread_mean = spread_array.mean()
            spread_std = spread_array.std()
            if spread_std == 0: continue
                
            z_score = (live_spread - spread_mean) / spread_std
            
            # --- EXIT LOGIC ---
            if spread_name in active_spreads:
                if abs(z_score) <= EXIT_Z:
                    print(f"[{time.strftime('%H:%M:%S')}] TARGET REACHED | {spread_name}. Z: {z_score:+.2f}")
                    close_symbol_positions(asset1)
                    close_symbol_positions(asset2)
                    
                    trade_currencies = extract_currencies(asset1, asset2)
                    engaged_currencies.difference_update(trade_currencies)
                    del active_spreads[spread_name]
                    print("     [+] Trade closed and profits secured.\n")
                continue 
            
            # --- ENTRY LOGIC ---
            if z_score > ENTRY_Z or z_score < -ENTRY_Z:
                if is_toxic_market(): continue 

                required_currencies = extract_currencies(asset1, asset2)
                if not engaged_currencies.isdisjoint(required_currencies): continue 

                direction = "SHORT" if z_score > ENTRY_Z else "LONG"
                
                info1, info2 = mt5.symbol_info(asset1), mt5.symbol_info(asset2)
                if not info1 or not info2 or info1.spread > 30 or info2.spread > 30:
                    continue

                print(f"[{time.strftime('%H:%M:%S')}] EXECUTING {direction} | {asset1} vs {asset2} | Z-Score: {z_score:+.2f}")

                if direction == "SHORT":
                    res1 = send_order(asset1, mt5.ORDER_TYPE_SELL)
                    res2 = send_order(asset2, mt5.ORDER_TYPE_BUY)
                else:
                    res1 = send_order(asset1, mt5.ORDER_TYPE_BUY)
                    res2 = send_order(asset2, mt5.ORDER_TYPE_SELL)
                
                if res1 and res2:
                    active_spreads[spread_name] = direction
                    engaged_currencies.update(required_currencies)
                else:
                    close_symbol_positions(asset1)
                    close_symbol_positions(asset2)

        time.sleep(1) 

except KeyboardInterrupt:
    print("\n\nShutting down V12.2 Engine...")
    mt5.shutdown()