package com.friday.remote.security

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecurityManager @Inject constructor(
    @ApplicationContext context: Context
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPreferences: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "friday_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun getServerUrl(): String {
        val url = sharedPreferences.getString("server_url", "http://REPLACE_WITH_SERVER_IP:8000") ?: ""
        Log.d("FridaySecurity", "getServerUrl() = '$url'")
        return url
    }

    fun setServerUrl(url: String) {
        Log.d("FridaySecurity", "setServerUrl('$url')")
        sharedPreferences.edit().putString("server_url", url).apply()
    }

    fun getToken(): String {
        val token = sharedPreferences.getString("auth_token", "") ?: ""
        Log.d("FridaySecurity", "getToken() = '${if (token.isNotEmpty()) "[SET]" else "[EMPTY]"}'")
        return token
    }

    fun setToken(token: String) {
        Log.d("FridaySecurity", "setToken('$token')")
        sharedPreferences.edit().putString("auth_token", token).apply()
    }

    fun getDeviceToken(): String = sharedPreferences.getString("device_token", "") ?: ""

    fun setDeviceToken(token: String) {
        sharedPreferences.edit().putString("device_token", token).apply()
    }

    fun getDeviceId(): String = sharedPreferences.getString("device_id", "") ?: ""

    fun setDeviceId(deviceId: String) {
        sharedPreferences.edit().putString("device_id", deviceId).apply()
    }

    fun isTlsEnabled(): Boolean {
        val enabled = sharedPreferences.getBoolean("tls_enabled", false)
        Log.d("FridaySecurity", "isTlsEnabled() = $enabled")
        return enabled
    }

    fun setTlsEnabled(enabled: Boolean) {
        Log.d("FridaySecurity", "setTlsEnabled($enabled)")
        sharedPreferences.edit().putBoolean("tls_enabled", enabled).apply()
    }
}
