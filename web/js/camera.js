import { addMoment, formatTime } from "./storage.js";

export class CameraTracker {
  constructor(options) {
    this.video = options.video;
    this.motionCanvas = options.motionCanvas;
    this.captureCanvas = options.captureCanvas;
    this.overlay = options.overlay;
    this.badge = options.badge;
    this.badgeText = options.badgeText;
    this.onStatus = options.onStatus || (() => {});
    this.onMoment = options.onMoment || (() => {});
    this.getMetadata = options.getMetadata || (() => ({}));

    this.stream = null;
    this.facingMode = "environment";
    this.motionEnabled = true;
    this.sensitivity = 25;
    this.cooldownSec = 3;
    this.lastCapture = 0;
    this.motionTimer = null;
    this.prevFrame = null;
    this.running = false;
  }

  setMotionEnabled(enabled) {
    this.motionEnabled = enabled;
  }

  setSensitivity(value) {
    this.sensitivity = Number(value);
  }

  setCooldown(seconds) {
    this.cooldownSec = Number(seconds);
  }

  async start() {
    if (this.stream) return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: this.facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      this.video.srcObject = this.stream;
      await this.video.play();
      this.badge.hidden = false;
      this.badgeText.textContent = "LIVE";
      this.running = true;
      this.onStatus("Camera active — motion tracking ready.");
      this._startMotionLoop();
    } catch (err) {
      this.onStatus(`Camera error: ${err.message}. HTTPS ya localhost par chalao.`, true);
      throw err;
    }
  }

  stop() {
    this.running = false;
    if (this.motionTimer) {
      cancelAnimationFrame(this.motionTimer);
      this.motionTimer = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    this.video.srcObject = null;
    this.badge.hidden = true;
    this.overlay.classList.remove("motion");
    this.onStatus("Camera stopped.");
  }

  async switchCamera() {
    this.facingMode = this.facingMode === "environment" ? "user" : "environment";
    this.stop();
    await this.start();
  }

  captureMoment(trigger = "manual") {
    if (!this.stream || !this.video.videoWidth) return null;

    const canvas = this.captureCanvas;
    canvas.width = this.video.videoWidth;
    canvas.height = this.video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(this.video, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.82);
    const meta = this.getMetadata();
    const moment = {
      id: crypto.randomUUID(),
      trigger,
      capturedAt: new Date().toISOString(),
      image: dataUrl,
      ...meta,
    };

    addMoment(moment);
    this.onMoment(moment);
    this.lastCapture = Date.now();
    this.onStatus(`Moment captured (${trigger}) at ${formatTime(moment.capturedAt)}`);
    return moment;
  }

  _startMotionLoop() {
    const ctx = this.motionCanvas.getContext("2d", { willReadFrequently: true });

    const tick = () => {
      if (!this.running) return;

      if (this.motionEnabled && this.video.readyState === 4) {
        const w = 160;
        const h = Math.round((this.video.videoHeight / this.video.videoWidth) * w) || 90;
        this.motionCanvas.width = w;
        this.motionCanvas.height = h;
        ctx.drawImage(this.video, 0, 0, w, h);
        const frame = ctx.getImageData(0, 0, w, h).data;
        const score = this._diffScore(frame, this.prevFrame);
        this.prevFrame = frame;

        if (score > this.sensitivity) {
          this.overlay.classList.add("motion");
          const elapsed = (Date.now() - this.lastCapture) / 1000;
          if (elapsed >= this.cooldownSec) {
            this.captureMoment("motion");
            this.badgeText.textContent = "MOTION";
            setTimeout(() => {
              if (this.badgeText) this.badgeText.textContent = "LIVE";
            }, 800);
          }
        } else {
          this.overlay.classList.remove("motion");
        }
      }

      this.motionTimer = requestAnimationFrame(tick);
    };

    this.motionTimer = requestAnimationFrame(tick);
  }

  _diffScore(frame, prev) {
    if (!prev || frame.length !== prev.length) return 0;
    let diff = 0;
    const step = 4 * 8;
    for (let i = 0; i < frame.length; i += step) {
      diff += Math.abs(frame[i] - prev[i]);
      diff += Math.abs(frame[i + 1] - prev[i + 1]);
      diff += Math.abs(frame[i + 2] - prev[i + 2]);
    }
    return diff / (frame.length / step);
  }
}
