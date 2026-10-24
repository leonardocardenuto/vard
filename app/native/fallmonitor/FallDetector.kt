package com.vard.app.fallmonitor

import kotlin.math.*

/** Phone must be carried on the body. Values are Android SI units (m/s²).
 * Initial heuristics, not a validated medical classifier. */
class FallDetector(private val config: FallDetectorConfig = FallDetectorConfig()) {
    private var gravity = doubleArrayOf(0.0, 9.81, 0.0)
    private var before = gravity.copyOf()
    private var initialized = false
    private var lowAt = -10000L
    private var impactAt = -10000L
    private var stillAt = 0L
    private var cooldownUntil = 0L
    private var peak = 0.0
    private var hadFreeFall = false

    fun reset(now: Long): Long {
        impactAt = -10000L
        lowAt = -10000L
        stillAt = 0
        cooldownUntil = now + config.rearmDelayMs
        return cooldownUntil
    }

    fun sample(x: Double, y: Double, z: Double, now: Long): Double? {
        val vector = doubleArrayOf(x, y, z)
        val magnitude = sqrt(x*x + y*y + z*z) / 9.80665
        if (!initialized) { gravity = vector.copyOf(); initialized = true }
        if (now < cooldownUntil) {
            if (magnitude in config.gravityMinG..config.gravityMaxG) {
                for (i in gravity.indices) gravity[i] = gravity[i]*config.gravityAlpha + vector[i]*(1.0-config.gravityAlpha)
            }
            return null
        }
        if (magnitude < config.freeFallG) lowAt = now
        if (impactAt < 0 && magnitude >= config.impactG) {
            before = gravity.copyOf()
            impactAt = now
            peak = magnitude
            hadFreeFall = now - lowAt < config.freeFallWindowMs
            stillAt = 0
        }
        if (impactAt >= 0) {
            peak = max(peak, magnitude)
            if (now - impactAt > config.impactWindowMs) { impactAt = -10000L; stillAt = 0 }
            else {
                val still = abs(magnitude - 1.0) < config.stillnessToleranceG
                if (still) { if (stillAt == 0L) stillAt = now } else stillAt = 0
                val normBefore = sqrt(before.sumOf { it*it })
                val normNow = sqrt(vector.sumOf { it*it })
                val cosine = (before.indices.sumOf { before[it]*vector[it] } /
                    max(0.0001, normBefore*normNow)).coerceIn(-1.0, 1.0)
                val angle = acos(cosine) * 180.0 / PI
                if (stillAt > 0 && now - stillAt >= config.stillnessDurationMs && (hadFreeFall || angle >= config.postureAngleDegrees)) {
                    val result = peak
                    reset(now)
                    return result
                }
            }
        }
        if (magnitude in config.gravityMinG..config.gravityMaxG) {
            for (i in gravity.indices) gravity[i] = gravity[i]*config.gravityAlpha + vector[i]*(1.0-config.gravityAlpha)
        }
        return null
    }
}
