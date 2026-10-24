package com.vard.app.fallmonitor

import org.junit.Assert.*
import org.junit.Test

class FallDetectorTest {
    private fun fall(detector: FallDetector, start: Long): List<Double> {
        for (t in start..start + 1000 step 20) detector.sample(0.0, 9.81, 0.0, t)
        detector.sample(0.0, 0.0, 0.0, start + 1020)
        detector.sample(0.0, 0.0, 32.0, start + 1320)
        return (start + 1340..start + 5000 step 20).mapNotNull {
            detector.sample(0.0, 0.0, 9.81, it)
        }
    }

    @Test fun detectsAgainAfterEachConfirmationOrCancellation() {
        val detector = FallDetector()
        var start = 100000L
        for (confirmationDelay in listOf(20000L, 2000L, 20000L)) {
            assertEquals(1, fall(detector, start).size)
            val confirmedAt = start + 5000 + confirmationDelay
            val rearmAt = detector.reset(confirmedAt)
            assertEquals(confirmedAt + 10000, rearmAt)
            for (t in confirmedAt until rearmAt step 20) {
                assertNull(detector.sample(0.0, 0.0, 32.0, t))
            }
            start = rearmAt
        }
        assertEquals(1, fall(detector, start).size)
    }

    @Test fun updatesPostureWhileRearming() {
        val detector = FallDetector()
        for (t in 100000L..101000L step 20) detector.sample(0.0, 9.81, 0.0, t)
        detector.reset(102000)
        for (t in 102020L..112000L step 20) detector.sample(0.0, 0.0, 9.81, t)
        detector.sample(32.0, 0.0, 0.0, 112020)
        val results = (112040L..116000L step 20).mapNotNull {
            detector.sample(9.81, 0.0, 0.0, it)
        }
        assertEquals(1, results.size)
    }

    @Test fun detectsFreeFallImpactAndImmobility() {
        val detector = FallDetector()
        for (t in 100000L..102000L step 20) assertNull(detector.sample(0.0, 9.81, 0.0, t))
        detector.sample(0.0, 0.0, 0.0, 102020)
        detector.sample(0.0, 0.0, 32.0, 102320)
        val results = (102340L..106000L step 20).mapNotNull { detector.sample(0.0, 0.0, 9.81, it) }
        assertEquals(1, results.size)
        assertTrue(results.first() > 3.0)
        for (t in 106020L..110000L step 20) assertNull(detector.sample(0.0, 0.0, 32.0, t))
    }
    @Test fun ignoresDailyMovementsWithoutImpact() {
        val detector = FallDetector()
        for (t in 100000L..120000L step 20) {
            val acceleration = if (t % 1000 < 500) 9.81 else 14.0
            assertNull(detector.sample(0.0, acceleration, 0.0, t))
        }
    }
    @Test fun requiresPostureChangeWithoutFreeFall() {
        val detector = FallDetector()
        for (t in 100000L..102000L step 20) detector.sample(0.0, 9.81, 0.0, t)
        detector.sample(0.0, 32.0, 0.0, 102020)
        for (t in 102040L..111000L step 20) assertNull(detector.sample(0.0, 9.81, 0.0, t))
        detector.sample(0.0, 0.0, 32.0, 112000)
        val results = (112020L..116000L step 20).mapNotNull { detector.sample(0.0, 0.0, 9.81, it) }
        assertEquals(1, results.size)
    }
    @Test fun configuredImpactThresholdChangesDetection() {
        assertEquals(1, fall(FallDetector(FallDetectorConfig(impactG = 2.5)), 100000).size)
        assertTrue(fall(FallDetector(FallDetectorConfig(impactG = 4.0)), 100000).isEmpty())
    }

    @Test fun configuredRearmAndStillnessAreApplied() {
        val detector = FallDetector(FallDetectorConfig(rearmDelayMs = 15000, stillnessDurationMs = 5000))
        assertTrue(fall(detector, 100000).isEmpty())
        assertEquals(135000L, detector.reset(120000))
    }
}
