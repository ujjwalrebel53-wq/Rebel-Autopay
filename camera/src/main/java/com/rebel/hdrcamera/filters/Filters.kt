package com.rebel.hdrcamera.filters

import android.graphics.ColorMatrix

/**
 * A colour-grading preset. [matrix] == null means "Original" (no grading, HDR pipeline).
 * [swatch] is the accent colour shown in the filter carousel.
 */
data class CameraFilter(
    val name: String,
    val matrix: ColorMatrix?,
    val swatch: Int
)

object Filters {

    private fun saturation(s: Float) = ColorMatrix().apply { setSaturation(s) }

    private fun contrast(c: Float): ColorMatrix {
        val t = (1f - c) * 128f
        return ColorMatrix(
            floatArrayOf(
                c, 0f, 0f, 0f, t,
                0f, c, 0f, 0f, t,
                0f, 0f, c, 0f, t,
                0f, 0f, 0f, 1f, 0f
            )
        )
    }

    private fun tint(r: Float, g: Float, b: Float, rOff: Float = 0f, gOff: Float = 0f, bOff: Float = 0f) =
        ColorMatrix(
            floatArrayOf(
                r, 0f, 0f, 0f, rOff,
                0f, g, 0f, 0f, gOff,
                0f, 0f, b, 0f, bOff,
                0f, 0f, 0f, 1f, 0f
            )
        )

    private fun compose(vararg parts: ColorMatrix): ColorMatrix {
        val out = ColorMatrix()
        for (p in parts) out.postConcat(p)
        return out
    }

    /** Blend a grading matrix toward identity by [t] (1 = full effect). Valid because the op is affine. */
    fun blend(m: ColorMatrix, t: Float): ColorMatrix {
        val a = m.array
        val id = ColorMatrix().array
        val out = FloatArray(20)
        for (i in 0 until 20) out[i] = id[i] * (1f - t) + a[i] * t
        return ColorMatrix(out)
    }

    /** Convert an Android 4x5 ColorMatrix into a GL column-major mat4 + offset vec4 (0..1 range). */
    fun toGl(cm: ColorMatrix): Pair<FloatArray, FloatArray> {
        val m = cm.array
        val mat = FloatArray(16)
        val off = FloatArray(4)
        for (row in 0..3) {
            for (col in 0..3) mat[col * 4 + row] = m[row * 5 + col]
            off[row] = m[row * 5 + 4] / 255f
        }
        return mat to off
    }

    val ALL: List<CameraFilter> = listOf(
        CameraFilter("Original", null, 0xFF9E9E9E.toInt()),
        CameraFilter(
            "Vivid",
            compose(saturation(1.35f), contrast(1.08f)),
            0xFFFF5252.toInt()
        ),
        CameraFilter(
            "Golden",
            compose(tint(1.18f, 1.05f, 0.86f, rOff = 8f), saturation(1.1f)),
            0xFFFFB300.toInt()
        ),
        CameraFilter(
            "Warm",
            compose(tint(1.12f, 1.02f, 0.9f), contrast(1.04f)),
            0xFFFF8A65.toInt()
        ),
        CameraFilter(
            "Cool",
            compose(tint(0.9f, 1.02f, 1.16f), contrast(1.04f)),
            0xFF4FC3F7.toInt()
        ),
        CameraFilter(
            "Film",
            compose(saturation(0.88f), contrast(1.12f), tint(1.06f, 1.0f, 0.94f, bOff = 6f)),
            0xFF8D6E63.toInt()
        ),
        CameraFilter(
            "Fade",
            compose(saturation(0.78f), contrast(0.86f), tint(1f, 1f, 1f, 14f, 14f, 14f)),
            0xFFB0BEC5.toInt()
        ),
        CameraFilter(
            "Vintage",
            ColorMatrix(
                floatArrayOf(
                    0.393f, 0.769f, 0.189f, 0f, 0f,
                    0.349f, 0.686f, 0.168f, 0f, 0f,
                    0.272f, 0.534f, 0.131f, 0f, 0f,
                    0f, 0f, 0f, 1f, 0f
                )
            ),
            0xFFD7A86E.toInt()
        ),
        CameraFilter(
            "Cyber",
            compose(tint(1.14f, 0.9f, 1.22f, bOff = 10f), saturation(1.2f), contrast(1.06f)),
            0xFFE040FB.toInt()
        ),
        CameraFilter(
            "Frost",
            compose(tint(0.95f, 1.04f, 1.18f, rOff = 6f, gOff = 8f, bOff = 12f), saturation(0.9f)),
            0xFF80DEEA.toInt()
        ),
        CameraFilter("Mono", saturation(0f), 0xFFE0E0E0.toInt()),
        CameraFilter(
            "Noir",
            compose(saturation(0f), contrast(1.35f)),
            0xFF616161.toInt()
        )
    )
}
