package com.vard.app.fallmonitor

import android.app.*
import android.content.*
import android.Manifest
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.LocationManager
import android.hardware.*
import android.os.*
import android.util.Log
import androidx.core.app.NotificationCompat
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.TimeZone
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import org.json.JSONArray
import org.json.JSONObject

class FallMonitorService : Service(), SensorEventListener {
    companion object {
        const val CANCEL = "com.vard.app.fallmonitor.CANCEL"
        const val STOP = "com.vard.app.fallmonitor.STOP"
        @Volatile var instance: FallMonitorService? = null
        @Volatile var starting = false
        @Volatile var running = false
        @Volatile var locationReady = false
        @Volatile var lastSample = 0L
        @Volatile var lastError = ""
        @Volatile var rearmUntil = 0L
    }
    private lateinit var store: MonitorStore
    private lateinit var sensors: SensorManager
    private lateinit var addressResolver: FallAddressResolver
    private lateinit var locationCapture: FallLocationCapture
    private lateinit var notifications: NotificationManager
    private val handler = Handler(Looper.getMainLooper())
    private val network = Executors.newSingleThreadExecutor()
    private val sending = AtomicBoolean(false)
    private var config = FallDetectorConfig()
    private var detector = FallDetector(config)
    private var wakeLock: PowerManager.WakeLock? = null
    private val confirmation = FallConfirmation()
    private var pendingDeadline: Long
        get() = confirmation.deadline
        set(value) { confirmation.restore(value) }
    @Volatile private var alive = true
    private val tick = object : Runnable {
        override fun run() {
            if (pendingDeadline > 0) {
                if (confirmation.isExpired(System.currentTimeMillis())) enqueuePending()
                else showPending()
            }
            if (running) flush()
            handler.postDelayed(this, 1000)
        }
    }
    private var lastSync = 0L

