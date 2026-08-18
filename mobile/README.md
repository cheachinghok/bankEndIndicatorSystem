# Gold Signals — Flutter Mobile App

Mobile client for the Gold Signals backend. Phase 9 in the project plan.

## Sub-phases (what's built vs. what's coming)

- **9a — Dashboard (current)**: project scaffold, dark theme, REST client, Dashboard screen showing the latest XAUUSD price + recent candles.
- **9b**: Signals list + Signal Detail screens (reads `/api/v1/signals`).
- **9c**: Market Detail screen with candle chart (`fl_chart`).
- **9d**: WebSocket integration for live price + signal push.
- **9e**: iOS + Android release builds.

## Prerequisites

- Flutter 3.35+ (`flutter --version` to check)
- Xcode (for iOS builds) — you already have signing set up
- Android Studio or command-line tools (for Android)

## First-time setup

1. **Set your backend URL.** Copy the env template and fill in your Railway URL:
   ```bash
   cd /Users/chinghok/gold-signals/mobile
   cp .env.example .env
   ```
   Then edit `.env`:
   ```
   API_BASE_URL=https://your-service.up.railway.app
   DEFAULT_SYMBOL=XAUUSD
   ```

2. **Install packages.**
   ```bash
   flutter pub get
   ```

3. **Generate Freezed / JSON code.** (Needed once, and after every model change.)
   ```bash
   dart run build_runner build --delete-conflicting-outputs
   ```

## Running the app

**On the iOS Simulator:**
```bash
open -a Simulator
flutter run
```

**On a physical iPhone** (already signed via Xcode):
```bash
flutter run -d <device-id>
```
(Get device id via `flutter devices`.)

**On Android emulator or device:**
```bash
flutter run
```
(Flutter will pick whatever emulator or connected device it finds.)

## Project layout

```
lib/
├── main.dart                             # entry point + ProviderScope
├── core/
│   ├── config/app_config.dart            # env-var wrapper (API URL, symbol)
│   ├── theme/app_theme.dart              # dark theme + bull/bear colours
│   ├── network/dio_client.dart           # shared Dio + Riverpod providers
│   └── router/app_router.dart            # go_router routes
├── features/
│   ├── market/
│   │   ├── domain/candle.dart            # Freezed Candle + CandlesResponse
│   │   ├── data/market_repository.dart   # REST /market/{symbol}/candles
│   │   └── presentation/market_providers.dart
│   ├── dashboard/
│   │   └── presentation/dashboard_screen.dart
│   ├── signals/                          # (9b)
│   ├── market_detail/                    # (9c)
│   ├── backtesting/                      # (9c or later)
│   └── settings/                         # later
└── shared/                               # cross-feature widgets, extensions
```

## Design notes

- **State**: Riverpod (`flutter_riverpod` + `riverpod_annotation` for codegen).
- **HTTP**: Dio. Base URL is `${apiBaseUrl}/api/v1`.
- **JSON**: Freezed + json_serializable (deterministic, null-safe, generated).
- **Routing**: `go_router`.
- **No secrets in the client**: the Railway backend holds all OANDA credentials. This app talks only to your public API.

## After every model change

Regenerate:
```bash
dart run build_runner build --delete-conflicting-outputs
```

## Troubleshooting

- **"API_BASE_URL missing from .env"** on launch → you haven't created `.env` yet, or the file is at the wrong path. Must be `mobile/.env`.
- **Dio 404 on `/market/XAUUSD/candles`** → your API base URL is missing the `https://` or has a stray path segment.
- **Empty dashboard, no error** → backend has no candles for the requested timeframe. Poll history or wait for the candle poller to fill in.
- **`build_runner` complains about conflicting outputs** → the `--delete-conflicting-outputs` flag in the command above handles that.
