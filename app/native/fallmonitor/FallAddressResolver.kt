package com.vard.app.fallmonitor

import android.content.Context
import android.location.Address
import android.location.Geocoder
import android.os.Build
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Best-effort reverse geocoding with a bounded wait; a lookup never prevents an alert. */
class FallAddressResolver(context: Context) {
    private val geocoder = Geocoder(context, Locale("pt", "BR"))
    private val legacy = ThreadPoolExecutor(1, 1, 10, TimeUnit.SECONDS, ArrayBlockingQueue<Runnable>(1))
        .apply { allowCoreThreadTimeOut(true) }

    fun resolve(coordinates: JSONObject): String? {
        if (!Geocoder.isPresent()) return null
        return try {
            val latitude = coordinates.getDouble("latitude")
            val longitude = coordinates.getDouble("longitude")
            val addresses = if (Build.VERSION.SDK_INT >= 33) {
                val result = AtomicReference<List<Address>>(emptyList())
                val done = CountDownLatch(1)
                geocoder.getFromLocation(latitude, longitude, 1, object : Geocoder.GeocodeListener {
                    override fun onGeocode(addresses: MutableList<Address>) {
                        result.set(addresses); done.countDown()
                    }
                    override fun onError(errorMessage: String?) { done.countDown() }
                })
                done.await(2, TimeUnit.SECONDS)
                result.get()
            } else {
                @Suppress("DEPRECATION")
                val task = legacy.submit<List<Address>> { geocoder.getFromLocation(latitude, longitude, 1) ?: emptyList() }
                try { task.get(2, TimeUnit.SECONDS) } finally { task.cancel(true) }
            }
            addresses.firstOrNull()?.let { address ->
                (address.getAddressLine(0)?.takeIf { it.isNotBlank() }
                    ?: listOfNotNull(address.thoroughfare, address.subLocality, address.locality,
                        address.subAdminArea, address.adminArea, address.countryName)
                        .filter { it.isNotBlank() }.distinct().joinToString(", "))
                    .trim().take(500).takeIf { it.isNotBlank() }
            }
        } catch (_: Exception) { null }
    }

    fun close() { legacy.shutdownNow() }
}
