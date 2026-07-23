package com.rebel.hdrcamera

import android.Manifest
import android.content.ContentValues
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.provider.MediaStore
import android.util.Size
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraInfo
import androidx.camera.core.CameraSelector
import androidx.camera.core.DynamicRange
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.MediaStoreOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.core.content.ContextCompat
import com.rebel.hdrcamera.databinding.ActivityMainBinding
import java.text.SimpleDateFormat
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private var cameraProvider: ProcessCameraProvider? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var activeRecording: Recording? = null

    private var lensFacing = CameraSelector.LENS_FACING_BACK
    private var audioGranted = false

    private val timerHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private var recordStartMs = 0L
    private val timerRunnable = object : Runnable {
        override fun run() {
            val elapsed = SystemClock.elapsedRealtime() - recordStartMs
            binding.timerText.text = formatDuration(elapsed)
            timerHandler.postDelayed(this, 250)
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        audioGranted = result[Manifest.permission.RECORD_AUDIO] == true
        if (result[Manifest.permission.CAMERA] == true) {
            startCamera()
        } else {
            Toast.makeText(this, R.string.camera_permission_required, Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.recordButton.setOnClickListener { toggleRecording() }
        binding.switchButton.setOnClickListener { switchCamera() }

        if (hasCameraPermission()) {
            audioGranted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
            startCamera()
        } else {
            permissionLauncher.launch(requiredPermissions())
        }
    }

    private fun requiredPermissions(): Array<String> {
        val perms = mutableListOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
            perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
        return perms.toTypedArray()
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(
            this, Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            cameraProvider = future.get()
            bindUseCases()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindUseCases() {
        val provider = cameraProvider ?: return
        provider.unbindAll()

        val cameraSelector = CameraSelector.Builder()
            .requireLensFacing(lensFacing)
            .build()

        val cameraInfo: CameraInfo? =
            cameraSelector.filter(provider.availableCameraInfos).firstOrNull()
        if (cameraInfo == null) {
            Toast.makeText(this, R.string.no_camera, Toast.LENGTH_LONG).show()
            return
        }

        val capabilities = Recorder.getVideoCapabilities(cameraInfo)

        // Prefer the richest 10-bit HDR range the camera supports, else fall back to SDR.
        val dynamicRange = pickBestDynamicRange(capabilities.supportedDynamicRanges)
        val isHdr = dynamicRange != DynamicRange.SDR

        // Highest quality supported for the chosen dynamic range (list is high -> low).
        val supportedQualities = capabilities.getSupportedQualities(dynamicRange)
        val bestQuality = supportedQualities.firstOrNull() ?: Quality.HIGHEST

        val qualitySelector = QualitySelector.from(
            bestQuality,
            FallbackStrategy.higherQualityOrLowerThan(Quality.SD)
        )

        val recorder = Recorder.Builder()
            .setExecutor(ContextCompat.getMainExecutor(this))
            .setQualitySelector(qualitySelector)
            .setAspectRatio(androidx.camera.core.AspectRatio.RATIO_16_9)
            .build()

        val capture = VideoCapture.Builder(recorder)
            .setDynamicRange(dynamicRange)
            .build()
        videoCapture = capture

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        try {
            provider.bindToLifecycle(this, cameraSelector, preview, capture)
        } catch (e: Exception) {
            Toast.makeText(this, getString(R.string.bind_failed, e.message), Toast.LENGTH_LONG).show()
            return
        }

        updateInfoOverlay(cameraInfo, bestQuality, dynamicRange, isHdr)
    }

    private fun pickBestDynamicRange(supported: Set<DynamicRange>): DynamicRange {
        val priority = listOf(
            DynamicRange.HLG_10_BIT,
            DynamicRange.HDR10_10_BIT,
            DynamicRange.HDR10_PLUS_10_BIT,
            DynamicRange.DOLBY_VISION_10_BIT,
            DynamicRange.DOLBY_VISION_8_BIT
        )
        for (dr in priority) {
            if (supported.contains(dr)) return dr
        }
        // Any 10-bit HDR range the device exposes.
        supported.firstOrNull { it.bitDepth == DynamicRange.BIT_DEPTH_10_BIT }?.let { return it }
        return DynamicRange.SDR
    }

    private fun updateInfoOverlay(
        cameraInfo: CameraInfo,
        quality: Quality,
        dynamicRange: DynamicRange,
        isHdr: Boolean
    ) {
        val resolution: Size? = QualitySelector.getResolution(cameraInfo, quality)
        val resText = resolution?.let { "${it.width} x ${it.height}" } ?: qualityName(quality)
        val hdrText = if (isHdr) getString(R.string.hdr_on, dynamicRangeName(dynamicRange))
        else getString(R.string.hdr_off)

        binding.infoText.text = getString(R.string.info_overlay, resText, hdrText)
        binding.hdrBadge.visibility = if (isHdr) android.view.View.VISIBLE else android.view.View.GONE
    }

    private fun toggleRecording() {
        val capture = videoCapture ?: return
        val recording = activeRecording
        if (recording != null) {
            recording.stop()
            activeRecording = null
            return
        }

        val name = "HDR_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(System.currentTimeMillis())
        val contentValues = ContentValues().apply {
            put(MediaStore.Video.Media.DISPLAY_NAME, name)
            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/HDRCamera")
            }
        }
        val outputOptions = MediaStoreOutputOptions.Builder(
            contentResolver,
            MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        ).setContentValues(contentValues).build()

        var pending = capture.output.prepareRecording(this, outputOptions)
        if (audioGranted) {
            pending = pending.withAudioEnabled()
        }

        activeRecording = pending.start(ContextCompat.getMainExecutor(this)) { event ->
            when (event) {
                is VideoRecordEvent.Start -> onRecordingStarted()
                is VideoRecordEvent.Finalize -> onRecordingFinalized(event)
            }
        }
    }

    private fun onRecordingStarted() {
        binding.recordButton.isSelected = true
        binding.switchButton.isEnabled = false
        recordStartMs = SystemClock.elapsedRealtime()
        binding.timerText.visibility = android.view.View.VISIBLE
        timerHandler.post(timerRunnable)
    }

    private fun onRecordingFinalized(event: VideoRecordEvent.Finalize) {
        binding.recordButton.isSelected = false
        binding.switchButton.isEnabled = true
        timerHandler.removeCallbacks(timerRunnable)
        binding.timerText.visibility = android.view.View.GONE
        binding.timerText.text = formatDuration(0)

        if (!event.hasError()) {
            Toast.makeText(this, getString(R.string.saved, event.outputResults.outputUri), Toast.LENGTH_LONG).show()
        } else {
            activeRecording?.close()
            activeRecording = null
            Toast.makeText(this, getString(R.string.record_error, event.error), Toast.LENGTH_LONG).show()
        }
    }

    private fun switchCamera() {
        if (activeRecording != null) return
        lensFacing = if (lensFacing == CameraSelector.LENS_FACING_BACK) {
            CameraSelector.LENS_FACING_FRONT
        } else {
            CameraSelector.LENS_FACING_BACK
        }
        bindUseCases()
    }

    private fun formatDuration(ms: Long): String {
        val totalSeconds = ms / 1000
        val minutes = totalSeconds / 60
        val seconds = totalSeconds % 60
        return String.format(Locale.US, "%02d:%02d", minutes, seconds)
    }

    private fun qualityName(quality: Quality): String = when (quality) {
        Quality.UHD -> "2160p (4K)"
        Quality.FHD -> "1080p"
        Quality.HD -> "720p"
        Quality.SD -> "480p"
        else -> "Highest"
    }

    private fun dynamicRangeName(dr: DynamicRange): String = when (dr) {
        DynamicRange.HLG_10_BIT -> "HLG 10-bit"
        DynamicRange.HDR10_10_BIT -> "HDR10"
        DynamicRange.HDR10_PLUS_10_BIT -> "HDR10+"
        DynamicRange.DOLBY_VISION_10_BIT -> "Dolby Vision 10-bit"
        DynamicRange.DOLBY_VISION_8_BIT -> "Dolby Vision 8-bit"
        else -> "HDR"
    }

    override fun onDestroy() {
        super.onDestroy()
        timerHandler.removeCallbacks(timerRunnable)
        activeRecording?.close()
    }
}