    override fun onCreate() {
        super.onCreate()
        instance = this
        store = MonitorStore(this)
        addressResolver = FallAddressResolver(this)
        locationCapture = FallLocationCapture(this, handler)
        sensors = getSystemService(SENSOR_SERVICE) as SensorManager
        notifications = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            notifications.createNotificationChannel(NotificationChannel("vard-monitor", "Monitoramento de quedas", NotificationManager.IMPORTANCE_LOW))
            FallNotificationSound.register(this)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) { stopMonitoring(); return START_NOT_STICKY }
        if (!store.prefs.getBoolean("enabled", false) || store.token() == null) {
            stopSelf(); return START_NOT_STICKY
        }
        // Only upgrade to location while the activity is visible. Boot and cancel
        // actions keep the sensor service working without while-in-use access.
        if (!running || intent?.getBooleanExtra("fromVisibleApp", false) == true) {
            val permission = checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            locationReady = permission && intent?.getBooleanExtra("fromVisibleApp", false) == true
        }
        if (Build.VERSION.SDK_INT >= 29) {
            val baseType = if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0
            try {
                startForeground(710, monitorNotification(), baseType or
                    (if (locationReady) ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION else 0))
            } catch (_: SecurityException) {
                locationReady = false
                startForeground(710, monitorNotification(), baseType)
            }
        } else startForeground(710, monitorNotification())
        if (intent?.action == CANCEL) cancelPending()
        if (!running && !starting) {
            starting = true
            lastError = ""
            network.execute {
                try {
                    val loaded = loadConfiguration()
                    handler.post {
                        starting = false
                        if (!alive || !store.prefs.getBoolean("enabled", false)) return@post
                        config = loaded
                        detector = FallDetector(config)
                        beginMonitoring()
                    }
                } catch (_: Exception) {
                    handler.post {
                        starting = false
                        if (!alive) return@post
                        lastError = "Não foi possível buscar a configuração da proteção. Conecte-se e ative novamente."
                        stopMonitoring()
                    }
                }
            }
        }
        return START_STICKY
    }

    private fun beginMonitoring() {
        val sensor = sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        if (sensor == null) { lastError = "Este aparelho não possui acelerômetro."; stopMonitoring(); return }
        running = sensors.registerListener(this, sensor, 20000)
        if (!running) { lastError = "Não foi possível iniciar o sensor."; stopMonitoring(); return }
        wakeLock = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK, "VARD:FallMonitor").apply { acquire() }
        pendingDeadline = store.prefs.getLong("pendingDeadline", 0)
        handler.removeCallbacks(tick)
        handler.post(tick)
        lastError = ""
    }

    private fun loadConfiguration(): FallDetectorConfig {
        val base = store.prefs.getString("baseUrl", "")!!
        val connection = URL(base + "/mobile-monitor/configuration").openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 10000; connection.readTimeout = 10000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer ${store.token()}")
            check(connection.responseCode in 200..299) { "Configuration unavailable" }
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            return FallDetectorConfig(
                impactG = json.getDouble("impact_g"), freeFallG = json.getDouble("free_fall_g"),
                freeFallWindowMs = json.getLong("free_fall_window_ms"), impactWindowMs = json.getLong("impact_window_ms"),
                stillnessToleranceG = json.getDouble("stillness_tolerance_g"), stillnessDurationMs = json.getLong("stillness_duration_ms"),
                postureAngleDegrees = json.getDouble("posture_angle_degrees"), rearmDelayMs = json.getLong("rearm_delay_ms"),
                confirmationTimeoutMs = json.getLong("confirmation_timeout_ms"), gravityMinG = json.getDouble("gravity_min_g"),
                gravityMaxG = json.getDouble("gravity_max_g"), gravityAlpha = json.getDouble("gravity_alpha"),
            )
        } finally { connection.disconnect() }
    }

    private fun launchIntent(): PendingIntent = PendingIntent.getActivity(this, 0,
        packageManager.getLaunchIntentForPackage(packageName), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun cancelIntent(): PendingIntent = PendingIntent.getService(this, 1,
        Intent(this, FallMonitorService::class.java).setAction(CANCEL), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun monitorNotification(): Notification = NotificationCompat.Builder(this, "vard-monitor")
        .setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("VARD · Monitoramento ativo")
        .setContentText("Detectando possíveis quedas pelo celular")
        .setContentIntent(launchIntent()).setOngoing(true).build()

    private fun showPending() {
        val seconds = ((pendingDeadline - System.currentTimeMillis()) / 1000 + 1).coerceAtLeast(0)
        notifications.notify(711, NotificationCompat.Builder(this, FallNotificationSound.CHANNEL_ID)
            .setSound(FallNotificationSound.uri(this))
            .setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle("Você está bem?")
            .setContentText("Possível queda. Avisaremos seu espaço em ${seconds}s.")
            .setContentIntent(launchIntent()).setOngoing(true).setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH).addAction(0, "Estou bem!", cancelIntent()).build())
    }

    override fun onSensorChanged(event: SensorEvent) {
        lastSample = SystemClock.elapsedRealtime()
        if (pendingDeadline > 0) return
        val peak = detector.sample(event.values[0].toDouble(), event.values[1].toDouble(),
            event.values[2].toDouble(), event.timestamp / 1000000) ?: return
        confirmation.start(System.currentTimeMillis(), config.confirmationTimeoutMs)
        store.prefs.edit().putLong("pendingDeadline", pendingDeadline)
            .putString("pendingEvent", JSONObject().put("event_id", UUID.randomUUID().toString())
                .put("occurred_at", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", java.util.Locale.US).apply {
                    timeZone = TimeZone.getTimeZone("UTC")
                }.format(Date())).put("peak_g", peak).toString()).commit()
        Log.i("VardFallMonitor", "Possible fall detected; confirmation pending")
        if (locationReady) {
            val pendingId = JSONObject(store.prefs.getString("pendingEvent", "{}")!!).getString("event_id")
            locationCapture.start { coordinates ->
                val raw = store.prefs.getString("pendingEvent", null)
                if (raw != null && coordinates != null) {
                    val pending = JSONObject(raw)
                    if (pending.optString("event_id") == pendingId) {
                        pending.put("coordinates", coordinates)
                        store.prefs.edit().putString("pendingEvent", pending.toString()).commit()
                    }
                }
            }
        }
        showPending()
    }

    fun cancelPending() {
        locationCapture.cancel()
        confirmation.cancel()
        store.prefs.edit().remove("pendingDeadline").remove("pendingEvent").commit()
        notifications.cancel(711)
        rearmUntil = detector.reset(SystemClock.elapsedRealtime())
    }

    private fun enqueuePending() {
        val item = store.prefs.getString("pendingEvent", null)
        if (item != null) {
            val queue = JSONArray(store.prefs.getString("queue", "[]"))
            queue.put(JSONObject(item))
            store.prefs.edit().putString("queue", queue.toString()).commit()
        }
        cancelPending()
        lastSync = 0
    }

    private fun flush() {
        val now = System.currentTimeMillis()
        if (now - lastSync < 30000 || !sending.compareAndSet(false, true)) return
        lastSync = now
        val queueSnapshot = JSONArray(store.prefs.getString("queue", "[]"))
        network.execute {
            try {
                if (!alive || !store.prefs.getBoolean("enabled", false)) return@execute
                val heartbeat = request("GET", "/mobile-monitor/devices/current", null)
                if (heartbeat == 401 || heartbeat == 403) { unauthorized(); return@execute }
                if (heartbeat !in 200..299) { lastError = "Sem conexão. Os alertas aguardam envio."; return@execute }
                lastError = ""
                for (i in 0 until queueSnapshot.length()) {
                    val item = queueSnapshot.getJSONObject(i)
                    val coordinates = item.optJSONObject("coordinates")
                    if (coordinates != null && coordinates.optString("address").isBlank()) {
                        addressResolver.resolve(coordinates)?.let { address ->
                            coordinates.put("address", address)
                            // Preserve the address for offline retries, alongside the original fix.
                            val resolved = JSONObject(coordinates.toString())
                            handler.post {
                                if (!alive || !store.prefs.getBoolean("enabled", false)) return@post
                                val current = JSONArray(store.prefs.getString("queue", "[]"))
                                for (index in 0 until current.length()) {
                                    val entry = current.getJSONObject(index)
                                    if (entry.optString("event_id") == item.optString("event_id")) {
                                        entry.put("coordinates", resolved)
                                    }
                                }
                                store.prefs.edit().putString("queue", current.toString()).commit()
                            }
                        }
                    }
                    val result = request("POST", "/mobile-monitor/falls", item.toString())
                    if (result == 401 || result == 403) { unauthorized(); break }
                    if (result !in 200..299) { lastError = "Não foi possível enviar o alerta. Tentaremos novamente."; break }
                    handler.post {
                        if (!alive || !store.prefs.getBoolean("enabled", false)) return@post
                        val current = JSONArray(store.prefs.getString("queue", "[]"))
                        val remaining = JSONArray()
                        for (index in 0 until current.length()) {
                            val entry = current.getJSONObject(index)
                            if (entry.getString("event_id") != item.getString("event_id")) remaining.put(entry)
                        }
                        store.prefs.edit().putString("queue", remaining.toString())
                            .putLong("lastSent", System.currentTimeMillis()).commit()
                    }
                }
            } catch (_: Exception) { lastError = "Sem conexão. Os alertas aguardam envio." }
            finally { sending.set(false) }
        }
    }

    private fun unauthorized() {
        lastError = "Acesso ao monitoramento expirou ou foi removido. Entre novamente."
        handler.post { if (alive) stopMonitoring() }
    }

    private fun request(method: String, path: String, body: String?): Int {
        val base = store.prefs.getString("baseUrl", "")!!
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 10000; connection.readTimeout = 10000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer ${store.token()}")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toByteArray()) }
            }
            return connection.responseCode
        } finally { connection.disconnect() }
    }

    private fun stopMonitoring() {
        store.prefs.edit().putBoolean("enabled", false).commit()
        cancelPending()
        running = false
        stopForeground(STOP_FOREGROUND_REMOVE)
        notifications.cancel(711)
        stopSelf()
    }
    override fun onDestroy() {
        alive = false
        starting = false
        instance = null
        locationReady = false
        locationCapture.cancel()
        running = false; lastSample = 0; rearmUntil = 0
        sensors.unregisterListener(this)
        handler.removeCallbacksAndMessages(null)
        network.shutdownNow()
        addressResolver.close()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    override fun onBind(intent: Intent?): IBinder? = null
}
