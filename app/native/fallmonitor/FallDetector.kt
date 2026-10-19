package com.vard.app.fallmonitor

import kotlin.math.*

/** Phone must be carried on the body. Values are Android SI units (m/s²).
 * Initial heuristics, not a validated medical classifier. */
class FallDetector {
    private var gravity = doubleArrayOf(0.0, 9.81, 0.0)
    private var before = gravity.copyOf()
    private var initialized = false
    private var lowAt = -10000L
    private var impactAt = -10000L
    private var stillAt = 0L
    private var cooldownUntil = 0L
    private var peak = 0.0
    private var hadFreeFall = false

    fun reset(now: Long) {
        impactAt = -10000L
        lowAt = -10000L
        stillAt = 0
        cooldownUntil = now + 60000
    }

    fun sample(x: Double, y: Double, z: Double, now: Long): Double? {
        val vector = doubleArrayOf(x, y, z)
        val magnitude = sqrt(x*x + y*y + z*z) / 9.80665
        if (!initialized) { gravity = vector.copyOf(); initialized = true }
        if (now < cooldownUntil) return null
        if (magnitude < 0.6) lowAt = now
        if (impactAt < 0 && magnitude >= 2.5) {
            before = gravity.copyOf()
            impactAt = now
            peak = magnitude
            hadFreeFall = now - lowAt < 1500
            stillAt = 0
        }
        if (impactAt >= 0) {
            peak = max(peak, magnitude)
            if (now - impactAt > 8000) { impactAt = -10000L; stillAt = 0 }
            else {
                val still = abs(magnitude - 1.0) < 0.18
                if (still) { if (stillAt == 0L) stillAt = now } else stillAt = 0
                val normBefore = sqrt(before.sumOf { it*it })
                val normNow = sqrt(vector.sumOf { it*it })
                val cosine = (before.indices.sumOf { before[it]*vector[it] } /
                    max(0.0001, normBefore*normNow)).coerceIn(-1.0, 1.0)
                val angle = acos(cosine) * 180.0 / PI
                if (stillAt > 0 && now - stillAt >= 2500 && (hadFreeFall || angle >= 35)) {
                    val result = peak
                    reset(now)
                    return result
                }
            }
        }
        if (magnitude in 0.7..1.3) {
            for (i in gravity.indices) gravity[i] = gravity[i]*0.9 + vector[i]*0.1
        }
        return null
    }
}
