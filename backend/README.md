# Gold Signals Backend (Phase 1)

FastAPI backend that pulls XAUUSD candles from OANDA into Postgres and exposes them via REST.

**Scope of this phase:** market-data ingest + REST only. No signal engine, no WebSocket, no auth, no Flutter — those come in later phases per the project plan.

---

## Prerequisites

- **Docker Desktop** (for Postgres + Redis)
- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or `pip`
- An **OANDA fxTrade practice account** — free.
  1. Sign up: https://www.oanda.com/apply/ (choose "Practice / demo")
  2. Generate a personal access token: https://www.oanda.com/demo-account/tpa/personal_token
  3. Note your account ID from the OANDA dashboard.

---

## First-time setup

```bash
cd /Users/chinghok/gold-signals/backend

# 1. Environment
cp .env.example .env
# then edit .env and fill in OANDA_API_TOKEN and OANDA_ACCOUNT_ID

# 2. Python deps (pick one)
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
# OR
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# 3. Start Postgres + Redis
docker compose up -d

# 4. Run migrations
alembic upgrade head
```

---

## Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Check it's up:

```bash
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

Fetch XAUUSD 15-minute candles (backfills from OANDA the first time, then serves from Postgres):

```bash
curl "http://localhost:8000/api/v1/market/XAUUSD/candles?timeframe=15m&limit=100"
```

Supported timeframes: `5m`, `15m`, `30m`, `1h`, `4h`, `1d`.

---

## Tests

```bash
# Unit tests (no DB required)
pytest tests/unit

# Integration tests (require running docker compose + migrations)
pytest tests/integration

# Everything
pytest
```

---

## Project layout (Phase 1 only)

```
app/
  api/v1/               REST routes (market.py)
  core/                 config
  db/                   SQLAlchemy models + Alembic migrations
  repositories/         DB access layer
  services/
    market_data/        MarketDataProvider interface + OANDA implementation
  # (indicators/, signals/, analysis/, risk/, news/, notifications/, workers/,
  # backtesting/ dirs are placeholders — filled in later phases)
tests/
  unit/
  integration/
```

---

## Design invariants (do not break)

- **All candle timestamps stored in UTC.** Display-time conversion only.
- **`MarketDataProvider` is the boundary.** Never import `OandaProvider` outside `services/market_data/` or `api/v1/market.py`. Future MT5 provider slots in behind the same interface.
- **Closed candles only** — the OANDA provider drops `complete=false` candles. This is what prevents look-ahead in later phases.

---

---

# Phase 2 — Live streaming + WebSocket

Phase 2 adds a background worker that:
1. Streams live prices from OANDA's SSE endpoint into Redis (pub/sub + latest-price key with 30s TTL).
2. Polls closed candles every 30s for each timeframe and upserts them into Postgres, publishing new candles on Redis.

A WebSocket endpoint fans this data out to connected clients.

## Run the worker

In a **new terminal** (with the venv active and Docker up):

```bash
cd /Users/chinghok/gold-signals/backend
source .venv/bin/activate
python -m app.workers.main
```

You should see log lines like:
```
INFO workers: workers started: ['XAUUSD']
INFO app.workers.price_stream: connecting price stream for ['XAUUSD']
INFO app.workers.candle_poller: poll XAUUSD 15m: inserted 1, newest ts=...
```

## Test the WebSocket

Install a WS CLI once:
```bash
brew install websocat   # or: npm i -g wscat
```

Then in another terminal:
```bash
websocat ws://localhost:8000/api/v1/ws/market/XAUUSD
```

You'll receive JSON messages as prices update:
```json
{"type":"price","symbol":"XAUUSD","timestamp":"2026-...Z","bid":2400.10,"ask":2400.30,"mid":2400.20,"tradeable":true}
{"type":"candle","symbol":"XAUUSD","timeframe":"15m","timestamp":"2026-...Z","open":...,"close":...}
```

**Note on trading hours**: OANDA's XAUUSD stream is quiet on weekends (Friday NY close → Sunday open). If you're not seeing ticks, check the day/time.

## Phase 2 verification

- Worker log shows `poll XAUUSD 15m: inserted N` at least once (proves candle poller works).
- Worker log shows continuous stream activity during market hours (proves SSE works).
- `redis-cli GET price:XAUUSD` returns a JSON tick payload (proves latest-price cache works).
- `websocat ws://localhost:8000/api/v1/ws/market/XAUUSD` streams live JSON (proves WS fanout works).

