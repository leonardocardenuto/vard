package com.vard.app.fallmonitor

/** A cancelled confirmation can never expire into a report. */
class FallConfirmation {
    var deadline: Long = 0
        private set
    fun start(now: Long, timeout: Long) { deadline = now + timeout }
    fun restore(savedDeadline: Long) { deadline = savedDeadline }
    fun cancel() { deadline = 0 }
    fun isExpired(now: Long): Boolean = deadline > 0 && now >= deadline
}
