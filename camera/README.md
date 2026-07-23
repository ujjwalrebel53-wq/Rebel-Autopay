# HDR Camera

An Android camera app that records video in **10-bit HDR** at the **maximum quality** the
device's camera supports. Built with Kotlin and CameraX.

## What it does

- Detects the richest dynamic range the camera + encoder support and uses it, in priority
  order: **HLG 10-bit → HDR10 → HDR10+ → Dolby Vision 10-bit → Dolby Vision 8-bit**. If no
  HDR range is available it falls back cleanly to SDR.
- Picks the **highest recording resolution/quality** offered for that dynamic range
  (e.g. 2160p / 4K when available), with a graceful fallback down the quality ladder.
- Records `.mp4` with audio to `Movies/HDRCamera` via MediaStore (scoped storage friendly).
- Front/back camera switch, live recording timer, and an on-screen overlay showing the
  active resolution and HDR mode.

Because HDR support and available resolutions differ per device, the app queries the camera
at runtime (`Recorder.getVideoCapabilities`) and adapts — it always uses the best the
hardware can actually deliver rather than a hard-coded profile.

## Tech

- CameraX `1.4.1` (`camera-video`, `camera-view`, `camera-lifecycle`, `camera-camera2`)
- `DynamicRange.HLG_10_BIT` and friends for HDR video capture
- `QualitySelector` with `FallbackStrategy` for max-quality selection
- Kotlin, ViewBinding, Material 3 dark theme

## Build

Requires JDK 17, Android SDK 34, build-tools 34.0.0.

```bash
# Debug APK (installable, debug-signed)
./gradlew :camera:assembleDebug
# -> camera/build/outputs/apk/debug/camera-debug.apk

# Release APK (signed with camera-release.keystore)
./gradlew :camera:assembleRelease
# -> camera/build/outputs/apk/release/camera-release.apk
```

The release signing keystore is created locally and is **not** committed. To recreate it:

```bash
keytool -genkeypair -v -keystore camera-release.keystore -alias hdrcamera \
  -keyalg RSA -keysize 2048 -validity 10000 -storepass hdrcam123 -keypass hdrcam123 \
  -dname "CN=HDR Camera, OU=Dev, O=HDR Camera, L=India, ST=India, C=IN"
```

## Notes

- **HDR playback:** HDR clips look correct on HDR-capable screens; on SDR screens the
  system tone-maps them. This is expected HDR behaviour, not a bug.
- **Min SDK 24.** True 10-bit HDR recording additionally requires a device whose camera +
  media encoder advertise an HDR dynamic range; on devices without it the app records SDR at
  the highest supported resolution.
