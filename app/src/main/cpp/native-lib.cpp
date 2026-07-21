#include <jni.h>
#include <string>
#include <android/log.h>

#define LOG_TAG "RebelAutopay"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT jstring JNICALL
Java_net_one97_paytm_SecurityUtils_getCommunityLink(JNIEnv *env, jclass clazz) {
    return env->NewStringUTF("https://t.me/+wEODy3Qd2xRhZTI1");
}

JNIEXPORT jstring JNICALL
Java_net_one97_paytm_SecurityUtils_getOwnerLink(JNIEnv *env, jclass clazz) {
    return env->NewStringUTF("https://t.me/+wEODy3Qd2xRhZTI1");
}

JNIEXPORT jboolean JNICALL
Java_net_one97_paytm_SecurityUtils_isAppTampered(JNIEnv *env, jclass clazz) {
    jclass securityUtilsClass = env->FindClass("net/one97/paytm/SecurityUtils");
    if (securityUtilsClass == nullptr) {
        LOGI("SecurityUtils class not found - tampered!");
        return JNI_TRUE;
    }

    jclass mainActivityClass = env->FindClass("net/one97/paytm/MainActivity");
    if (mainActivityClass == nullptr) {
        LOGI("MainActivity class not found - tampered!");
        return JNI_TRUE;
    }

    return JNI_FALSE;
}

JNIEXPORT jboolean JNICALL
Java_net_one97_paytm_SecurityUtils_verifyClasses(JNIEnv *env, jclass clazz) {
    jclass securityUtilsClass = env->FindClass("net/one97/paytm/SecurityUtils");
    if (securityUtilsClass == nullptr) {
        return JNI_FALSE;
    }

    jclass mainActivityClass = env->FindClass("net/one97/paytm/MainActivity");
    if (mainActivityClass == nullptr) {
        return JNI_FALSE;
    }

    return JNI_TRUE;
}

}
