# Statistical Arbitrage via State-Space Modeling (Kalman Filter) in High-Frequency FX

## Abstract
This repository documents the end-to-end research, validation, and production deployment of a market-neutral Statistical Arbitrage strategy (v12.2). The research focuses on extracting alpha from the transient breakdown of cointegration between highly correlated FX pairs (e.g., Asset A and Asset B) using a 5-minute timeframe.

Moving beyond static Ordinary Least Squares (OLS) regression, this model implements a recursive Kalman Filter to dynamically estimate the hedge ratio ($\beta$). The project demonstrates a rigorous quantitative pipeline: massive data ingestion, strict Out-Of-Sample (OOS) blind testing, injection of real-world market friction, and a stateful production architecture engineered to comply with strict proprietary trading firm risk mandates.

## 1. The Alpha Hypothesis & Mathematical Framework
Standard pairs trading relies on historical beta estimation, which is highly susceptible to look-ahead bias and structural market breaks. To resolve this, I modeled the spread relationship as a state-space system.

* **Observation Equation:** $y_t = x_t \theta_t + v_t$
* **State Equation:** $\theta_t = \theta_{t-1} + w_t$

Where $y_t$ is the price of Asset A, $x_t$ is Asset B, $\theta_t$ is the dynamic hedge ratio (Beta), and $v_t$, $w_t$ are the measurement and system noise respectively. By recursively updating the covariance matrix at each tick, the model adapts to micro-structural changes in real-time without relying on static historical lookbacks. The trading signal is generated via a rolling Z-Score of the residual spread, triggering mean-reversion entries at $\pm 2.0$ standard deviations.

## 2. Data Engineering & Integrity
A robust quantitative model is only as good as its data. Relying on standard broker exports is insufficient due to pagination limits and missing data points.

* **Custom Ingestion Engine:** I built a pagination-based script (`00_Data_Ingestion_Pagination.ipynb`) to bypass MetaTrader 5 server limits, extracting over 100,000 clean M5 candles per asset.
* **Data Integrity Check:** During the initial pipeline construction, a schema mismatch occurred (`KeyError: 'close_B'`) due to an automated string-slicing logic in the ingestion engine. This was documented, debugged, and resolved, establishing a strict naming convention across the pipeline.
* **The Split:** To prevent data snooping, the dataset was strictly partitioned into a 70% In-Sample training set (~70,000 candles) and a 30% Out-Of-Sample testing set (~30,000 candles).

## 3. Quantitative Research & The Reality Check
The initial In-Sample vectorized backtest yielded an exceptionally smooth equity curve. However, transparency and skepticism are core to this research. I identified two critical flaws in the naive assumption:

* **Overfitting:** The parameters were optimized for the In-Sample regime.
* **The Gross Profit Illusion:** The model measured theoretical spread points, ignoring transaction costs.

### In-Sample Training (Gross Equity)
<img width="1156" height="624" alt="01_training_data_In-Sample" src="https://github.com/user-attachments/assets/c5d048e9-4a9b-4b2d-856b-e4a350360be0" />


**The Blind Test (OOS) & Market Friction Injection:**
To validate the alpha, the exact parameters ($\Delta = 1e-5$, Lookback = 500) were locked and tested on the OOS dataset (Nov 2025 - Apr 2026). Furthermore, I injected a heavy friction penalty (estimated 2 pips total for spread, commission, and slippage per round trip) directly into the vectorized array.

The strategy survived the friction, retaining approximately 72% of its gross profit, confirming that the identified market inefficiency was genuine and tradable.

### Out-of-Sample Blind Test (Net vs Gross)
<img width="1165" height="624" alt="02_Net_vs_Gross_Out-ofSample" src="https://github.com/user-attachments/assets/785a7919-6b1e-4203-a593-5a955dad53ff" />


## 4. Risk Management & Proprietary Firm Compliance
Institutional trading prioritizes capital preservation over maximum yield. The strategy was stress-tested against the strict risk mandates of proprietary trading firms (e.g., 5% Daily Drawdown, 10% Maximum Drawdown).

* **The Position Sizing Error:** Initial simulations utilizing a fixed 0.50 lot size on a 10,000 USD account yielded a 43% ROI but suffered a -14.12% Maximum Drawdown. This would have triggered an automatic account termination in a live environment.
* **The Correction:** By scaling risk down to 0.25 lots (Asymmetric Compounding), the total drawdown was compressed to a safe -7.82%.

### Institutional Money Management
<img width="1389" height="989" alt="03_Money_Management" src="https://github.com/user-attachments/assets/236d3fa8-63cf-44ea-8344-1f09382ca765" />


* **Forensic Daily Drawdown Analysis:** I conducted a daily forensic analysis of the account balance. The worst single-day drawdown recorded was -4.00% (Jan 27, 2026). The algorithm never breached the 5% daily failure threshold.

### Daily Drawdown Forensic Analysis
<img width="1232" height="547" alt="04_Daily_Drawdown_Test" src="https://github.com/user-attachments/assets/bd1c0fd2-0d63-40f6-a4fb-fc72b90ed48b" />


## 5. Production Engineering (v12.2)
Transitioning from a vectorized Jupyter environment to live execution requires fundamental architectural changes to manage memory and asynchronous events.

* **Stateful Memory Management:** Instead of recalculating the Kalman matrix over 500 candles at every tick (computationally heavy and prone to look-ahead bias), v12.2 runs an initial warm-up loop. It then stores $\theta$ and $P$ (covariance) in memory, updating the matrix via O(1) complexity on new incoming ticks. Z-score calculations are handled efficiently using a `collections.deque` object.
* **Hardware-Level Safety (Daily Killswitch):** To guarantee survival against Black Swan events, the production code includes an autonomous risk module. It logs the equity at 00:00 UTC. If floating PnL breaches -4.5% intraday, it overrides the trading logic, sends `ORDER_TYPE_SELL/BUY` commands to liquidate all positions instantly, and halts the process thread until the next trading day.
* **Broker IPC Resilience:** Addressed and resolved `IPC timeout` errors by dynamically mapping the correct broker server (TenTrade) and bypassing hardcoded executable paths.

## 6. Out-Of-Sample Performance Metrics (Net of All Costs)
* **Testing Period:** 5 Months (Blind OOS)
* **Initial Capital:** 10,000.00 USD
* **Final Net Equity:** 12,160.55 USD
* **Net ROI:** +21.61%
* **Total Trading Costs (Friction):** ~840.12 USD
* **Max Total Drawdown:** -7.82%
* **Max Daily Drawdown:** -4.00%
* **Total Executions:** 84 Round Trips

## 7. Acknowledgments & AI Assistance
In my opinion, the transparency is a core principle of quantitative research. The architecture, mathematical modeling, and codebase of this project were developed in collaboration with Google's Gemini (specifically, the Gemini 3.1 Pro model) acting as an advanced pair-programmer and research assistant. The AI was instrumental in structuring the vectorized backtesting environment, refactoring the production code for stateful memory management, and formatting this documentation.

## Further Research
Future iterations will focus on Orthogonal Diversification. By deploying this logic across multiple uncorrelated cointegrated pairs simultaneously (e.g., AUD/CAD, EUR/GBP), the objective is to compound returns while naturally smoothing the aggregate equity curve through non-correlated drawdown periods.
