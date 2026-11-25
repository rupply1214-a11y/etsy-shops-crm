package com.rish.smartroutine.alarm

import com.rish.smartroutine.data.IntervalReminder
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.data.RepeatType
import com.rish.smartroutine.data.hasDay
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId

/** Pure functions (no Android APIs) so they are easy to unit test. */
object ScheduleMath {

    /** Next time this reminder should ring strictly after [now], or null if it never will. */
    fun nextOccurrence(r: Reminder, now: LocalDateTime): LocalDateTime? {
        val time = LocalTime.of(r.hour, r.minute)
        if (r.repeatType == RepeatType.ONCE) {
            val day = r.onceDateEpochDay?.let(LocalDate::ofEpochDay) ?: return null
            return day.atTime(time).takeIf { it.isAfter(now) }
        }
        if (r.effectiveMask == 0) return null
        for (offset in 0L..7L) {
            val date = now.toLocalDate().plusDays(offset)
            if (!r.effectiveMask.hasDay(date.dayOfWeek)) continue
            val candidate = date.atTime(time)
            if (candidate.isAfter(now)) return candidate
        }
        return null
    }

    /** For a one-time reminder: today if the time is still ahead, otherwise tomorrow. */
    fun onceDateFor(hour: Int, minute: Int, now: LocalDateTime): LocalDate {
        val today = now.toLocalDate()
        return if (today.atTime(hour, minute).isAfter(now)) today else today.plusDays(1)
    }

    /** Next nudge strictly after [now], aligned to start + k * interval inside [start, end]. */
    fun nextIntervalFire(i: IntervalReminder, now: LocalDateTime): LocalDateTime? {
        val step = i.intervalMinutes.toLong()
        if (step <= 0 || i.daysMask == 0 || i.endMinuteOfDay <= i.startMinuteOfDay) return null
        for (offset in 0L..7L) {
            val date = now.toLocalDate().plusDays(offset)
            if (!i.daysMask.hasDay(date.dayOfWeek)) continue
            val start = date.atStartOfDay().plusMinutes(i.startMinuteOfDay.toLong())
            val end = date.atStartOfDay().plusMinutes(i.endMinuteOfDay.toLong())
            val candidate = if (now.isBefore(start)) {
                start
            } else {
                val elapsed = Duration.between(start, now).toMinutes()
                start.plusMinutes((elapsed / step + 1) * step)
            }
            if (candidate.isAfter(now) && !candidate.isAfter(end)) return candidate
        }
        return null
    }

    fun LocalDateTime.toEpochMillis(): Long =
        atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
}
