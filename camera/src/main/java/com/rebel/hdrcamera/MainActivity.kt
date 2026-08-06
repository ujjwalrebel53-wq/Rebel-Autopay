package com.rebel.hdrcamera

import android.Manifest
import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.ColorMatrixColorFilter
import android.graphics.Matrix
import android.graphics.Paint
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.MediaStore
import android.util.Size
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.Camera
import androidx.camera.core.CameraInfo
import androidx.camera.core.CameraSelector
import androidx.camera.core.DynamicRange
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.UseCaseGroup
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.extensions.ExtensionMode
import androidx.camera.extensions.ExtensionsManager
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
import androidx.recyclerview.widget.LinearLayoutManager
import com.rebel.hdrcamera.databinding.ActivityMainBinding
import com.rebel.hdrcamera.filters.CameraFilter
import com.rebel.hdrcamera.filters.Filters
import com.rebel.hdrcamera.gl.ColorGradeEffect
import com.rebel.hdrcamera.gl.GlFilterProcessor
import com.rebel.hdrcamera.ui.FilterAdapter
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private var cameraProvider: ProcessCameraProvider? = null
    private var extensionsManager: ExtensionsManager? = null
    private var camera: Camera? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var imageCapture: ImageCapture? = null
    private var activeRecording: Recording? = null

    private var lensFacing = CameraSelector.LENS_FACING_BACK
    private var audioGranted = false
    private var torchOn = false
    private var timerSeconds = 0
    private var filterIntensity = 1f
    private var countdownActive = false

    /** Active Camera-Extension (computational photography) mode; NONE = standard pipeline. */
    private var proMode = ExtensionMode.NONE
    private val proModeCandidates = listOf(
        ExtensionMode.NONE,
        ExtensionMode.AUTO,
        ExtensionMode.HDR,
        ExtensionMode.NIGHT,
        ExtensionMode.BOKEH,
        ExtensionMode.FACE_RETOUCH
    )

    private val glProcessor = GlFilterProcessor()
    private val colorEffect = ColorGradeEffect(glProcessor)
    private lateinit var filterAdapter: FilterAdapter
    private val bgExecutor = Executors.newSingleThreadExecutor()

    private val mainHandler = Handler(Looper.getMainLooper())
    private var recordStartMs = 0L
    private val recordTimerRunnable = object : Runnable {
        override fun run() {
            val elapsed = SystemClock.elapsedRealtime() - recordStartMs
            binding.timerText.text = formatDuration(elapsed)
            mainHandler.postDelayed(this, 250)
        }
    }
    private val hideZoomRunnable = Runnable { binding.zoomText.visibility = View.GONE }

    private var longPressTriggered = false
    private val longPressRunnable = Runnable {
        longPressTriggered = true
        startRecording()
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
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        setUpFilterCarousel()
        setUpCaptureButton()
        setUpControls()
        setUpPreviewGestures()

        if (hasCameraPermission()) {
            audioGranted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
            startCamera()
        } else {
            permissionLauncher.launch(requiredPermissions())
        }
    }

    // ---------------------------------------------------------------- setup

    private fun setUpFilterCarousel() {
        filterAdapter = FilterAdapter(Filters.ALL) { index -> onFilterSelected(index) }
        binding.filterRecycler.layoutManager =
            LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false)
        binding.filterRecycler.adapter = filterAdapter
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setUpCaptureButton() {
        binding.captureButton.setOnTouchListener { _, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    // Hold-to-record only when a video pipeline is active (not in PRO photo mode).
                    if (activeRecording == null && !countdownActive && videoCapture != null) {
                        longPressTriggered = false
                        mainHandler.postDelayed(longPressRunnable, 350)
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    mainHandler.removeCallbacks(longPressRunnable)
                    when {
                        activeRecording != null -> stopRecording()
                        !longPressTriggered && event.actionMasked == MotionEvent.ACTION_UP &&
                            !countdownActive -> requestPhoto()
                    }
                    true
                }
                else -> false
            }
        }
    }

    private fun setUpControls() {
        binding.switchButton.setOnClickListener { switchCamera() }

        binding.proButton.setOnClickListener { cyclePro() }

        binding.flashButton.setOnClickListener {
            torchOn = !torchOn
            camera?.cameraControl?.enableTorch(torchOn)
            binding.flashButton.setImageResource(
                if (torchOn) R.drawable.ic_flash_on else R.drawable.ic_flash_off
            )
        }

        binding.gridButton.setOnClickListener {
            val show = binding.gridOverlay.visibility != View.VISIBLE
            binding.gridOverlay.visibility = if (show) View.VISIBLE else View.GONE
            binding.gridButton.alpha = if (show) 1f else 0.6f
        }

        binding.timerButton.setOnClickListener {
            timerSeconds = when (timerSeconds) {
                0 -> 3
                3 -> 10
                else -> 0
            }
            binding.timerLabel.visibility = if (timerSeconds > 0) View.VISIBLE else View.GONE
            binding.timerLabel.text = "${timerSeconds}s"
            binding.timerButton.alpha = if (timerSeconds > 0) 1f else 0.6f
        }

        binding.evButton.setOnClickListener {
            binding.evSlider.visibility =
                if (binding.evSlider.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }

        binding.evSlider.addOnChangeListener { _, value, fromUser ->
            if (fromUser) camera?.cameraControl?.setExposureCompensationIndex(value.toInt())
        }

        binding.intensitySlider.addOnChangeListener { _, value, fromUser ->
            if (fromUser) {
                filterIntensity = value
                currentFilter().matrix?.let { glProcessor.setFilter(it, filterIntensity) }
            }
        }

        binding.gridButton.alpha = 0.6f
        binding.timerButton.alpha = 0.6f
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setUpPreviewGestures() {
        val scaleDetector = ScaleGestureDetector(
            this,
            object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
                override fun onScale(detector: ScaleGestureDetector): Boolean {
                    val cam = camera ?: return false
                    val state = cam.cameraInfo.zoomState.value ?: return false
                    val ratio = (state.zoomRatio * detector.scaleFactor)
                        .coerceIn(state.minZoomRatio, state.maxZoomRatio)
                    cam.cameraControl.setZoomRatio(ratio)
                    binding.zoomText.text = String.format(Locale.US, getString(R.string.zoom_format), ratio)
                    binding.zoomText.visibility = View.VISIBLE
                    mainHandler.removeCallbacks(hideZoomRunnable)
                    mainHandler.postDelayed(hideZoomRunnable, 1200)
                    return true
                }
            }
        )
        val tapDetector = GestureDetector(
            this,
            object : GestureDetector.SimpleOnGestureListener() {
                override fun onSingleTapUp(e: MotionEvent): Boolean {
                    focusAt(e.x, e.y)
                    return true
                }
            }
        )
        binding.previewView.setOnTouchListener { _, event ->
            scaleDetector.onTouchEvent(event)
            tapDetector.onTouchEvent(event)
            true
        }
    }

    // ---------------------------------------------------------------- camera

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
            val provider = future.get()
            cameraProvider = provider
            val extFuture = ExtensionsManager.getInstanceAsync(this, provider)
            extFuture.addListener({
                extensionsManager = try {
                    extFuture.get()
                } catch (e: Exception) {
                    null
                }
                bindUseCases()
            }, ContextCompat.getMainExecutor(this))
        }, ContextCompat.getMainExecutor(this))
    }

    private fun availableProModes(baseSelector: CameraSelector): List<Int> {
        val mgr = extensionsManager ?: return listOf(ExtensionMode.NONE)
        return proModeCandidates.filter {
            it == ExtensionMode.NONE || mgr.isExtensionAvailable(baseSelector, it)
        }
    }

    private fun cyclePro() {
        if (activeRecording != null) {
            Toast.makeText(this, R.string.pro_locked_recording, Toast.LENGTH_SHORT).show()
            return
        }
        val baseSelector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
        val modes = availableProModes(baseSelector)
        val currentIdx = modes.indexOf(proMode).coerceAtLeast(0)
        proMode = modes[(currentIdx + 1) % modes.size]
        bindUseCases()
    }

    private fun proModeName(mode: Int): String = when (mode) {
        ExtensionMode.AUTO -> getString(R.string.mode_auto)
        ExtensionMode.HDR -> getString(R.string.mode_hdr)
        ExtensionMode.NIGHT -> getString(R.string.mode_night)
        ExtensionMode.BOKEH -> getString(R.string.mode_portrait)
        ExtensionMode.FACE_RETOUCH -> getString(R.string.mode_retouch)
        else -> ""
    }

    private fun currentFilter(): CameraFilter = Filters.ALL[filterAdapter.selectedIndex]

    private fun newImageCapture(): ImageCapture =
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
            .setJpegQuality(100)
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionStrategy(ResolutionStrategy.HIGHEST_AVAILABLE_STRATEGY)
                    .build()
            )
            .build()

    private fun bindUseCases() {
        val provider = cameraProvider ?: return

        val baseSelector = CameraSelector.Builder()
            .requireLensFacing(lensFacing)
            .build()

        val cameraInfo: CameraInfo? =
            baseSelector.filter(provider.availableCameraInfos).firstOrNull()
        if (cameraInfo == null) {
            Toast.makeText(this, R.string.no_camera, Toast.LENGTH_LONG).show()
            return
        }

        // The selected PRO extension may not exist on this lens (e.g. no front Bokeh).
        if (proMode != ExtensionMode.NONE && proMode !in availableProModes(baseSelector)) {
            proMode = ExtensionMode.NONE
        }

        if (proMode != ExtensionMode.NONE) {
            bindProMode(provider, baseSelector, cameraInfo)
        } else {
            bindStandard(provider, baseSelector, cameraInfo)
        }
        refreshProButton(baseSelector)
    }

    /** DSLR-grade computational-photography pipeline (Camera Extensions): preview + max-res photo. */
    private fun bindProMode(
        provider: ProcessCameraProvider,
        baseSelector: CameraSelector,
        cameraInfo: CameraInfo
    ) {
        val mgr = extensionsManager
        if (mgr == null) {
            proMode = ExtensionMode.NONE
            bindStandard(provider, baseSelector, cameraInfo)
            return
        }
        provider.unbindAll()
        camera = null
        videoCapture = null
        glProcessor.setFilter(null, 0f)

        val extSelector = mgr.getExtensionEnabledCameraSelector(baseSelector, proMode)
        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }
        val photo = newImageCapture()

        try {
            camera = provider.bindToLifecycle(this, extSelector, preview, photo)
            imageCapture = photo
        } catch (e: Exception) {
            proMode = ExtensionMode.NONE
            bindStandard(provider, baseSelector, cameraInfo)
            return
        }

        camera?.let { cam ->
            if (torchOn) cam.cameraControl.enableTorch(true)
            configureEvSlider(cam)
        }
        binding.intensitySlider.visibility = View.GONE
        binding.captureHint.text = getString(R.string.pro_hint_photo, proModeName(proMode))
        binding.infoText.text = getString(
            R.string.info_overlay,
            photoResText(photo),
            proModeName(proMode)
        )
        binding.hdrBadge.visibility = View.GONE
    }

    private fun bindStandard(
        provider: ProcessCameraProvider,
        cameraSelector: CameraSelector,
        cameraInfo: CameraInfo
    ) {
        provider.unbindAll()
        camera = null

        val capabilities = Recorder.getVideoCapabilities(cameraInfo)
        val filter = currentFilter()
        val filterActive = filter.matrix != null

        // Real-time GL colour grading runs in SDR; "Original" uses the full 10-bit HDR pipeline.
        val bestHdr = pickBestDynamicRange(capabilities.supportedDynamicRanges)
        val dynamicRange = if (filterActive) DynamicRange.SDR else bestHdr
        val isHdr = dynamicRange != DynamicRange.SDR

        val supportedQualities = capabilities.getSupportedQualities(dynamicRange)
        val bestQuality = supportedQualities.firstOrNull() ?: Quality.HIGHEST

        val recorder = Recorder.Builder()
            .setExecutor(ContextCompat.getMainExecutor(this))
            .setQualitySelector(
                QualitySelector.from(bestQuality, FallbackStrategy.higherQualityOrLowerThan(Quality.SD))
            )
            // DSLR-grade footage: request a very high encoder bitrate (encoder clamps to its max).
            .setTargetVideoEncodingBitRate(targetBitRate(bestQuality))
            .build()

        val capture = VideoCapture.Builder(recorder)
            .setDynamicRange(dynamicRange)
            .build()
        videoCapture = capture

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        val photo = newImageCapture()

        if (filterActive) {
            glProcessor.setFilter(filter.matrix, filterIntensity)
        } else {
            glProcessor.setFilter(null, 0f)
        }

        fun buildGroup(withPhoto: Boolean): UseCaseGroup {
            val builder = UseCaseGroup.Builder()
                .addUseCase(preview)
                .addUseCase(capture)
            if (withPhoto) builder.addUseCase(photo)
            if (filterActive) builder.addEffect(colorEffect)
            return builder.build()
        }

        val boundCamera: Camera
        try {
            boundCamera = provider.bindToLifecycle(this, cameraSelector, buildGroup(true))
            imageCapture = photo
        } catch (e: Exception) {
            // Some devices can't combine max-res photo + 4K video; retry video-only.
            provider.unbindAll()
            try {
                camera = provider.bindToLifecycle(this, cameraSelector, buildGroup(false))
                imageCapture = null
            } catch (e2: Exception) {
                Toast.makeText(this, getString(R.string.bind_failed, e2.message), Toast.LENGTH_LONG).show()
                return
            }
            camera?.let { cam ->
                if (torchOn) cam.cameraControl.enableTorch(true)
                configureEvSlider(cam)
            }
            binding.captureHint.text = getString(R.string.capture_hint)
            updateInfoOverlay(cameraInfo, bestQuality, dynamicRange, isHdr, filter)
            return
        }
        camera = boundCamera
        if (torchOn) boundCamera.cameraControl.enableTorch(true)
        configureEvSlider(boundCamera)

        binding.captureHint.text = getString(R.string.capture_hint)
        binding.intensitySlider.visibility = if (filterActive) View.VISIBLE else View.GONE
        updateInfoOverlay(cameraInfo, bestQuality, dynamicRange, isHdr, filter)
    }

    private fun refreshProButton(baseSelector: CameraSelector) {
        val hasExtensions = availableProModes(baseSelector).size > 1
        binding.proButton.visibility = if (hasExtensions) View.VISIBLE else View.GONE
        if (proMode == ExtensionMode.NONE) {
            binding.proButton.alpha = 0.6f
            binding.proLabel.visibility = View.GONE
        } else {
            binding.proButton.alpha = 1f
            binding.proLabel.visibility = View.VISIBLE
            binding.proLabel.text = proModeName(proMode)
        }
    }

    private fun photoResText(photo: ImageCapture): String {
        val res = photo.resolutionInfo?.resolution ?: return getString(R.string.mode_hdr)
        val mp = (res.width.toLong() * res.height) / 1_000_000.0
        return String.format(Locale.US, "%dx%d (%.0fMP)", res.width, res.height, mp)
    }

    private fun targetBitRate(quality: Quality): Int = when (quality) {
        Quality.UHD -> 100_000_000
        Quality.FHD -> 32_000_000
        Quality.HD -> 16_000_000
        Quality.SD -> 6_000_000
        else -> 60_000_000
    }

    private fun configureEvSlider(cam: Camera) {
        val es = cam.cameraInfo.exposureState
        if (!es.isExposureCompensationSupported) {
            binding.evButton.visibility = View.GONE
            binding.evSlider.visibility = View.GONE
            return
        }
        binding.evButton.visibility = View.VISIBLE
        val range = es.exposureCompensationRange
        binding.evSlider.valueFrom = range.lower.toFloat()
        binding.evSlider.valueTo = range.upper.toFloat()
        binding.evSlider.stepSize = 1f
        binding.evSlider.value = es.exposureCompensationIndex.toFloat()
            .coerceIn(range.lower.toFloat(), range.upper.toFloat())
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
        supported.firstOrNull { it.bitDepth == DynamicRange.BIT_DEPTH_10_BIT }?.let { return it }
        return DynamicRange.SDR
    }

    private fun updateInfoOverlay(
        cameraInfo: CameraInfo,
        quality: Quality,
        dynamicRange: DynamicRange,
        isHdr: Boolean,
        filter: CameraFilter
    ) {
        val resolution: Size? = QualitySelector.getResolution(cameraInfo, quality)
        val resText = resolution?.let { "${it.width}x${it.height}" } ?: qualityName(quality)
        val modeText = when {
            isHdr -> getString(R.string.hdr_on, dynamicRangeName(dynamicRange))
            filter.matrix != null -> getString(R.string.filter_mode, filter.name)
            else -> getString(R.string.hdr_off)
        }
        binding.infoText.text = getString(R.string.info_overlay, resText, modeText)
        binding.hdrBadge.visibility = if (isHdr) View.VISIBLE else View.GONE
    }

    // ---------------------------------------------------------------- filters

    private fun onFilterSelected(index: Int) {
        // Choosing a filter leaves PRO (extensions) mode and returns to the video pipeline.
        val leavingPro = proMode != ExtensionMode.NONE
        if (index == filterAdapter.selectedIndex && !leavingPro) return
        val oldOriginal = filterAdapter.selectedIndex == 0
        val newOriginal = index == 0

        // Original <-> filter needs a pipeline rebind (HDR vs GL effect); block while recording.
        if (activeRecording != null && oldOriginal != newOriginal) {
            Toast.makeText(this, R.string.filter_locked_recording, Toast.LENGTH_SHORT).show()
            return
        }

        filterAdapter.select(index)
        val filter = currentFilter()
        binding.intensitySlider.visibility = if (filter.matrix != null) View.VISIBLE else View.GONE

        if (leavingPro) {
            proMode = ExtensionMode.NONE
            bindUseCases()
        } else if (oldOriginal != newOriginal) {
            bindUseCases()
        } else {
            filter.matrix?.let { glProcessor.setFilter(it, filterIntensity) }
            val provider = cameraProvider
            val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
            val info = provider?.let { selector.filter(it.availableCameraInfos).firstOrNull() }
            if (info != null) {
                val caps = Recorder.getVideoCapabilities(info)
                val quality = caps.getSupportedQualities(DynamicRange.SDR).firstOrNull() ?: Quality.HIGHEST
                updateInfoOverlay(info, quality, DynamicRange.SDR, false, filter)
            }
        }
    }

    // ---------------------------------------------------------------- photo

    private fun requestPhoto() {
        if (imageCapture == null) return
        if (timerSeconds > 0) {
            countdown(timerSeconds) { capturePhoto() }
        } else {
            capturePhoto()
        }
    }

    private fun countdown(seconds: Int, onDone: () -> Unit) {
        countdownActive = true
        binding.countdownText.visibility = View.VISIBLE
        var remaining = seconds
        val tick = object : Runnable {
            override fun run() {
                if (remaining > 0) {
                    binding.countdownText.text = remaining.toString()
                    remaining--
                    mainHandler.postDelayed(this, 1000)
                } else {
                    binding.countdownText.visibility = View.GONE
                    countdownActive = false
                    onDone()
                }
            }
        }
        tick.run()
    }

    private fun capturePhoto() {
        val ic = imageCapture ?: return
        val filter = currentFilter()
        val name = "HDR_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
            .format(System.currentTimeMillis())

        if (filter.matrix == null) {
            val contentValues = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/HDRCamera")
                }
            }
            val options = ImageCapture.OutputFileOptions.Builder(
                contentResolver, MediaStore.Images.Media.EXTERNAL_CONTENT_URI, contentValues
            ).build()
            ic.takePicture(
                options,
                ContextCompat.getMainExecutor(this),
                object : ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(results: ImageCapture.OutputFileResults) {
                        Toast.makeText(this@MainActivity, R.string.photo_saved, Toast.LENGTH_SHORT).show()
                    }

                    override fun onError(exception: ImageCaptureException) {
                        Toast.makeText(
                            this@MainActivity,
                            getString(R.string.photo_error, exception.message),
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            )
        } else {
            ic.takePicture(
                ContextCompat.getMainExecutor(this),
                object : ImageCapture.OnImageCapturedCallback() {
                    override fun onCaptureSuccess(image: ImageProxy) {
                        bgExecutor.execute { processAndSavePhoto(image, name) }
                    }

                    override fun onError(exception: ImageCaptureException) {
                        Toast.makeText(
                            this@MainActivity,
                            getString(R.string.photo_error, exception.message),
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            )
        }
    }

    /** Bakes the active colour grade into the full-resolution JPEG. */
    private fun processAndSavePhoto(image: ImageProxy, name: String) {
        try {
            val buffer = image.planes[0].buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            val rotation = image.imageInfo.rotationDegrees
            image.close()

            var bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            if (rotation != 0) {
                val m = Matrix().apply { postRotate(rotation.toFloat()) }
                val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, m, true)
                if (rotated != bitmap) bitmap.recycle()
                bitmap = rotated
            }

            val matrix = currentFilter().matrix
            val graded: Bitmap
            if (matrix != null) {
                graded = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
                val canvas = Canvas(graded)
                val paint = Paint(Paint.FILTER_BITMAP_FLAG).apply {
                    colorFilter = ColorMatrixColorFilter(Filters.blend(matrix, filterIntensity))
                }
                canvas.drawBitmap(bitmap, 0f, 0f, paint)
                bitmap.recycle()
            } else {
                graded = bitmap
            }

            val contentValues = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/HDRCamera")
                }
            }
            val uri = contentResolver.insert(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI, contentValues
            ) ?: throw IllegalStateException("MediaStore insert failed")
            contentResolver.openOutputStream(uri)?.use { out ->
                graded.compress(Bitmap.CompressFormat.JPEG, 97, out)
            }
            graded.recycle()

            runOnUiThread {
                Toast.makeText(this, R.string.photo_saved, Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            runOnUiThread {
                Toast.makeText(this, getString(R.string.photo_error, e.message), Toast.LENGTH_LONG).show()
            }
        }
    }

    // ---------------------------------------------------------------- video

    private fun startRecording() {
        val capture = videoCapture ?: return
        if (activeRecording != null) return

        val name = "HDR_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
            .format(System.currentTimeMillis())
        val contentValues = ContentValues().apply {
            put(MediaStore.Video.Media.DISPLAY_NAME, name)
            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/HDRCamera")
            }
        }
        val outputOptions = MediaStoreOutputOptions.Builder(
            contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        ).setContentValues(contentValues).build()

        var pending = capture.output.prepareRecording(this, outputOptions)
        if (audioGranted) pending = pending.withAudioEnabled()

        activeRecording = pending.start(ContextCompat.getMainExecutor(this)) { event ->
            when (event) {
                is VideoRecordEvent.Start -> onRecordingStarted()
                is VideoRecordEvent.Finalize -> onRecordingFinalized(event)
            }
        }
    }

    private fun stopRecording() {
        activeRecording?.stop()
        activeRecording = null
    }

    private fun onRecordingStarted() {
        binding.captureButton.isSelected = true
        binding.switchButton.isEnabled = false
        binding.captureHint.visibility = View.INVISIBLE
        recordStartMs = SystemClock.elapsedRealtime()
        binding.timerText.visibility = View.VISIBLE
        mainHandler.post(recordTimerRunnable)
    }

    private fun onRecordingFinalized(event: VideoRecordEvent.Finalize) {
        binding.captureButton.isSelected = false
        binding.switchButton.isEnabled = true
        binding.captureHint.visibility = View.VISIBLE
        mainHandler.removeCallbacks(recordTimerRunnable)
        binding.timerText.visibility = View.GONE
        binding.timerText.text = formatDuration(0)

        if (!event.hasError()) {
            Toast.makeText(
                this, getString(R.string.saved, event.outputResults.outputUri), Toast.LENGTH_LONG
            ).show()
        } else {
            activeRecording?.close()
            activeRecording = null
            Toast.makeText(
                this, getString(R.string.record_error, event.error), Toast.LENGTH_LONG
            ).show()
        }
    }

    // ---------------------------------------------------------------- misc

    private fun focusAt(x: Float, y: Float) {
        val cam = camera ?: return
        val point = binding.previewView.meteringPointFactory.createPoint(x, y)
        val action = FocusMeteringAction.Builder(
            point, FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
        ).setAutoCancelDuration(3, TimeUnit.SECONDS).build()
        cam.cameraControl.startFocusAndMetering(action)

        binding.focusRing.apply {
            translationX = x - width / 2f
            translationY = y - height / 2f
            visibility = View.VISIBLE
            alpha = 1f
            scaleX = 1.3f
            scaleY = 1.3f
            animate().scaleX(1f).scaleY(1f).setDuration(150).withEndAction {
                animate().alpha(0f).setStartDelay(500).setDuration(250).withEndAction {
                    visibility = View.GONE
                }.start()
            }.start()
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
        mainHandler.removeCallbacksAndMessages(null)
        activeRecording?.close()
        glProcessor.release()
        bgExecutor.shutdown()
    }
}
