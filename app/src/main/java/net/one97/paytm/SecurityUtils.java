package net.one97.paytm;

import android.content.Context;
import android.content.pm.Signature;
import android.util.Base64;

import java.security.MessageDigest;

public class SecurityUtils {

    private static final String TELEGRAM_COMMUNITY = "https://t.me/skillx_community";
    private static final String TELEGRAM_OWNER = "https://t.me/skillx_owner";

    private static Context appContext;
    private static boolean isVerified;

    static {
        try {
            System.loadLibrary("native-lib");
        } catch (UnsatisfiedLinkError ignored) {
        }
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
        return TELEGRAM_COMMUNITY;
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
        return TELEGRAM_OWNER;
    }

    public static native String getCommunityLink();

    public static native String getOwnerLink();

    public static native boolean isAppTampered();

    public static native boolean verifyClasses();

    private static boolean verifyAppSignature(Context context) {
        try {
            Signature[] signatures = context.getPackageManager()
                    .getPackageInfo(context.getPackageName(), 64)
                    .signatures;
            for (Signature signature : signatures) {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                digest.update(signature.toByteArray());
                if (Base64.encodeToString(digest.digest(), 0).trim().length() > 0) {
                    return true;
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return false;
    }
}
