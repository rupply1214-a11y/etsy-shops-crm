package com.rish.smartroutine

import com.rish.smartroutine.alarm.ScheduleMath
import com.rish.smartroutine.data.*
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime

class ScheduleMathTest {
    @Test
    fun scheduling() {
        val wed = LocalDateTime.of(2026, 11, 25, 10, 30) // Wednesday
        assertEquals("daily later today", LocalDateTime.of(2026,11,25,11,0), ScheduleMath.nextOccurrence(Reminder(hour=11, minute=0), wed))
        assertEquals("daily passed -> tomorrow", LocalDateTime.of(2026,11,26,9,0), ScheduleMath.nextOccurrence(Reminder(hour=9, minute=0), wed))
        assertEquals("exact same minute -> tomorrow", LocalDateTime.of(2026,11,26,10,30), ScheduleMath.nextOccurrence(Reminder(hour=10, minute=30), wed))
        val fri = LocalDateTime.of(2026, 11, 27, 20, 0)
        assertEquals("weekdays fri night -> mon", LocalDateTime.of(2026,11,30,9,0), ScheduleMath.nextOccurrence(Reminder(hour=9, minute=0, repeatType=RepeatType.WEEKDAYS), fri))
        val sunOnly = DayOfWeek.SUNDAY.bit()
        assertEquals("custom sunday", LocalDateTime.of(2026,11,29,8,0), ScheduleMath.nextOccurrence(Reminder(hour=8, minute=0, repeatType=RepeatType.CUSTOM, daysMask=sunOnly), wed))
        assertEquals("custom wed already passed -> next wed", LocalDateTime.of(2026,12,2,8,0), ScheduleMath.nextOccurrence(Reminder(hour=8, minute=0, repeatType=RepeatType.CUSTOM, daysMask=DayOfWeek.WEDNESDAY.bit()), wed))
        assertEquals("custom none", null, ScheduleMath.nextOccurrence(Reminder(repeatType=RepeatType.CUSTOM, daysMask=0), wed))
        val od = ScheduleMath.onceDateFor(9, 0, wed)
        assertEquals("once date tomorrow", LocalDate.of(2026,11,26), od)
        assertEquals("once next", LocalDateTime.of(2026,11,26,9,0), ScheduleMath.nextOccurrence(Reminder(hour=9, minute=0, repeatType=RepeatType.ONCE, onceDateEpochDay=od.toEpochDay()), wed))
        assertEquals("once past -> null", null, ScheduleMath.nextOccurrence(Reminder(hour=9, minute=0, repeatType=RepeatType.ONCE, onceDateEpochDay=LocalDate.of(2026,11,25).toEpochDay()), wed))
        val water = IntervalReminder(intervalMinutes = 45, startMinuteOfDay = 9*60, endMinuteOfDay = 19*60)
        assertEquals("interval before start", LocalDateTime.of(2026,11,25,9,0), ScheduleMath.nextIntervalFire(water, LocalDateTime.of(2026,11,25,7,0)))
        assertEquals("interval mid", LocalDateTime.of(2026,11,25,11,15), ScheduleMath.nextIntervalFire(water, wed))
        assertEquals("interval exactly on slot", LocalDateTime.of(2026,11,25,10,30), ScheduleMath.nextIntervalFire(water, LocalDateTime.of(2026,11,25,9,45)))
        assertEquals("interval last slot 18:45", LocalDateTime.of(2026,11,25,18,45), ScheduleMath.nextIntervalFire(water, LocalDateTime.of(2026,11,25,18,10)))
        assertEquals("interval after end -> tomorrow", LocalDateTime.of(2026,11,26,9,0), ScheduleMath.nextIntervalFire(water, LocalDateTime.of(2026,11,25,18,50)))
        assertEquals("interval weekdays fri eve -> mon", LocalDateTime.of(2026,11,30,9,0), ScheduleMath.nextIntervalFire(water.copy(daysMask=WEEKDAYS), LocalDateTime.of(2026,11,27,20,0)))
        assertEquals("interval bad window", null, ScheduleMath.nextIntervalFire(water.copy(endMinuteOfDay=8*60), wed))
        assertEquals("isScheduledOn weekdays sat", false, Reminder(repeatType=RepeatType.WEEKDAYS).isScheduledOn(LocalDate.of(2026,11,28)))
        assertEquals("lockScreenTitle", "Task", Reminder(title="Pill", discreetLabel="Task").lockScreenTitle())
    }
}
