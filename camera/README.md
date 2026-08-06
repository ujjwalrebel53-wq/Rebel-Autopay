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

## Snapchat-style advanced features (v2.0)

- **12 colour-grading filters** (Vivid, Golden, Warm, Cool, Film, Fade, Vintage, Cyber,
  Frost, Mono, Noir) rendered in real time by a custom OpenGL shader pipeline
  (`CameraEffect` + `SurfaceProcessor`), so the grade is **baked into the recorded video
  and photos**, not just the preview. Adjustable filter intensity slider.
- **Tap = photo, hold = video** capture button (Snapchat-style). Photos are captured at the
  sensor's maximum resolution (`CAPTURE_MODE_MAXIMIZE_QUALITY`) with the filter applied at
  full resolution.
- **Pinch to zoom** with live zoom-ratio display, **tap to focus** with focus ring,
  **exposure compensation (EV) slider**, **torch/flash toggle**, **rule-of-thirds grid**,
  and a **3s/10s countdown timer**.
- Live filter switching *while recording* (between graded filters) with zero glitches —
  it is just a shader uniform update.
- "Original" filter = full **10-bit HDR** pipeline; graded filters run the maximum-quality
  SDR pipeline (10-bit HDR and GL effects cannot be combined by CameraX).

## DSLR-grade quality (v3.0)

- **PRO computational-photography modes** via CameraX **Camera Extensions**: **HDR+**,
  **Night**, **Portrait (Bokeh / shallow depth-of-field)**, **Face Retouch**, and **Auto**.
  These use the device vendor's tuned multi-frame processing — the same engines behind the
  phone's stock "Pro"/"Portrait" camera — giving that DSLR look (clean shadows, natural
  bokeh, low-light detail). The `PRO` button cycles only the modes the current lens actually
  supports and hides itself when none are available.
- **Max-resolution stills**: photos captured at the sensor's highest resolution with
  `CAPTURE_MODE_MAXIMIZE_QUALITY` and JPEG quality 100; overlay shows the live megapixel count.
- **DSLR-grade video bitrate**: the encoder is asked for a very high target bitrate scaled to
  resolution (~100 Mbps at 4K, ~32 Mbps at 1080p) so footage stays crisp with minimal
  compression artefacts (the encoder clamps to its own maximum).
- PRO modes are photo-oriented (Camera Extensions don't support video capture), so while a
  PRO mode is active the capture button takes photos; picking a colour filter or tapping PRO
  again returns to the HDR video pipeline.

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
