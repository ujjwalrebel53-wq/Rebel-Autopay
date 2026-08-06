package com.rebel.hdrcamera.gl

import android.util.Log
import androidx.camera.core.CameraEffect
import androidx.core.util.Consumer

/** Applies [GlFilterProcessor] to both the preview and the recorded video stream. */
class ColorGradeEffect(processor: GlFilterProcessor) : CameraEffect(
    PREVIEW or VIDEO_CAPTURE,
    processor.glExecutor,
    processor,
    Consumer { t -> Log.e("ColorGradeEffect", "Effect error", t) }
)
