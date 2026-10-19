package com.vard.app.fallmonitor

import org.junit.Assert.*
import org.junit.Test

class FallDetectorTest {
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
}
