-repackageclasses 'o'
-allowaccessmodification
-overloadaggressively
-optimizationpasses 5

-keep class net.one97.paytm.SecurityUtils {
    public static void init(android.content.Context);
    public static java.io.InputStream getDecryptedLogoStream(android.content.Context);
    public static java.lang.String getTelegramCommunity();
    public static java.lang.String getTelegramOwner();
    native <methods>;
}

-keep class net.one97.paytm.MainActivity { *; }

-keepclasseswithmembernames class * {
    native <methods>;
}

-keep class com.journeyapps.barcodescanner.** { *; }
-keep class com.google.zxing.** { *; }
