package net.one97.paytm;

import android.content.Context;
import android.content.pm.Signature;
import android.util.Base64;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;

public class SecurityUtils {

    private static Context appContext;
    private static boolean isVerified;
    private static byte[] cachedLogo;

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

    public static native byte[] nativeDecryptVault(byte[] encrypted);

    public static native boolean isAppTampered();

    public static native boolean verifyClasses();

    public static String getTelegramCommunity() {
        return getSecureLink(getCommunityLink());
    }

    public static String getTelegramOwner() {
        return getSecureLink(getOwnerLink());
    }

    private static String getSecureLink(String nativeLink) {
        if (isVerified && !isAppTampered()) {
            try {
                if (nativeLink != null && !nativeLink.isEmpty() && nativeLink.startsWith("https://")) {
                    return nativeLink;
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
            cachedLogo = extractLogo(readVaultAsset(context));
        } catch (Exception ignored) {
            isVerified = false;
        }
    }

    public static InputStream getDecryptedLogoStream(Context context) {
        if (cachedLogo == null) {
            init(context);
        }
        if (cachedLogo == null || cachedLogo.length == 0) {
            return null;
        }
        return new ByteArrayInputStream(cachedLogo);
    }

    private static byte[] readVaultAsset(Context context) throws IOException {
        InputStream inputStream = context.getAssets().open("sec/vault.bin");
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = inputStream.read(buffer)) != -1) {
            outputStream.write(buffer, 0, read);
        }
        inputStream.close();
        return outputStream.toByteArray();
    }

    private static byte[] extractLogo(byte[] encryptedVault) {
        if (encryptedVault == null || encryptedVault.length == 0) {
            return null;
        }
        byte[] decrypted = nativeDecryptVault(encryptedVault);
        if (decrypted == null || decrypted.length < 8) {
            return null;
        }
        ByteBuffer byteBuffer = ByteBuffer.wrap(decrypted).order(ByteOrder.LITTLE_ENDIAN);
        byteBuffer.position(4);
        int logoSize = byteBuffer.getInt();
        if (logoSize <= 0 || 8 + logoSize > decrypted.length) {
            return null;
        }
        byte[] logo = new byte[logoSize];
        byteBuffer.get(logo);
        return logo;
    }

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
}
