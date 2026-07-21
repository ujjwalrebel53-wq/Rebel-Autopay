#include <jni.h>
#include <android/log.h>

#define LOG_TAG "RebelAutopay"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT jstring JNICALL
Java_com_rebel_autopay_SecurityUtils_getCommunityLink(JNIEnv *env, jclass clazz) {
    return env->NewStringUTF("https://t.me/+wEODy3Qd2xRhZTI1");
}

JNIEXPORT jstring JNICALL
Java_com_rebel_autopay_SecurityUtils_getOwnerLink(JNIEnv *env, jclass clazz) {
    return env->NewStringUTF("https://t.me/+wEODy3Qd2xRhZTI1");
}

JNIEXPORT jboolean JNICALL
Java_com_rebel_autopay_SecurityUtils_isAppTampered(JNIEnv *env, jclass clazz) {
    jclass securityUtilsClass = env->FindClass("com/rebel/autopay/SecurityUtils");
    if (securityUtilsClass == nullptr) {
        LOGI("SecurityUtils class not found - tampered!");
        return JNI_TRUE;
    }

    jclass mainActivityClass = env->FindClass("com/rebel/autopay/MainActivity");
    if (mainActivityClass == nullptr) {
        LOGI("MainActivity class not found - tampered!");
        return JNI_TRUE;
    }

    return JNI_FALSE;
}

JNIEXPORT jboolean JNICALL
Java_com_rebel_autopay_SecurityUtils_verifyClasses(JNIEnv *env, jclass clazz) {
    jclass securityUtilsClass = env->FindClass("com/rebel/autopay/SecurityUtils");
    if (securityUtilsClass == nullptr) {
        return JNI_FALSE;
    }

    jclass mainActivityClass = env->FindClass("com/rebel/autopay/MainActivity");
    if (mainActivityClass == nullptr) {
        return JNI_FALSE;
    }

    return JNI_TRUE;
}

}
