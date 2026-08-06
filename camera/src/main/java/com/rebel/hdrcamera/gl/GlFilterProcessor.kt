package com.rebel.hdrcamera.gl

import android.graphics.ColorMatrix
import android.graphics.SurfaceTexture
import android.opengl.EGL14
import android.opengl.EGLConfig
import android.opengl.EGLSurface
import android.opengl.EGLExt
import android.opengl.GLES11Ext
import android.opengl.GLES20
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.view.Surface
import androidx.camera.core.SurfaceOutput
import androidx.camera.core.SurfaceProcessor
import androidx.camera.core.SurfaceRequest
import com.rebel.hdrcamera.filters.Filters
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.util.concurrent.Executor

/**
 * A [SurfaceProcessor] that copies camera frames to the preview / video outputs through an
 * OpenGL shader that applies a 4x5 colour matrix. This bakes the selected colour grade into
 * the recorded video, not just the on-screen preview.
 */
class GlFilterProcessor : SurfaceProcessor {

    private val thread = HandlerThread("gl-filter").apply { start() }
    private val handler = Handler(thread.looper)
    val glExecutor: Executor = Executor { handler.post(it) }

    private var eglDisplay = EGL14.EGL_NO_DISPLAY
    private var eglContext = EGL14.EGL_NO_CONTEXT
    private var eglConfig: EGLConfig? = null
    private var stubSurface: EGLSurface = EGL14.EGL_NO_SURFACE

    private var program = 0
    private var posLoc = 0
    private var tcLoc = 0
    private var texMatrixLoc = 0
    private var colorMatrixLoc = 0
    private var colorOffsetLoc = 0
    private var intensityLoc = 0

    private lateinit var vertexBuf: FloatBuffer
    private lateinit var texBuf: FloatBuffer

    private var oesTexId = 0
    private var surfaceTexture: SurfaceTexture? = null

    private val outputs = LinkedHashMap<SurfaceOutput, EGLSurface>()
    private val texTransform = FloatArray(16)
    private val outTransform = FloatArray(16)

    private var glMatrix = FloatArray(16).also { android.opengl.Matrix.setIdentityM(it, 0) }
    private var glOffset = FloatArray(4)
    private var intensity = 1f

    private var initialized = false
    @Volatile private var released = false

    /** Update the active colour grade. Safe to call from any thread; cheap (no rebinding). */
    fun setFilter(matrix: ColorMatrix?, strength: Float) {
        handler.post {
            if (matrix == null) {
                android.opengl.Matrix.setIdentityM(glMatrix, 0)
                glOffset = FloatArray(4)
                intensity = 0f
            } else {
                val (m, o) = Filters.toGl(matrix)
                glMatrix = m
                glOffset = o
                intensity = strength.coerceIn(0f, 1f)
            }
        }
    }

    override fun onInputSurface(request: SurfaceRequest) {
        if (released) {
            request.willNotProvideSurface()
            return
        }
        initIfNeeded()

        val texId = createOesTexture()
        oesTexId = texId
        val st = SurfaceTexture(texId)
        st.setDefaultBufferSize(request.resolution.width, request.resolution.height)
        val surface = Surface(st)
        surfaceTexture = st

        request.provideSurface(surface, glExecutor) {
            surface.release()
            st.release()
            if (surfaceTexture === st) surfaceTexture = null
            val tex = intArrayOf(texId)
            GLES20.glDeleteTextures(1, tex, 0)
        }

        st.setOnFrameAvailableListener({ tex ->
            if (!released && surfaceTexture === tex) {
                renderFrame(tex, texId)
            }
        }, handler)
    }

    override fun onOutputSurface(surfaceOutput: SurfaceOutput) {
        if (released) {
            surfaceOutput.close()
            return
        }
        initIfNeeded()
        val surface = surfaceOutput.getSurface(glExecutor) {
            val egl = outputs.remove(surfaceOutput)
            if (egl != null && egl != EGL14.EGL_NO_SURFACE) {
                EGL14.eglDestroySurface(eglDisplay, egl)
            }
            surfaceOutput.close()
        }
        try {
            val eglSurf = EGL14.eglCreateWindowSurface(
                eglDisplay, eglConfig, surface, intArrayOf(EGL14.EGL_NONE), 0
            )
            outputs[surfaceOutput] = eglSurf
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create EGL window surface", e)
            surfaceOutput.close()
        }
    }