Once Phase 2 verifies for you, Phase 3 starts the indicator library (EMA / RSI / MACD / ATR) and Phase 4 wires the market-analysis engine.

---

# Phase 3 — Indicator library

Pure-Python indicators at `app/services/indicators/`. No new dependencies (no `pandas-ta`, no `numpy`) — deterministic, easy to test, fast enough at MVP scale.

## What's implemented

| Indicator | Function | Latest-value helper | Incremental |
|---|---|---|---|
| EMA (SMA-seeded) | `ema(values, length)` | `ema_latest(...)` | `IncrementalEMA` (O(1) push) |
| RSI (Wilder) | `rsi(values, length=14)` | `rsi_latest(...)` | — |
| MACD (12/26/9 default) | `macd(values, fast, slow, signal)` → `MacdResult` | `macd_latest(...)` → `(macd, signal, hist)` | — |
| ATR (Wilder) | `atr(highs, lows, closes, length=14)` | `atr_latest(...)` | — |

**Design notes:**
- All batch functions return `list[float]` with `math.nan` for the warmup period (first `length-1` or `length` values, depending on indicator). Callers should filter NaN before using values.
- **SMA-seeded EMA** is the TradingView / MT5 convention. The value at index `length-1` is the SMA of the first `length` inputs; the EMA recursion starts from there.
- **Wilder smoothing** for RSI and ATR — matches TradingView's default RSI (not the "exponential RSI" variant).
- `IncrementalEMA` exists for the live signal path (update EMA on each new closed candle in O(1) instead of recomputing over history). RSI/MACD/ATR are batch-only for now — the analysis engine can call batch on the last N candles each tick; it's fast enough. Incremental variants will come if profiling demands.

## Usage

```python
from app.services.indicators import (
    closes, highs, lows,
    ema_latest, rsi_latest, macd_latest, atr_latest,
)

# `candles` is a list[Candle] from the DB
close_s = closes(candles)
ema200 = ema_latest(close_s, length=200)
rsi14 = rsi_latest(close_s)
macd_line, signal_line, hist = macd_latest(close_s)
atr14 = atr_latest(highs(candles), lows(candles), close_s)
```

## Tests

```bash
pytest tests/unit/test_indicators.py -v
```

Tests use hand-verifiable inputs (constant series, monotonic series, small hand-computed examples) rather than snapshot testing, so any regression is immediately readable.

---

# Phase 4 — Market Analysis Engine

Consumes Phase 3 indicators. For one timeframe of candles, returns per-bucket direction (BULLISH / BEARISH / NEUTRAL) + score + human-readable reasons. Signal engine (Phase 5) will combine across timeframes.

## Scoring buckets

| Bucket | Max | What it measures |
|---|---:|---|
| Trend | 25 | EMA 20/50/200 alignment + price position + EMA20 slope |
| Momentum | 20 | RSI direction + MACD histogram polarity + not overbought/oversold |
| Structure | 20 | Swing HH/HL vs LH/LL sequence + BOS + CHoCH |
| Support/Resistance | 15 | Proximity to nearest S/R zone (favorable side only) |
| Volatility | 10 | ATR as % of price, bucketed (LOW/NORMAL/HIGH/EXTREME) |
| **Analysis total** | **90** | — |
| R:R (Phase 5) | 10 | Distance to stop vs distance to target |
| **Grand total** | **100** | — |

## Aggregate direction

`majority(trend, momentum, structure)` — ties or all-neutral become NEUTRAL. Volatility and S/R don't vote (S/R depends on knowing the direction first).

## Public API

