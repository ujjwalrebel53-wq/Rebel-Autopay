package net.one97.paytm;

import android.app.Activity;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.Window;
import android.view.animation.AlphaAnimation;
import android.view.animation.TranslateAnimation;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
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
    private LinearLayout headerSection;
    private LinearLayout layoutDirectOpen;
    private LinearLayout layoutIntentContent;
    private Button btnTelegram;
    private Button btnContactDev;
    private Intent launchIntent;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SecurityUtils.init(this);
        setContentView(R.layout.activity_main);

        ivQRCode = findViewById(R.id.ivQRCode);
        ivLogo = findViewById(R.id.ivLogo);
        ivLogoIntent = findViewById(R.id.ivLogoIntent);
        headerSection = findViewById(R.id.headerSection);
        layoutDirectOpen = findViewById(R.id.layoutDirectOpen);
        layoutIntentContent = findViewById(R.id.layoutIntentContent);
        btnTelegram = findViewById(R.id.btnTelegram);
        btnContactDev = findViewById(R.id.btnContactDev);

        launchIntent = getIntent();
        boolean hasUpiIntent = isUpiIntent(launchIntent);

        if (hasUpiIntent) {
            showUpiQrScreen();
        } else {
            showDirectOpenScreen();
        }

        btnTelegram.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramCommunity()))));
        btnContactDev.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramOwner()))));
    }

    private boolean isUpiIntent(Intent intent) {
        if (intent == null) {
            return false;
        }
        if (intent.getData() != null) {
            return "upi".equals(intent.getData().getScheme());
        }
        return intent.hasExtra(Intent.EXTRA_TEXT);
    }

    private void showUpiQrScreen() {
        layoutIntentContent.setVisibility(android.view.View.VISIBLE);
        layoutDirectOpen.setVisibility(android.view.View.GONE);
        loadLogo(ivLogoIntent);
        animateHeader();

        String upiPayload = extractUpiPayload(launchIntent);
        if (upiPayload != null) {
            try {
                ivQRCode.setImageBitmap(new BarcodeEncoder().encodeBitmap(upiPayload, BarcodeFormat.QR_CODE, 600, 600));
            } catch (WriterException e) {
                e.printStackTrace();
                Toast.makeText(this, "Failed to generate QR", Toast.LENGTH_SHORT).show();
            }
        }

        showSupportDialog();
    }

    private void showDirectOpenScreen() {
        layoutDirectOpen.setVisibility(android.view.View.VISIBLE);
        layoutIntentContent.setVisibility(android.view.View.GONE);
        loadLogo(ivLogo);
    }

    private void loadLogo(ImageView imageView) {
        try (InputStream inputStream = getAssets().open("logo.png")) {
            imageView.setImageBitmap(BitmapFactory.decodeStream(inputStream));
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void animateHeader() {
        AlphaAnimation alphaAnimation = new AlphaAnimation(0.0f, 1.0f);
        alphaAnimation.setDuration(800L);
        alphaAnimation.setStartOffset(300L);

        TranslateAnimation translateAnimation = new TranslateAnimation(0.0f, 0.0f, -50.0f, 0.0f);
        translateAnimation.setDuration(800L);
        translateAnimation.setStartOffset(300L);

        headerSection.setAlpha(1.0f);
        headerSection.setTranslationY(0.0f);
        headerSection.startAnimation(alphaAnimation);
        headerSection.startAnimation(translateAnimation);
    }

    private String extractUpiPayload(Intent intent) {
        if (intent == null) {
            return null;
        }
        Uri data = intent.getData();
        if (data != null && "upi".equals(data.getScheme())) {
            return data.toString();
        }
        if (intent.hasExtra(Intent.EXTRA_TEXT)) {
            return intent.getStringExtra(Intent.EXTRA_TEXT);
        }
        return null;
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
        dialog.show();
    }
}
