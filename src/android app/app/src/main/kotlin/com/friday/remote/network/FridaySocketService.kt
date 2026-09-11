package com.friday.remote.network

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.friday.remote.FridayApp
import com.friday.remote.R
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class FridaySocketService : Service() {

    @Inject
    lateinit var socketManager: FridaySocketManager

    override fun onCreate() {
        super.onCreate()
        Log.d("FridaySocket", "Service onCreate() - starting foreground service")
        startForeground(NOTIFICATION_ID, createNotification())
        Log.d("FridaySocket", "Service calling socketManager.connect()")
        socketManager.connect()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d("FridaySocket", "Service onStartCommand()")
        return START_STICKY
    }

    override fun onDestroy() {
        Log.d("FridaySocket", "Service onDestroy()")
        socketManager.disconnect()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, FridayApp.CHANNEL_ID)
            .setContentTitle("F.R.I.D.A.Y Active")
            .setContentText("Connected to home server")
            .setSmallIcon(R.drawable.ic_friday_accent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    companion object {
        private const val NOTIFICATION_ID = 1001
    }
}
