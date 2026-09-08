package com.friday.remote.security

import android.content.Context
import android.content.SharedPreferences
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
        return sharedPreferences.getString("server_url", "http://192.168.1.100:8000") ?: ""
    }

    fun setServerUrl(url: String) {
        sharedPreferences.edit().putString("server_url", url).apply()
    }

    fun getToken(): String {
        return sharedPreferences.getString("auth_token", "") ?: ""
    }

    fun setToken(token: String) {
        sharedPreferences.edit().putString("auth_token", token).apply()
    }

    fun isTlsEnabled(): Boolean {
        return sharedPreferences.getBoolean("tls_enabled", false)
    }

    fun setTlsEnabled(enabled: Boolean) {
        sharedPreferences.edit().putBoolean("tls_enabled", enabled).apply()
    }
}
