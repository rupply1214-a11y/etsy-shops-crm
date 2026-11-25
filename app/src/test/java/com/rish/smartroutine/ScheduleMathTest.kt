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

    @Test
    fun courses() {
        val today = LocalDate.of(2026, 11, 25)
        val start = today.toEpochDay()
        val routine = StarterRoutine.reminders(today)
        assertEquals("7 tasks", 7, routine.size)
        val duphalac = routine.first { it.title.contains("Duphalac") }
        assertEquals("duphalac end", 1), duphalac.endDate, LocalDate.of(2026, 12)
        assertEquals("duphalac day1 badge-day", 1, duphalac.courseDayOn(today))
        assertEquals("not tapering day5", false, duphalac.isTaperingOn(today.plusDays(4)))
        assertEquals("tapering day6", true, duphalac.isTaperingOn(today.plusDays(5)))
        assertEquals("tapering day7", true, duphalac.isTaperingOn(today.plusDays(6)))
        assertEquals("completed day8", CourseStatus.COMPLETED, duphalac.courseStatus(today.plusDays(7)))
        assertEquals("last alarm on day7", LocalDateTime.of(2026,12,1,19,0), ScheduleMath.nextOccurrence(duphalac, LocalDateTime.of(2026,11,30,20,0)))
        assertEquals("no alarm after end", null, ScheduleMath.nextOccurrence(duphalac, LocalDateTime.of(2026,12,1,19,30)))
        val ext = duphalac.copy(extraDays = 1)
        assertEquals("+1 day end", 2), ext.endDate, LocalDate.of(2026, 12)
        assertEquals("+1 alarm", LocalDateTime.of(2026,12,2,19,0), ScheduleMath.nextOccurrence(ext, LocalDateTime.of(2026,12,1,19,30)))
        val gul = routine.first { it.hour == 11 }
        assertEquals("gulkand end 15d", 9), gul.endDate, LocalDate.of(2026, 12)
        val future = gul.copy(startEpochDay = start + 20)
        assertEquals("future start alarm", LocalDateTime.of(2026,12,15,11,0), ScheduleMath.nextOccurrence(future, LocalDateTime.of(2026,11,25,12,0)))
        assertEquals("upcoming status", CourseStatus.UPCOMING, future.courseStatus(today))
        assertEquals("not scheduled before start", false, future.isScheduledOn(today))
        val hyd = routine.first()
        assertEquals("ongoing", CourseStatus.ONGOING, hyd.courseStatus(today.plusDays(500)))
        assertEquals("ongoing scheduled", true, hyd.isScheduledOn(today.plusDays(500)))
        val end = duphalac.endEpochDay!!; val t = LocalDate.of(2026,12,10).toEpochDay()
        val base = maxOf(end, t - 1); val newEnd = base + 2
        val extra = (newEnd - duphalac.startEpochDay + 1 - duphalac.courseDays!!).toInt()
        val e2 = duphalac.copy(extraDays = extra)
        assertEquals("+2 after completion ends 11 Dec", LocalDate.of(2026,12,11), e2.endDate)
        assertEquals("+2 active again 10 Dec", CourseStatus.ACTIVE, e2.courseStatus(LocalDate.of(2026,12,10)))
    }
}