```python
from app.services.analysis import analyze, Direction

result = analyze(candles)  # candles: list[Candle] (any timeframe)

result.direction          # Direction.BULLISH | BEARISH | NEUTRAL
result.score              # 0..90
result.trend.direction    # per-bucket direction
result.trend.score        # per-bucket score
result.reasons            # list[str] — for the Signal Detail screen
result.warnings           # list[str] — "extreme volatility", etc.
```

## Design notes

- **Bucket dataclasses are frozen** — analyzers are pure functions, no hidden mutable state. Same input → same output.
- **Engine is FastAPI-free** — the same engine will run inside the backtester (Phase 6) with identical logic.
- **Volatility has no direction** — it modulates confidence for both bull and bear equally. XAUUSD-tuned thresholds (0.15% / 0.60% / 1.20%).
- **S/R clustering is 0.5 × ATR** — same wick tested twice doesn't double-count. "Near" means within 1.5 × ATR.

## Tests

```bash
pytest tests/unit/test_analysis.py -v
```

---

# Phase 5 — Signal Engine

Turns per-timeframe `AnalysisResult`s into a `SignalResult` (BUY / SELL / WAIT) with confidence 0..100, entry, stop-loss, two take-profit targets, and a full audit trail.

## Multi-timeframe gate

Timeframes have distinct roles:

| TF | Role | Gate |
|---|---|---|
| **4H** | Major trend | Must be BULL or BEAR (NEUTRAL → WAIT) |
| **1H** | Confirmation | Must not disagree with 4H (NEUTRAL is allowed) |
| **15M** | Primary decision TF | Must not disagree with 4H |
| **5M** | Optional refinement | Contributes to confidence weight only |

Blend weights: **4H 40%, 1H 30%, 15M 20%, 5M 10%** — higher TFs are more reliable, so they count more.

## Risk / Reward (XAUUSD defaults)

| Item | Default | Notes |
|---|---:|---|
| Stop loss | 1.5 × ATR | ~1 candle's noise |
| Take profit 1 | 3.0 × ATR | R:R = 2.0 |
| Take profit 2 | 4.5 × ATR | R:R = 3.0 |
| R:R score | 0..10 | 0 for R:R<1.0, linear to 10 at R:R≥2.5 |

## Confidence math

```
confidence = blended_analysis_score (0..90) + risk_reward_score (0..10)
```

**Confidence is NOT probability.** It's the strength of the setup vs the strategy. UI must label as "Setup Strength" and include a disclaimer.

## Public API

```python
from app.services.signals import generate_signal, SignalDirection

result = generate_signal("XAUUSD", analyses_by_tf)
# analyses_by_tf: dict[str, AnalysisResult] — keys: "4h","1h","15m","5m"

result.direction          # SignalDirection.BUY | SELL | WAIT
result.confidence         # 0..100
result.entry / stop_loss / take_profit_1 / take_profit_2 / risk_reward
result.breakdown          # dict[str, float] — per-TF and R:R contributions
result.reasons            # list[str] — for the Signal Detail screen
result.warnings           # list[str]
```

## Database

`signals` table (migration `0002_signals`). Stores every generated signal — including WAITs — so we can measure strategy calibration over time. `breakdown`/`reasons`/`warnings` are JSON columns; the Signal Detail screen reads directly from them.

## Run the new migration

```bash
alembic upgrade head
```

## Tests

```bash
pytest tests/unit/test_signals.py -v
```

---

# Phase 6 — Backtesting Engine

Walk-forward simulator using the **exact same** `generate_signal` engine that runs live. Strict no-look-ahead. Realistic execution (spread / slippage / SL-first pessimistic rule).

## What it does

For each 15m candle in the historical dataset:
1. Slice each timeframe's candles to only what was CLOSED at that moment (no look-ahead).
2. Run `analyze()` on each TF, then `generate_signal()`.
3. If a position is open, check whether the current 15m bar hit SL or TP.
4. If no position is open AND the signal is actionable AND confidence ≥ threshold: open a new position on the **next** bar's open.
5. Track equity, drawdown, and a full trade log.

