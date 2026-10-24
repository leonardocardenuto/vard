package com.vard.app.fallmonitor

import org.junit.Assert.*
import org.junit.Test

class FallConfirmationTest {
    @Test fun safeConfirmationDoesNotExpireOrReportAfterDeadlineOrRestart() {
        val confirmation = FallConfirmation()
        confirmation.start(1000, 20000)
        assertFalse(confirmation.isExpired(20999))
        confirmation.cancel() // Estou bem, including immediately before the timeout tick.
        assertFalse(confirmation.isExpired(21000))
        assertFalse(confirmation.isExpired(90000))
        val restored = FallConfirmation()
        restored.restore(confirmation.deadline)
        assertFalse(restored.isExpired(90000))
    }

    @Test fun onlyUncancelledFallTimesOutAndNextFallCanStillNotify() {
        val confirmation = FallConfirmation()
        confirmation.start(1000, 30000)
        assertFalse(confirmation.isExpired(21000))
        assertTrue(confirmation.isExpired(31000))
        confirmation.cancel()
        confirmation.start(40000, 30000)
        assertFalse(confirmation.isExpired(69999))
        assertTrue(confirmation.isExpired(70000))
    }
}