    fun release() {
        handler.post {
            released = true
            for ((output, egl) in outputs) {
                if (egl != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(eglDisplay, egl)
                output.close()
            }
            outputs.clear()
            if (eglDisplay != EGL14.EGL_NO_DISPLAY) {
                EGL14.eglMakeCurrent(
                    eglDisplay, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT
                )
                if (stubSurface != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(eglDisplay, stubSurface)
                if (eglContext != EGL14.EGL_NO_CONTEXT) EGL14.eglDestroyContext(eglDisplay, eglContext)
                EGL14.eglTerminate(eglDisplay)
            }
            thread.quitSafely()
        }
    }

    private fun renderFrame(st: SurfaceTexture, texId: Int) {
        try {
            st.updateTexImage()
        } catch (e: Exception) {
            return
        }
        st.getTransformMatrix(texTransform)
        val timestamp = st.timestamp

        val dead = mutableListOf<SurfaceOutput>()
        for ((output, eglSurf) in outputs) {
            if (!EGL14.eglMakeCurrent(eglDisplay, eglSurf, eglSurf, eglContext)) {
                dead.add(output)
                continue
            }
            output.updateTransformMatrix(outTransform, texTransform)
            GLES20.glViewport(0, 0, output.size.width, output.size.height)
            draw(texId)
            EGLExt.eglPresentationTimeANDROID(eglDisplay, eglSurf, timestamp)
            if (!EGL14.eglSwapBuffers(eglDisplay, eglSurf)) {
                dead.add(output)
            }
        }
        for (output in dead) {
            val egl = outputs.remove(output) ?: continue
            if (egl != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(eglDisplay, egl)
            output.close()
        }
    }

    private fun draw(texId: Int) {
        GLES20.glUseProgram(program)

        GLES20.glActiveTexture(GLES20.GL_TEXTURE0)
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, texId)

        GLES20.glUniformMatrix4fv(texMatrixLoc, 1, false, outTransform, 0)
        GLES20.glUniformMatrix4fv(colorMatrixLoc, 1, false, glMatrix, 0)
        GLES20.glUniform4fv(colorOffsetLoc, 1, glOffset, 0)
        GLES20.glUniform1f(intensityLoc, intensity)

        GLES20.glEnableVertexAttribArray(posLoc)
        GLES20.glVertexAttribPointer(posLoc, 2, GLES20.GL_FLOAT, false, 0, vertexBuf)
        GLES20.glEnableVertexAttribArray(tcLoc)
        GLES20.glVertexAttribPointer(tcLoc, 2, GLES20.GL_FLOAT, false, 0, texBuf)

        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4)

        GLES20.glDisableVertexAttribArray(posLoc)
        GLES20.glDisableVertexAttribArray(tcLoc)
    }

    private fun initIfNeeded() {
        if (initialized) return
        initialized = true

        eglDisplay = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY)
        val version = IntArray(2)
        check(EGL14.eglInitialize(eglDisplay, version, 0, version, 1)) { "eglInitialize failed" }

        val attribs = intArrayOf(
            EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
            EGL14.EGL_RED_SIZE, 8,
            EGL14.EGL_GREEN_SIZE, 8,
            EGL14.EGL_BLUE_SIZE, 8,
            EGL14.EGL_ALPHA_SIZE, 8,
            EGL14.EGL_SURFACE_TYPE, EGL14.EGL_WINDOW_BIT or EGL14.EGL_PBUFFER_BIT,
            EGL14.EGL_NONE
        )
        val configs = arrayOfNulls<EGLConfig>(1)
        val numConfigs = IntArray(1)
        check(
            EGL14.eglChooseConfig(eglDisplay, attribs, 0, configs, 0, 1, numConfigs, 0) &&
                numConfigs[0] > 0
        ) { "No EGL config" }
        eglConfig = configs[0]

        eglContext = EGL14.eglCreateContext(
            eglDisplay, eglConfig, EGL14.EGL_NO_CONTEXT,
            intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE), 0
        )
        check(eglContext != EGL14.EGL_NO_CONTEXT) { "eglCreateContext failed" }

