package net.one97.paytm;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.View;

import java.util.Random;

public class MatrixRainView extends View {

    private static final String CHARS = "01アイウABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final int COLUMN_WIDTH = 32;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Random random = new Random();
    private int[] drops;
    private int columnCount;
    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            invalidate();
            postDelayed(this, 55L);
        }
    };

    public MatrixRainView(Context context) {
        super(context);
        init();
    }

    public MatrixRainView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        paint.setColor(0x2800FF41);
        paint.setTextSize(26f);
        setWillNotDraw(false);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        columnCount = Math.max(1, w / COLUMN_WIDTH);
        drops = new int[columnCount];
        for (int i = 0; i < columnCount; i++) {
            drops[i] = random.nextInt(Math.max(1, h / COLUMN_WIDTH));
        }
        removeCallbacks(tick);
        post(tick);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (drops == null) {
            return;
        }
        for (int i = 0; i < columnCount; i++) {
            String ch = String.valueOf(CHARS.charAt(random.nextInt(CHARS.length())));
            float x = i * COLUMN_WIDTH;
            float y = drops[i] * COLUMN_WIDTH;
            canvas.drawText(ch, x, y, paint);
            if (y > getHeight() && random.nextFloat() > 0.97f) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        removeCallbacks(tick);
        super.onDetachedFromWindow();
    }
}