## Configuration (XAUUSD defaults)

```python
from app.backtesting import BacktestConfig

BacktestConfig(
    initial_equity=10_000.0,
    risk_per_trade_pct=1.0,
    min_confidence=60.0,
    spread=0.30,
    slippage_entry=0.20,
    slippage_sl=0.50,
    allow_pyramiding=False,
)
```

## Public API

```python
from app.backtesting import run_backtest, BacktestConfig

# candles_by_tf: {"4h": [...], "1h": [...], "15m": [...], "5m": [...]}
result = run_backtest(candles_by_tf, symbol="XAUUSD", config=BacktestConfig())

result.stats.total_trades
result.stats.win_rate               # 0..1
result.stats.profit_factor          # gross_profit / gross_loss
result.stats.net_profit             # currency
result.stats.net_profit_pct         # % of initial equity
result.stats.max_drawdown_pct       # % from peak equity
result.stats.avg_rr_realized        # in R multiples
result.stats.max_consecutive_losses
result.equity_curve                 # list[(datetime, float)]
result.trades                       # list[Trade] — full audit trail
```

## Execution model

- **Entry**: mid-price → BUY fills at `mid + spread/2 + slippage_entry` (ask + adverse), SELL mirrors.
- **Stop loss**: triggers at SL price, fills at `SL - slippage_sl` (worse) for BUY.
- **Take profit**: fills at the exact TP price (limit order assumption).
- **Same-bar collision**: if a single 15m bar's H/L touches both SL and TP, SL is assumed to have fired first (pessimistic).

## Assumptions / limitations

- One symbol per backtest (no portfolio correlation).
- Full exit at TP1 — TP2 partial exits are NOT modeled in this MVP.
- Intra-15m execution approximated by 15m OHLC (5m-precision execution is future work).
- No commission modeled (OANDA-style embedded in spread). Add if using a commission-based broker.
- Weekends aren't candle-filled by OANDA, so they don't confuse the loop; but be aware if using a different data source.

## No-look-ahead invariant

Enforced by `align_all_timeframes(candles_by_tf, at_instant)` — for every TF, only candles whose CLOSE time is ≤ `at_instant` are returned. There is a dedicated test (`test_backtest_no_look_ahead_invariant`) that mutates the last 100 candles wildly and asserts that trades entered before the mutation zone are **identical** in both runs. If look-ahead is ever accidentally introduced, that test fails immediately.

## Tests

```bash
pytest tests/unit/test_backtest.py -v
```

---

# Phase 7 — REST endpoints (signals + backtest)

## New endpoints

### Signals

```
GET  /api/v1/signals?symbol=XAUUSD&min_confidence=70&direction=BUY&limit=50
GET  /api/v1/signals/{id}
```

Reads the `signals` table. `direction` filter is optional and can be `BUY`, `SELL`, or `WAIT`. Default limit 50, max 500.

### Backtests

```
POST /api/v1/backtest      body: BacktestRequest
GET  /api/v1/backtest/{id}
GET  /api/v1/backtest?limit=50
```