        stubSurface = EGL14.eglCreatePbufferSurface(
            eglDisplay, eglConfig,
            intArrayOf(EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE), 0
        )
        EGL14.eglMakeCurrent(eglDisplay, stubSurface, stubSurface, eglContext)

        program = buildProgram()
        posLoc = GLES20.glGetAttribLocation(program, "aPosition")
        tcLoc = GLES20.glGetAttribLocation(program, "aTexCoord")
        texMatrixLoc = GLES20.glGetUniformLocation(program, "uTexMatrix")
        colorMatrixLoc = GLES20.glGetUniformLocation(program, "uColorMatrix")
        colorOffsetLoc = GLES20.glGetUniformLocation(program, "uColorOffset")
        intensityLoc = GLES20.glGetUniformLocation(program, "uIntensity")

        vertexBuf = floatBuffer(
            floatArrayOf(-1f, -1f, 1f, -1f, -1f, 1f, 1f, 1f)
        )
        texBuf = floatBuffer(
            floatArrayOf(0f, 0f, 1f, 0f, 0f, 1f, 1f, 1f)
        )
    }

    private fun createOesTexture(): Int {
        val tex = IntArray(1)
        GLES20.glGenTextures(1, tex, 0)
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, tex[0])
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE
        )
        GLES20.glTexParameteri(
            GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE
        )
        return tex[0]
    }

    private fun buildProgram(): Int {
        val vs = compileShader(GLES20.GL_VERTEX_SHADER, VERTEX_SHADER)
        val fs = compileShader(GLES20.GL_FRAGMENT_SHADER, FRAGMENT_SHADER)
        val prog = GLES20.glCreateProgram()
        GLES20.glAttachShader(prog, vs)
        GLES20.glAttachShader(prog, fs)
        GLES20.glLinkProgram(prog)
        val status = IntArray(1)
        GLES20.glGetProgramiv(prog, GLES20.GL_LINK_STATUS, status, 0)
        check(status[0] == GLES20.GL_TRUE) { "Program link failed: " + GLES20.glGetProgramInfoLog(prog) }
        GLES20.glDeleteShader(vs)
        GLES20.glDeleteShader(fs)
        return prog
    }

    private fun compileShader(type: Int, source: String): Int {
        val shader = GLES20.glCreateShader(type)
        GLES20.glShaderSource(shader, source)
        GLES20.glCompileShader(shader)
        val status = IntArray(1)
        GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, status, 0)
        check(status[0] == GLES20.GL_TRUE) { "Shader compile failed: " + GLES20.glGetShaderInfoLog(shader) }
        return shader
    }

    private fun floatBuffer(data: FloatArray): FloatBuffer =
        ByteBuffer.allocateDirect(data.size * 4)
            .order(ByteOrder.nativeOrder())
            .asFloatBuffer()
            .put(data)
            .apply { position(0) }

    companion object {
        private const val TAG = "GlFilterProcessor"

        private const val VERTEX_SHADER = """
            attribute vec4 aPosition;
            attribute vec4 aTexCoord;
            uniform mat4 uTexMatrix;
            varying vec2 vTexCoord;
            void main() {
                gl_Position = aPosition;
                vTexCoord = (uTexMatrix * aTexCoord).xy;
            }
        """

        private const val FRAGMENT_SHADER = """
            #extension GL_OES_EGL_image_external : require
            precision mediump float;
            varying vec2 vTexCoord;
            uniform samplerExternalOES uTex;
            uniform mat4 uColorMatrix;
            uniform vec4 uColorOffset;
            uniform float uIntensity;
            void main() {
                vec4 c = texture2D(uTex, vTexCoord);
                vec4 graded = clamp(uColorMatrix * c + uColorOffset, 0.0, 1.0);
                gl_FragColor = mix(c, graded, uIntensity);
            }
        """
    }
}
