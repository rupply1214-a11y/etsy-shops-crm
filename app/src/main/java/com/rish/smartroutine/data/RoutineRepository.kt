package com.rish.smartroutine.data

import com.rish.smartroutine.alarm.AlarmScheduler
import com.rish.smartroutine.alarm.ScheduleMath
import kotlinx.coroutines.flow.Flow
import java.time.LocalDate
import java.time.LocalDateTime

/**
 * Single source of truth. Every write also re-arms or cancels the matching system alarm,
 * so the database and AlarmManager never drift apart.
 */
class RoutineRepository(
    private val db: AppDatabase,
    private val scheduler: AlarmScheduler,
) {
    private val reminders = db.reminderDao()
    private val completions = db.completionDao()
    private val intervals = db.intervalDao()

    // ----- Reminders -----

    fun observeReminders(): Flow<List<Reminder>> = reminders.observeAll()

    fun observeCompletedIds(day: LocalDate): Flow<List<Long>> =
        completions.observeCompletedIds(day.toEpochDay())

    suspend fun getReminder(id: Long): Reminder? = reminders.getById(id)

    /** Insert or update, then schedule. Returns the saved reminder (with id). */
    suspend fun saveReminder(input: Reminder): Reminder {
        val normalized = if (input.repeatType == RepeatType.ONCE) {
            input.copy(onceDateEpochDay = ScheduleMath.onceDateFor(input.hour, input.minute, LocalDateTime.now()).toEpochDay())
        } else input.copy(onceDateEpochDay = null)

        val saved = if (normalized.id == 0L) {
            normalized.copy(id = reminders.insert(normalized))
        } else {
            reminders.update(normalized); normalized
        }
        scheduler.schedule(saved)
        return saved
    }

    /** Re-insert a deleted reminder with its original id (used by "Undo"). */
    suspend fun restoreReminder(reminder: Reminder) {
        reminders.insert(reminder)
        scheduler.schedule(reminder)
    }

    suspend fun setReminderEnabled(reminder: Reminder, enabled: Boolean) {
        reminders.setEnabled(reminder.id, enabled)
        val updated = reminder.copy(enabled = enabled)
        if (enabled && updated.repeatType == RepeatType.ONCE &&
            ScheduleMath.nextOccurrence(updated, LocalDateTime.now()) == null
        ) {
            // Re-enabling an old one-time reminder: move it to the next upcoming slot.
            saveReminder(updated)
        } else {
            scheduler.schedule(updated)
        }
    }

    suspend fun deleteReminder(reminder: Reminder) {
        scheduler.cancel(reminder.id)
        reminders.delete(reminder)
    }

    suspend fun isCompleted(id: Long, day: Long) = completions.isCompleted(id, day)

    suspend fun markDone(id: Long, day: Long) = completions.insert(CompletionLog(id, day))

    suspend fun setCompleted(id: Long, day: LocalDate, done: Boolean) {
        if (done) completions.insert(CompletionLog(id, day.toEpochDay()))
        else completions.delete(id, day.toEpochDay())
    }

    // ----- Interval nudges -----

    fun observeIntervals(): Flow<List<IntervalReminder>> = intervals.observeAll()

    suspend fun getInterval(id: Long): IntervalReminder? = intervals.getById(id)

    suspend fun saveInterval(input: IntervalReminder): IntervalReminder {
        val saved = if (input.id == 0L) input.copy(id = intervals.insert(input))
        else { intervals.update(input); input }
        scheduler.scheduleInterval(saved)
        return saved
    }

    suspend fun setIntervalEnabled(item: IntervalReminder, enabled: Boolean) {
        intervals.setEnabled(item.id, enabled)
        scheduler.scheduleInterval(item.copy(enabled = enabled))
    }

    suspend fun deleteInterval(item: IntervalReminder) {
        scheduler.cancelInterval(item.id)
        intervals.delete(item)
    }

    // ----- Maintenance -----

    /** Called after boot, app update, time/timezone change and exact-alarm permission changes. */
    suspend fun rescheduleAll() {
        reminders.getAll().forEach(scheduler::schedule)
        intervals.getAll().forEach { scheduler.scheduleInterval(it) }
        completions.prune(LocalDate.now().minusDays(90).toEpochDay())
    }
}
