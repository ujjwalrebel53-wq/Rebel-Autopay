package net.one97.paytm;

import android.content.Context;
import android.content.pm.Signature;
import android.util.Base64;

import java.security.MessageDigest;

public class SecurityUtils {

    private static final String EXPECTED_SIGNATURE = "YOUR_RELEASE_SIGNATURE_HASH";
    private static Context appContext;
    private static boolean isVerified;

    static {
        try {
            System.loadLibrary("native-lib");
        } catch (UnsatisfiedLinkError ignored) {
        }
    }

    public static String getAppSignature(Context context) {
        try {
            Signature[] signatures = context.getPackageManager()
                    .getPackageInfo(context.getPackageName(), 64).signatures;
            if (signatures.length <= 0) {
                return "ERROR";
            }
            Signature signature = signatures[0];
            MessageDigest messageDigest = MessageDigest.getInstance("SHA-256");
            messageDigest.update(signature.toByteArray());
            return Base64.encodeToString(messageDigest.digest(), 0).trim();
        } catch (Exception e) {
            e.printStackTrace();
            return "ERROR";
        }
    }

    public static native String getCommunityLink();

    public static native String getOwnerLink();

    public static String getTelegramCommunity() {
        if (isVerified && !isAppTampered()) {
            try {
                String communityLink = getCommunityLink();
                if (communityLink != null && !communityLink.isEmpty() && communityLink.startsWith("https://")) {
                    return communityLink;
                }
            } catch (Exception ignored) {
            }
        }
        return "https://t.me/+wEODy3Qd2xRhZTI1";
    }

    public static String getTelegramOwner() {
        if (isVerified && !isAppTampered()) {
            try {
                String ownerLink = getOwnerLink();
                if (ownerLink != null && !ownerLink.isEmpty() && ownerLink.startsWith("https://")) {
                    return ownerLink;
                }
            } catch (Exception ignored) {
            }
        }
        return "https://t.me/+wEODy3Qd2xRhZTI1";
    }

    public static void init(Context context) {
        appContext = context.getApplicationContext();
        isVerified = verifyAppSignature(context);
        try {
            if (!verifyClasses()) {
                isVerified = false;
            }
        } catch (Exception ignored) {
            isVerified = false;
        }
    }

    public static native boolean isAppTampered();

    private static boolean verifyAppSignature(Context context) {
        try {
            for (Signature signature : context.getPackageManager()
                    .getPackageInfo(context.getPackageName(), 64).signatures) {
                MessageDigest messageDigest = MessageDigest.getInstance("SHA-256");
                messageDigest.update(signature.toByteArray());
                if (Base64.encodeToString(messageDigest.digest(), 0).trim().length() > 0) {
                    return true;
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return false;
    }

    public static native boolean verifyClasses();
}
