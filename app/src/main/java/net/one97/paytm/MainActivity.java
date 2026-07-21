package net.one97.paytm;

import android.app.Activity;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.animation.AlphaAnimation;
import android.view.animation.TranslateAnimation;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.view.Window;
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
        boolean hasUpiIntent;
        String upiPayload = null;

        super.onCreate(savedInstanceState);
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
        if (launchIntent == null || launchIntent.getData() == null) {
            hasUpiIntent = launchIntent != null && launchIntent.hasExtra(Intent.EXTRA_TEXT);
        } else {
            hasUpiIntent = "upi".equals(launchIntent.getData().getScheme());
        }

        if (hasUpiIntent) {
            layoutIntentContent.setVisibility(android.view.View.VISIBLE);
            layoutDirectOpen.setVisibility(android.view.View.GONE);
            loadLogo(ivLogoIntent);

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
        } else {
            layoutDirectOpen.setVisibility(android.view.View.VISIBLE);
            layoutIntentContent.setVisibility(android.view.View.GONE);
            loadLogo(ivLogo);
        }

        btnTelegram.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramCommunity()))));
        btnContactDev.setOnClickListener(v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(SecurityUtils.getTelegramOwner()))));
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
