package com.vard.app.fallmonitor

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build

object FallNotificationSound {
    // A new ID is necessary for existing installs: Android retains the original channel sound.
    const val CHANNEL_ID = "vard-fall-sound-v1"
    fun uri(context: Context): Uri = Uri.parse("android.resource://${context.packageName}/raw/vard_fall_alert")

    fun register(context: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
        val channel = NotificationChannel(CHANNEL_ID, "Alertas de queda", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Avisos de possível queda"
            enableVibration(true)
            setSound(uri(context), attributes)
        }
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
    }
}
