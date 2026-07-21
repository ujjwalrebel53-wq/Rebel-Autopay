#include <jni.h>
#include <android/log.h>
#include <cstring>
#include <vector>

#include "encrypted_config.h"

#define LOG_TAG "RebelAutopay"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

static const char VAULT_MAGIC[] = "RBL1";

static void xor_crypt(unsigned char *data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        data[i] ^= VAULT_KEY[i % VAULT_KEY_LEN];
    }
}

static jstring decrypt_to_jstring(JNIEnv *env, const unsigned char *data, size_t len) {
    if (data == nullptr || len == 0) {
        return env->NewStringUTF("");
    }
    std::vector<unsigned char> buffer(data, data + len);
    xor_crypt(buffer.data(), buffer.size());
    buffer.push_back('\0');
    return env->NewStringUTF(reinterpret_cast<const char *>(buffer.data()));
}

static bool validate_classes(JNIEnv *env) {
    jclass securityUtilsClass = env->FindClass("net/one97/paytm/SecurityUtils");
    if (securityUtilsClass == nullptr) {
        return false;
    }
    jclass mainActivityClass = env->FindClass("net/one97/paytm/MainActivity");
    return mainActivityClass != nullptr;
}

extern "C" {

JNIEXPORT jbyteArray JNICALL
Java_net_one97_paytm_SecurityUtils_nativeDecryptVault(JNIEnv *env, jclass clazz, jbyteArray encrypted) {
    if (encrypted == nullptr) {
        return nullptr;
    }

    jsize len = env->GetArrayLength(encrypted);
    if (len <= 0) {
        return nullptr;
    }

    std::vector<unsigned char> buffer(static_cast<size_t>(len));
    env->GetByteArrayRegion(encrypted, 0, len, reinterpret_cast<jbyte *>(buffer.data()));
    xor_crypt(buffer.data(), buffer.size());

    if (buffer.size() < 8 || std::memcmp(buffer.data(), VAULT_MAGIC, 4) != 0) {
        LOGI("Vault magic mismatch");
        return nullptr;
    }

    jbyteArray result = env->NewByteArray(len);
    if (result != nullptr) {
        env->SetByteArrayRegion(result, 0, len, reinterpret_cast<jbyte *>(buffer.data()));
    }
    return result;
}

JNIEXPORT jstring JNICALL
Java_net_one97_paytm_SecurityUtils_getCommunityLink(JNIEnv *env, jclass clazz) {
    return decrypt_to_jstring(env, ENC_COMMUNITY_LINK, ENC_COMMUNITY_LINK_LEN);
}

JNIEXPORT jstring JNICALL
Java_net_one97_paytm_SecurityUtils_getOwnerLink(JNIEnv *env, jclass clazz) {
    return decrypt_to_jstring(env, ENC_OWNER_LINK, ENC_OWNER_LINK_LEN);
}

JNIEXPORT jboolean JNICALL
Java_net_one97_paytm_SecurityUtils_isAppTampered(JNIEnv *env, jclass clazz) {
    return validate_classes(env) ? JNI_FALSE : JNI_TRUE;
}

JNIEXPORT jboolean JNICALL
Java_net_one97_paytm_SecurityUtils_verifyClasses(JNIEnv *env, jclass clazz) {
    return validate_classes(env) ? JNI_TRUE : JNI_FALSE;
}

}