`POST /api/v1/backtest` runs synchronously (the work happens in a thread so it doesn't block the event loop), stores the result, and returns the full result including trade log and equity curve.

## Migration

The `backtest_runs` table needs a new migration:

```bash
alembic upgrade head    # applies 0003_backtest_runs
```

## Example — running a backtest against your live candle DB

```bash
curl -s -X POST http://localhost:8000/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","initial_equity":10000,"min_confidence":60}' \
  | python3 -m json.tool | head -80
```

Response includes:
- `stats` — win_rate, profit_factor, net_profit_pct, max_drawdown_pct, avg_rr_realized, etc.
- `trades` — every trade with entry/exit/PnL
- `equity_curve` — full time series

**IMPORTANT**: for the backtest to produce meaningful results you need a lot of history in Postgres — the higher timeframe (4h) needs ~35 days of candles seeded before the trend indicator becomes valid. Two options:

1. Let the candle poller run for at least a month.
2. Or backfill by calling `GET /api/v1/market/XAUUSD/candles?timeframe=4h&limit=5000` (this fetches from OANDA and stores; do the same for 1h and 15m). Note OANDA rate-limits requests, so several minutes may be needed for a large backfill.

## Example — listing signals

```bash
curl -s "http://localhost:8000/api/v1/signals?limit=10&min_confidence=70" | python3 -m json.tool
```

## Tests

```bash
pytest tests/unit/test_backtest_service.py -v
```

(Full end-to-end API tests hitting a live Postgres are exercised manually via curl.)

---

# Phase 8 — Live signal generation (loop closed)

The backend now completes the full loop end-to-end:

```
OANDA stream ─▶ price_stream_worker ─▶ Redis prices:*
                                         │
OANDA candles ▶ candle_poller ▶ Postgres market_data
                     │
                     └─▶ Redis candles:XAUUSD:15m  (only on NEW inserts)
                                    │
                                    ▼
                   signal_worker (subscribed to that channel)
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
       load candles       analyze() +      insert into
       from Postgres    generate_signal    signals table
                              │
                              ▼
                       Redis signals:XAUUSD ─▶ /ws/market/XAUUSD ─▶ Flutter
```

## What's new

- `app/workers/signal_worker.py` — subscribes to `candles:{symbol}:15m` (published by the poller). On each event, loads 500 candles per TF from Postgres, runs the analysis + signal engine, persists to the `signals` table, and publishes on `signals:{symbol}`.
- `app/workers/main.py` — spawns the signal worker alongside the price stream and candle poller.
- `app/api/v1/ws.py` — WebSocket now subscribes to `signals:{symbol}` too and forwards `{"type":"signal",...}` frames to clients.

## Verify

1. **Restart the worker** (it now includes the signal worker):
```bash
cd /Users/chinghok/gold-signals/backend
source .venv/bin/activate
python -m app.workers.main
```

You should see in the log after startup:
```
INFO app.workers.signal_worker: signal worker subscribed to candles:XAUUSD:15m
```

2. **Wait for the next 15m candle to close** (or trigger manually — see below). When the poller inserts a new 15m candle, the signal worker fires:
```
INFO app.workers.candle_poller: poll XAUUSD 15m: inserted 1, ...
INFO app.workers.signal_worker: signal generated: XAUUSD BUY conf=72.5 (4H+1H+15M aligned BULLISH)
```

3. **See the persisted signal via REST:**
```bash
curl -s "http://localhost:8000/api/v1/signals?limit=5" | python3 -m json.tool
```

4. **See it stream over WebSocket:**
```bash
websocat ws://localhost:8000/api/v1/ws/market/XAUUSD
```
Look for `{"type":"signal",...}` lines mixed in with the prices and candles.

## Trigger a signal without waiting for the next 15m close

For testing, manually publish a fake candle-closed event:
```bash
cd /Users/chinghok/gold-signals/backend
docker compose exec redis redis-cli PUBLISH candles:XAUUSD:15m '{"trigger":"manual"}'
```

The signal worker will react immediately (log line + signal in DB + WS frame).

## Requirements for real signals

Same as backtest: the signal worker needs ~35 days of 4h candles in Postgres for the trend indicator to seed. Below that it logs `signal worker: skipping XAUUSD — 4h has only N candles (need ≥210)`. Backfill by hitting the market endpoint with a large `limit` for each TF.

## Tests

```bash
pytest tests/unit/test_signal_worker.py -v
```

## Next

Phase 9 = Flutter mobile app (Dashboard, Signals, Market Detail, Signal Detail screens per the original spec).
Phase 10 = auth + push notifications (Firebase Auth + FCM).
Phase 11 = ML confirmation layer (only after enough signal history + backtest validation).

---

# Phase 8.5 — Deploy to Railway

Everything you built in Phases 1–8 runs locally. Before touching Flutter, deploy the backend to Railway so the mobile app can hit a real production URL from day one.

## What's in the repo for deployment

| File | Purpose |
|---|---|
| `Dockerfile` | Reproducible container. Same image serves both services (different start commands). |
| `.dockerignore` | Keeps `.env`, `.venv`, `.git`, tests out of the image. |
| `railway.toml` | Declares Dockerfile builder + healthcheck + restart policy for the default service (API). |
| `app/main.py` `/healthz` | Deep health check — pings Postgres + Redis. Returns 503 if either is down, so Railway routes away from bad instances. |
| `app/core/config.py` | Auto-transforms Railway's `postgres://` DATABASE_URL to `postgresql+asyncpg://`. |

## One-time Railway setup

1. **Sign up** at https://railway.app (GitHub login is easiest).
2. **New Project** → **Deploy from GitHub repo** → pick `cheachinghok/bankEndIndicatorSystem`.
3. Railway will detect the `Dockerfile` (via `railway.toml` at repo root — but ours is in `backend/`, see step 4).
4. **IMPORTANT — set the root directory**: in service Settings → Source → set **Root Directory** to `backend`. This is needed because our code lives in `backend/`, not the repo root.
5. **Add Postgres**: Project → New → Database → **PostgreSQL**. Railway auto-injects `DATABASE_URL` into the service.
6. **Add Redis**: Project → New → Database → **Redis**. Auto-injects `REDIS_URL`.
7. **Add environment variables** to the API service (Settings → Variables):
   - `OANDA_API_TOKEN` = *your new rotated token*
   - `OANDA_ACCOUNT_ID` = *your practice account id*
   - `OANDA_API_URL` = `https://api-fxpractice.oanda.com` (change to `https://api-fxtrade.oanda.com` for live later)
   - `OANDA_ENVIRONMENT` = `practice`
   - `LOG_LEVEL` = `INFO`
   - Do NOT set `DATABASE_URL` or `REDIS_URL` manually — Railway injects those.
8. **Deploy** — Railway builds the image and runs the API. Watch build logs.
9. **Verify** — Railway gives you a URL like `https://<something>.up.railway.app`. Hit `https://<url>/healthz`:
   ```json
   {"api":"ok","db":"ok","redis":"ok"}
   ```

## Add the second service — the workers

The API service is running. The workers (price stream + candle poller + signal worker) need their own Railway service pointing to the same repo, with a different start command.

1. In the same project → **New** → **GitHub Repo** → pick the same repo.
2. Root Directory: `backend` (same as before).
3. Settings → **Deploy** → **Custom Start Command**: `python -m app.workers.main`
4. Settings → **Variables** → **Reference Variables** → copy all the OANDA vars from the API service. Do NOT reset DATABASE_URL / REDIS_URL — Railway shares those across services in the same project via the built-in references.
5. Deploy. Logs should show:
   ```
   INFO workers: workers started: ['XAUUSD']
   INFO app.workers.signal_worker: signal worker subscribed to candles:XAUUSD:15m
   INFO app.workers.price_stream: first tick received: XAUUSD bid=... ask=...
   ```

## Backfill history so signals actually fire

The signal worker needs ~35 days of 4h candles before it can compute trend. Trigger backfill by hitting the market endpoint (replace `<url>` with your Railway URL):

```bash
for tf in 4h 1h 15m; do
  curl -s "https://<url>/api/v1/market/XAUUSD/candles?timeframe=$tf&limit=1000" > /dev/null
done
```

Then trigger a signal manually to test the loop (you'll need railway CLI or another way to run redis-cli in the deployed Redis; easiest is to just wait for the next 15m candle close, which happens every 15 minutes).

## Cost expectations

- Postgres: ~$5/mo
- Redis: ~$5/mo
- API service compute: ~$5/mo
- Worker service compute: ~$5/mo
- **Total: ~$20/mo** at MVP scale. Scale up as needed.

## Rotating the OANDA token (do NOT skip)

If the token you're deploying with has been in shell history or curl -v output at any point, **rotate it before deploying**:
1. https://www.oanda.com/demo-account/tpa/personal_token → Revoke
2. Generate a new one → paste ONLY into Railway env vars → never anywhere else

## Next

Phase 9 = Flutter mobile app, pointing at your Railway URL.
