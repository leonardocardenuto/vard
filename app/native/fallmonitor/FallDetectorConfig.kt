package com.vard.app.fallmonitor

/** Defaults match the seeded database; production always loads /configuration before starting sensors. */
data class FallDetectorConfig(
    val impactG: Double = 2.5,
    val freeFallG: Double = 0.6,
    val freeFallWindowMs: Long = 1500,
    val impactWindowMs: Long = 8000,
    val stillnessToleranceG: Double = 0.18,
    val stillnessDurationMs: Long = 2500,
    val postureAngleDegrees: Double = 35.0,
    val rearmDelayMs: Long = 10000,
    val confirmationTimeoutMs: Long = 20000,
    val gravityMinG: Double = 0.7,
    val gravityMaxG: Double = 1.3,
    val gravityAlpha: Double = 0.9,
)
