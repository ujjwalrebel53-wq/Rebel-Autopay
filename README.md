# Rebel Autopay

Android app that handles UPI payment intents and displays a scannable QR code.

## Features

- Registers as a UPI handler (`upi://` deep links)
- Converts incoming UPI payment links into QR codes
- Dark cyber-themed UI with Telegram community links
- Native integrity checks via `libnative-lib.so`

## Build

Requirements:
- JDK 17+
- Android SDK 34
- Android NDK 25.2

```bash
# Create signing keystore (first time only)
keytool -genkeypair -v -keystore skillx-release.keystore -alias skillx \
  -keyalg RSA -keysize 2048 -validity 10000 -storepass skillx123 -keypass skillx123 \
  -dname "CN=SkillX, OU=Dev, O=SkillX, L=India, ST=India, C=IN"

# Build release APK
./gradlew assembleRelease
```

Output APK: `app/build/outputs/apk/release/app-release.apk`

## Usage

1. Install the APK on your Android device.
2. Open any payment app and start a UPI payment.
3. When prompted to choose a UPI app, select **Paytm UPI** (Rebel Autopay).
4. The app will show a QR code for the payment link.

Do not open the app directly from the launcher — it must be launched via a UPI payment intent.

## Original APK Analysis

| Property | Value |
|----------|-------|
| Package | `net.one97.paytm` |
| App Name | Rebel Autopay |
| Version | 1.0 (1) |
| Min SDK | 21 |
| Target SDK | 34 |
| Permissions | CAMERA |

## Telegram

- Community: https://t.me/skillx_community
- Developer: https://t.me/skillx_owner
