package com.vard.app.fallmonitor

import android.content.Context
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Requests fresh fixes only during the fall confirmation window; never tracks continuously. */
class FallLocationCapture(context: Context, private val handler: Handler) : LocationListener {
    private val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private var callback: ((JSONObject?) -> Unit)? = null
    private var best: Location? = null
    private var startedAt = 0L
    private val timeout = Runnable { finish() }

    fun start(onResult: (JSONObject?) -> Unit) {
        cancel()
        callback = onResult
        startedAt = SystemClock.elapsedRealtimeNanos()
        handler.postDelayed(timeout, 15000)
        var requested = false
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            try {
                if (manager.isProviderEnabled(provider)) {
                    manager.requestLocationUpdates(provider, 1000L, 0f, this, Looper.getMainLooper())
                    requested = true
                }
            } catch (_: SecurityException) { /* Denied or approximate-only permission. */ }
            catch (_: IllegalArgumentException) { /* Provider unavailable on this device. */ }
        }
        if (!requested) finish()
    }

    override fun onLocationChanged(location: Location) {
        if (callback == null || location.elapsedRealtimeNanos < startedAt || !location.hasAccuracy()
            || !location.latitude.isFinite() || !location.longitude.isFinite()
            || !location.accuracy.isFinite() || location.accuracy < 0) return
        if (best == null || location.accuracy < best!!.accuracy) best = location
        if (location.accuracy <= 25f) finish()
    }

    private fun finish() {
        val result = best?.let { location ->
            JSONObject().put("latitude", location.latitude).put("longitude", location.longitude)
                .put("accuracy_m", location.accuracy.toDouble()).put("captured_at",
                    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
                        timeZone = TimeZone.getTimeZone("UTC")
                    }.format(Date(location.time)))
        }
        val done = callback
        cancel()
        done?.invoke(result)
    }

    fun cancel() {
        handler.removeCallbacks(timeout)
        try { manager.removeUpdates(this) } catch (_: SecurityException) { }
        callback = null
        best = null
    }

    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}
    @Deprecated("Required for older Android versions")
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
}
