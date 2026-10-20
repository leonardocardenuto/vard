package com.vard.app.fallmonitor

import android.app.*
import android.content.*
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
        @Volatile var running = false
        @Volatile var lastSample = 0L
        @Volatile var lastError = ""
        @Volatile var rearmUntil = 0L
    }
    private lateinit var store: MonitorStore
    private lateinit var sensors: SensorManager
    private lateinit var notifications: NotificationManager
    private val handler = Handler(Looper.getMainLooper())
    private val network = Executors.newSingleThreadExecutor()
    private val sending = AtomicBoolean(false)
    private val detector = FallDetector()
    private var wakeLock: PowerManager.WakeLock? = null
    private var pendingDeadline = 0L
    @Volatile private var alive = true
    private val tick = object : Runnable {
        override fun run() {
            if (pendingDeadline > 0) {
                if (System.currentTimeMillis() >= pendingDeadline) enqueuePending()
                else showPending()
            }
            if (running) flush()
            handler.postDelayed(this, 1000)
        }
    }
    private var lastSync = 0L

    override fun onCreate() {
        super.onCreate()
        store = MonitorStore(this)
        sensors = getSystemService(SENSOR_SERVICE) as SensorManager
        notifications = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            notifications.createNotificationChannel(NotificationChannel("vard-monitor", "Monitoramento de quedas", NotificationManager.IMPORTANCE_LOW))
            notifications.createNotificationChannel(NotificationChannel("vard-fall", "Possível queda", NotificationManager.IMPORTANCE_HIGH).apply {
                enableVibration(true); description = "Confirme se você está bem após uma possível queda"
            })
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) { stopMonitoring(); return START_NOT_STICKY }
        if (!store.prefs.getBoolean("enabled", false) || store.token() == null) {
            stopSelf(); return START_NOT_STICKY
        }
        startForeground(710, monitorNotification())
        if (intent?.action == CANCEL) cancelPending()
        if (!running) {
            val sensor = sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
            if (sensor == null) { lastError = "Este aparelho não possui acelerômetro."; stopMonitoring(); return START_NOT_STICKY }
            running = sensors.registerListener(this, sensor, 20000)
            if (!running) { lastError = "Não foi possível iniciar o sensor."; stopMonitoring(); return START_NOT_STICKY }
            wakeLock = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK, "VARD:FallMonitor").apply { acquire() }
            pendingDeadline = store.prefs.getLong("pendingDeadline", 0)
            handler.removeCallbacks(tick)
            handler.post(tick)
            lastError = ""
        }
        return START_STICKY
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
        notifications.notify(711, NotificationCompat.Builder(this, "vard-fall")
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
        pendingDeadline = System.currentTimeMillis() + 20000
        store.prefs.edit().putLong("pendingDeadline", pendingDeadline)
            .putString("pendingEvent", JSONObject().put("event_id", UUID.randomUUID().toString())
                .put("occurred_at", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", java.util.Locale.US).apply {
                    timeZone = TimeZone.getTimeZone("UTC")
                }.format(Date())).put("peak_g", peak).toString()).commit()
        Log.i("VardFallMonitor", "Possible fall detected; confirmation pending")
        showPending()
    }

    fun cancelPending() {
        pendingDeadline = 0
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
        running = false; lastSample = 0; rearmUntil = 0
        sensors.unregisterListener(this)
        handler.removeCallbacksAndMessages(null)
        network.shutdownNow()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    override fun onBind(intent: Intent?): IBinder? = null
}
