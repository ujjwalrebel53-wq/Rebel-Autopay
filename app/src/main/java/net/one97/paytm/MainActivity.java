package net.one97.paytm;

import android.app.Activity;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.Window;
import android.view.animation.Animation;
import android.view.animation.AnimationUtils;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.WriterException;
import com.journeyapps.barcodescanner.BarcodeEncoder;

import java.io.IOException;
import java.io.InputStream;

public class MainActivity extends Activity {

    private ImageView ivQRCode;
    private ImageView ivLogo;
    private ImageView ivLogoIntent;
    private TextView tvStatus;
    private View terminalBar;
    private View scanLine;
    private LinearLayout headerSection;
    private LinearLayout directHeaderSection;
    private LinearLayout directInfoSection;
    private View qrSection;
    private View qrGlowFrame;
    private LinearLayout infoSection;
    private LinearLayout layoutDirectOpen;
    private LinearLayout layoutIntentContent;
    private Button btnTelegram;
    private Button btnContactDev;
    private Intent launchIntent;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        boolean hasUpiIntent;
        String upiPayload = null;

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        ivQRCode = findViewById(R.id.ivQRCode);
        ivLogo = findViewById(R.id.ivLogo);
        ivLogoIntent = findViewById(R.id.ivLogoIntent);
        tvStatus = findViewById(R.id.tvStatus);
        terminalBar = findViewById(R.id.terminalBar);
        scanLine = findViewById(R.id.scanLine);
        headerSection = findViewById(R.id.headerSection);
        directHeaderSection = findViewById(R.id.directHeaderSection);
        directInfoSection = findViewById(R.id.directInfoSection);
        qrSection = findViewById(R.id.qrSection);
        qrGlowFrame = findViewById(R.id.qrGlowFrame);
        infoSection = findViewById(R.id.infoSection);
        layoutDirectOpen = findViewById(R.id.layoutDirectOpen);
        layoutIntentContent = findViewById(R.id.layoutIntentContent);
        btnTelegram = findViewById(R.id.btnTelegram);
        btnContactDev = findViewById(R.id.btnContactDev);

        launchIntent = getIntent();
        if (launchIntent == null || launchIntent.getData() == null) {
            hasUpiIntent = launchIntent != null && launchIntent.hasExtra(Intent.EXTRA_TEXT);
        } else {
            hasUpiIntent = "upi".equals(launchIntent.getData().getScheme());
        }

        animateTerminalBar();

        if (hasUpiIntent) {
            layoutIntentContent.setVisibility(View.VISIBLE);
            layoutDirectOpen.setVisibility(View.GONE);
            loadLogo(ivLogoIntent);
            runBootSequence(() -> {
                animateView(headerSection, R.anim.slide_fade_down, 0L);
                animateView(qrSection, R.anim.scale_fade_in, 200L, () -> {
                    qrGlowFrame.startAnimation(AnimationUtils.loadAnimation(this, R.anim.pulse_glow));
                    scanLine.startAnimation(AnimationUtils.loadAnimation(this, R.anim.scan_line_move));
                });
                animateView(infoSection, R.anim.slide_fade_up, 400L);
                animateView(btnTelegram, R.anim.slide_fade_up, 550L);
                animateView(btnContactDev, R.anim.slide_fade_up, 700L);
                handler.postDelayed(this::showSupportDialog, 900L);
            });

            if (launchIntent != null) {
                Uri data = launchIntent.getData();
                if (data != null && "upi".equals(data.getScheme())) {
                    upiPayload = data.toString();
                } else if (launchIntent.hasExtra(Intent.EXTRA_TEXT)) {
                    upiPayload = launchIntent.getStringExtra(Intent.EXTRA_TEXT);
                }
                if (upiPayload != null) {
                    try {
                        ivQRCode.setImageBitmap(new BarcodeEncoder().encodeBitmap(upiPayload, BarcodeFormat.QR_CODE, 600, 600));
                    } catch (WriterException e) {
                        e.printStackTrace();
                        Toast.makeText(this, "Failed to generate QR", Toast.LENGTH_SHORT).show();
                    }
                }
            }
        } else {
            layoutDirectOpen.setVisibility(View.VISIBLE);
            layoutIntentContent.setVisibility(View.GONE);
            loadLogo(ivLogo);
            animateView(directHeaderSection, R.anim.slide_fade_down, 150L);
            animateView(directInfoSection, R.anim.slide_fade_up, 350L);
        }

        btnTelegram.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramCommunity()))));
        btnContactDev.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramOwner()))));
    }

    private void animateTerminalBar() {
        animateView(terminalBar, R.anim.fade_in, 0L);
    }

    private void runBootSequence(Runnable onComplete) {
        tvStatus.setAlpha(1f);
        typewriter(tvStatus, getString(R.string.status_boot), 35L, () ->
                handler.postDelayed(() ->
                        typewriter(tvStatus, getString(R.string.status_ready), 30L, onComplete), 400L));
    }

    private void typewriter(TextView textView, String fullText, long charDelay, Runnable onComplete) {
        textView.setText("");
        for (int i = 0; i <= fullText.length(); i++) {
            final int index = i;
            handler.postDelayed(() -> {
                textView.setText(fullText.substring(0, index));
                if (index == fullText.length() && onComplete != null) {
                    onComplete.run();
                }
            }, index * charDelay);
        }
    }

    private void animateView(View view, int animRes, long delay) {
        animateView(view, animRes, delay, null);
    }

    private void animateView(View view, int animRes, long delay, Runnable onEnd) {
        view.setAlpha(1f);
        view.setTranslationY(0f);
        Animation animation = AnimationUtils.loadAnimation(this, animRes);
        animation.setStartOffset(delay);
        animation.setAnimationListener(new Animation.AnimationListener() {
            @Override
            public void onAnimationStart(Animation animation) {
            }

            @Override
            public void onAnimationEnd(Animation animation) {
                view.clearAnimation();
                if (onEnd != null) {
                    onEnd.run();
                }
            }

            @Override
            public void onAnimationRepeat(Animation animation) {
            }
        });
        view.startAnimation(animation);
    }

    private void showSupportDialog() {
        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        dialog.setContentView(R.layout.dialog_support);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(android.graphics.Color.TRANSPARENT));
        }
        dialog.setCancelable(true);
        Button btnDialogTelegram = dialog.findViewById(R.id.btnDialogTelegram);
        Button btnDialogLater = dialog.findViewById(R.id.btnDialogLater);
        btnDialogTelegram.setOnClickListener(v -> {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramCommunity())));
            dialog.dismiss();
        });
        btnDialogLater.setOnClickListener(v -> dialog.dismiss());

        View dialogRoot = dialog.findViewById(R.id.btnDialogTelegram).getRootView();
        dialogRoot.setAlpha(0f);
        dialogRoot.setTranslationY(60f);
        dialog.show();
        dialogRoot.animate()
                .alpha(1f)
                .translationY(0f)
                .setDuration(500L)
                .start();
    }

    private void loadLogo(ImageView imageView) {
        try {
            InputStream inputStream = getAssets().open("logo.png");
            imageView.setImageBitmap(BitmapFactory.decodeStream(inputStream));
            inputStream.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
