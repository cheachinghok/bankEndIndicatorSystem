# Release Builds — iOS & Android

Everything below assumes the app already runs in debug (`flutter run`) and you're on macOS.

Before shipping any build, confirm:
- `mobile/.env` has the real production `API_BASE_URL` (your Railway URL). This file is bundled as an asset — its contents ship inside the app.
- `pubspec.yaml` `version:` is bumped for each release (format: `major.minor.patch+buildNumber`, e.g. `0.2.0+2`).

Both platforms:
```bash
cd /Users/chinghok/gold-signals/mobile
flutter pub get
flutter analyze --no-fatal-infos    # must be clean
```

---

## iOS — TestFlight

You already have an Apple Developer account and Xcode is configured with your Apple ID (I saw the auto-picked signing cert during `flutter create`). This flow ships to TestFlight, which lets you install on your own devices and invite testers.

**One-time setup:**

1. Open the iOS project in Xcode:
   ```bash
   open ios/Runner.xcworkspace
   ```
   (Use `.xcworkspace`, NOT `.xcodeproj` — Flutter uses CocoaPods.)

2. In Xcode:
   - Click **Runner** in the project navigator (top).
   - **Signing & Capabilities** tab.
   - **Team**: pick your Apple Developer team.
   - **Bundle Identifier**: `com.chinghok.goldSignals` (auto-set — change to something unique to you if you want, e.g. `com.yourname.goldsignals`).
   - Xcode automatically generates a provisioning profile and distribution certificate.

3. On https://appstoreconnect.apple.com:
   - **My Apps** → **+** → **New App**.
   - Platform: iOS. Name: `Gold Signals`. Primary language: English. Bundle ID: the same one you set in Xcode. SKU: any string (e.g. `gold-signals-mvp`).
   - Fill in the required metadata (screenshots, description, "not financial advice" disclaimer). App Store screenshots aren't required for TestFlight-only distribution.

**Every release:**

```bash
cd /Users/chinghok/gold-signals/mobile
flutter build ipa --release
```

This produces `build/ios/ipa/gold_signals.ipa`. Then upload to App Store Connect:

```bash
xcrun altool --upload-app -f build/ios/ipa/gold_signals.ipa \
  -t ios --apiKey <API_KEY_ID> --apiIssuer <ISSUER_ID>
```

Or drag `gold_signals.ipa` into Transporter (Mac App Store, free).

After ~10 minutes, TestFlight shows the build. Add yourself as an **internal tester**, install via the TestFlight app on your iPhone.

**IMPORTANT** — Apple review is stricter for signal apps. Before submitting to public review (later, not for TestFlight):
- Add a "Not financial advice" disclaimer to your app store listing.
- Do NOT claim any specific win rate or profit numbers.
- Consider adding a "Sign in / Terms of Service" screen.

---

## Android — Play Store internal testing

**One-time setup — release keystore:**

Android release APKs and app bundles must be signed with a keystore. Never lose this file — you can't publish updates without it.

```bash
cd /Users/chinghok/gold-signals/mobile
keytool -genkey -v \
  -keystore ~/.android/goldsignals-upload.jks \
  -alias upload -keyalg RSA -keysize 2048 -validity 10000
```

Answer the prompts (name, org, city, etc. — any values are fine). It'll ask for a **keystore password** and a **key password** — you can use the same value. **Save these passwords in a password manager NOW.** Losing them = losing publish access to your app on Play Store.

Then create `mobile/android/key.properties` (this file is gitignored via the parent `.gitignore` — verify before committing anything):

```
storePassword=<your keystore password>
keyPassword=<your key password>
keyAlias=upload
storeFile=/Users/chinghok/.android/goldsignals-upload.jks
```

Edit `mobile/android/app/build.gradle.kts` (or `build.gradle`) — find the `android { }` block and add signing configs. Ask me for the exact patch when you get here — the file structure varies slightly between Flutter versions.

**One-time setup — Play Console:**

1. Sign up at https://play.google.com/console — $25 one-time fee.
2. Create new app: `Gold Signals`. Same "not financial advice" disclaimers apply.
3. **Testing → Internal testing → Create new release** → this is your first upload target.

**Every release:**

```bash
cd /Users/chinghok/gold-signals/mobile
flutter build appbundle --release
```

Produces `build/app/outputs/bundle/release/app-release.aab`. Upload it to your Play Console internal testing track. Google's review is ~1 hour for internal tracks (vs 7 days for public).

Install on your Android device via the internal testing opt-in URL (found in Play Console).

---

## Local device install without stores (dev / demo)

**iOS:**
```bash
flutter run --release -d <your-iphone-id>
```
Only works if your iPhone is trusted in Xcode (Window → Devices and Simulators). The build gets installed and left on the device even after `flutter run` exits.

**Android (side-load APK):**
```bash
flutter build apk --release
adb install build/app/outputs/flutter-apk/app-release.apk
```

---

## Verification checklist before each release

- [ ] `mobile/.env` has the production `API_BASE_URL`
- [ ] `pubspec.yaml` `version:` incremented
- [ ] `flutter analyze` clean
- [ ] Manual smoke test: Dashboard shows price, WebSocket dot pulses green, Signals list loads, Market Detail chart renders
- [ ] iOS: build in Xcode with **Release** scheme, install to a physical device, confirm no debug watermarks
- [ ] Android: install the release APK, confirm no crashes on cold start

---

## Cost summary for shipping

| Item | Cost |
|---|---|
| Apple Developer Program | $99/yr (you already have it) |
| Google Play Developer account | $25 one-time |
| TestFlight (internal + external) | Free with Apple Developer |
| Play Store internal testing | Free with Google account |
| App icons / splash design | DIY or ~$50 on Fiverr |
| **Total to ship MVP publicly** | ~$25 (Google) + existing Apple |

---

## Next — Phase 10

Once you can install builds on your device, Phase 10 wires:
- **Firebase Auth** so users log in (needed for cloud sync + push targeting)
- **Firebase Cloud Messaging** so the backend can push notifications when high-confidence signals fire

I'll walk you through creating the Firebase project when we get there.
