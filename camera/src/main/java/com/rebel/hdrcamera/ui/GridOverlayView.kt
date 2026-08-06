package com.rebel.hdrcamera.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View

/** Rule-of-thirds 3x3 grid overlay. */
class GridOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(110, 255, 255, 255)
        strokeWidth = 1.5f * resources.displayMetrics.density
        style = Paint.Style.STROKE
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        canvas.drawLine(w / 3f, 0f, w / 3f, h, paint)
        canvas.drawLine(2f * w / 3f, 0f, 2f * w / 3f, h, paint)
        canvas.drawLine(0f, h / 3f, w, h / 3f, paint)
        canvas.drawLine(0f, 2f * h / 3f, w, 2f * h / 3f, paint)
    }
}
