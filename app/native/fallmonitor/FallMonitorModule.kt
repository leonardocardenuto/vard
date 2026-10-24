package com.vard.app.fallmonitor

import android.content.*
import android.hardware.*
import android.os.*
import com.facebook.react.ReactPackage
import com.facebook.react.bridge.*
import com.facebook.react.uimanager.ViewManager
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import org.json.JSONArray

class FallMonitorModule(private val context: ReactApplicationContext) : ReactContextBaseJavaModule(context) {
    override fun getName() = "VardFallMonitor"
    @ReactMethod fun status(promise: Promise) {
        val prefs = MonitorStore(context).prefs
        promise.resolve(Arguments.createMap().apply {
            putBoolean("running", FallMonitorService.running || FallMonitorService.starting)
            putBoolean("locationReady", FallMonitorService.locationReady)
            putBoolean("enabled", prefs.getBoolean("enabled", false))
            putBoolean("sensorAvailable", (context.getSystemService(Context.SENSOR_SERVICE) as SensorManager)
                .getDefaultSensor(Sensor.TYPE_ACCELEROMETER) != null)
            putBoolean("sensorActive", FallMonitorService.lastSample > 0 && SystemClock.elapsedRealtime() - FallMonitorService.lastSample < 5000)
            putString("workspaceId", prefs.getString("workspaceId", null))
            putString("error", FallMonitorService.lastError)
            putDouble("pendingDeadline", prefs.getLong("pendingDeadline", 0).toDouble())
            val rearmRemaining = (FallMonitorService.rearmUntil - SystemClock.elapsedRealtime()).coerceAtLeast(0)
            putDouble("rearmDeadline", if (rearmRemaining > 0) (System.currentTimeMillis() + rearmRemaining).toDouble() else 0.0)
            putDouble("lastSent", prefs.getLong("lastSent", 0).toDouble())
            putInt("queued", JSONArray(prefs.getString("queue", "[]")).length())
        })
    }
    @ReactMethod fun start(baseUrl: String, token: String, workspaceId: String, promise: Promise) {
        try {
            val store = MonitorStore(context)
            if (FallMonitorService.running || FallMonitorService.starting) throw IllegalStateException("Pare o monitoramento antes de trocar de espaço.")
            store.saveToken(token)
            store.prefs.edit().putString("baseUrl", baseUrl.trimEnd('/')).putString("workspaceId", workspaceId)
                .putBoolean("enabled", true).commit()
            val intent = Intent(context, FallMonitorService::class.java).putExtra("fromVisibleApp", true)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent) else context.startService(intent)
            promise.resolve(null)
        } catch (e: Exception) {
            MonitorStore(context).prefs.edit().putBoolean("enabled", false).commit()
            promise.reject("START_FAILED", e.message, e)
        }
    }
    @ReactMethod fun cancel(promise: Promise) {
        // Serialize with sensor callbacks and the timeout tick. Resolve only after
        // the pending event and location capture have actually been discarded.
        UiThreadUtil.runOnUiThread {
            try {
                val service = FallMonitorService.instance
                if (service != null) service.cancelPending()
                else MonitorStore(context).prefs.edit().remove("pendingDeadline").remove("pendingEvent").commit()
                promise.resolve(null)
            } catch (e: Exception) { promise.reject("CANCEL_FAILED", e.message, e) }
        }
    }
    @ReactMethod fun stop(promise: Promise) {
        val store = MonitorStore(context)
        val token = store.token()
        val base = store.prefs.getString("baseUrl", "")!!
        store.prefs.edit().clear().commit()
        context.stopService(Intent(context, FallMonitorService::class.java))
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager).cancel(711)
        // Revoke only this installation. Works even after the UI access token expires.
        val executor = Executors.newSingleThreadExecutor()
        executor.execute {
            try {
                if (token != null) {
                    val c = URL(base + "/mobile-monitor/devices/current").openConnection() as HttpURLConnection
                    try {
                        c.requestMethod = "DELETE"; c.connectTimeout = 5000; c.readTimeout = 5000
                        c.setRequestProperty("Authorization", "Bearer $token"); c.responseCode
                    } finally { c.disconnect() }
                }
            } catch (_: Exception) { /* Local credentials have already been erased. */ }
            finally { executor.shutdown() }
        }
        promise.resolve(null)
    }
}

class FallMonitorPackage : ReactPackage {
    override fun createNativeModules(context: ReactApplicationContext): List<NativeModule> = listOf(FallMonitorModule(context))
    override fun createViewManagers(context: ReactApplicationContext): List<ViewManager<*, *>> = emptyList()
}

class MonitorBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action !in listOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) return
        if (MonitorStore(context).prefs.getBoolean("enabled", false)) {
            try {
                val service = Intent(context, FallMonitorService::class.java)
                if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(service) else context.startService(service)
            }
            catch (_: Exception) { /* User can resume from the monitor screen if OS blocks boot start. */ }
        }
    }
}
