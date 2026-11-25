package com.rish.smartroutine.alarm

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.util.Log
import com.rish.smartroutine.alarm.ScheduleMath.toEpochMillis
import com.rish.smartroutine.data.IntervalReminder
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.ui.MainActivity
import java.time.LocalDateTime

/**
 * Wraps AlarmManager.
 *
 * Reminders use setAlarmClock(): the most reliable exact API. It fires in Doze, wakes the device
 * and is never deferred. Interval nudges use setExactAndAllowWhileIdle(), which is also exact in
 * Doze (the OS allows roughly one per 9 minutes per app while idle — fine for 15+ min intervals).
 */
class AlarmScheduler(private val context: Context) {

    private val alarmManager = context.getSystemService(AlarmManager::class.java)

    fun canScheduleExact(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms()

    // ---------- Daily / custom reminders ----------

    fun schedule(reminder: Reminder, now: LocalDateTime = LocalDateTime.now()) {
        cancelMain(reminder.id)
        if (!reminder.enabled) return
        val next = ScheduleMath.nextOccurrence(reminder, now) ?: return
        val pi = reminderPendingIntent(reminder.id, next.toLocalDate().toEpochDay(), snooze = false)
        setAlarmClock(next.toEpochMillis(), pi)
        Log.d(TAG, "Reminder ${reminder.id} '${reminder.title}' scheduled for $next")
    }

    fun scheduleSnooze(reminderId: Long, occurrenceDay: Long, minutes: Int) {
        val at = System.currentTimeMillis() + minutes * 60_000L
        setAlarmClock(at, reminderPendingIntent(reminderId, occurrenceDay, snooze = true))
    }

    fun cancel(reminderId: Long) {
        cancelMain(reminderId)
        cancelPending(reminderIntent(reminderId, snooze = true))
    }

    private fun cancelMain(reminderId: Long) = cancelPending(reminderIntent(reminderId, snooze = false))

    // ---------- Interval nudges ----------

    fun scheduleInterval(item: IntervalReminder, now: LocalDateTime = LocalDateTime.now()) {
        cancelInterval(item.id)
        if (!item.enabled) return
        val next = ScheduleMath.nextIntervalFire(item, now) ?: return
        val pi = PendingIntent.getBroadcast(
            context, 0, intervalIntent(item.id),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val at = next.toEpochMillis()
        try {
            if (canScheduleExact()) {
                alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
            } else {
                alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
            }
        } catch (e: SecurityException) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
        }
        Log.d(TAG, "Interval ${item.id} next nudge at $next")
    }

    fun cancelInterval(id: Long) = cancelPending(intervalIntent(id))

    // ---------- Internals ----------

    private fun setAlarmClock(triggerAtMillis: Long, operation: PendingIntent) {
        val showIntent = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        try {
            if (canScheduleExact()) {
                alarmManager.setAlarmClock(AlarmManager.AlarmClockInfo(triggerAtMillis, showIntent), operation)
            } else {
                // Permission revoked (Android 12/12L only): best effort until the user re-grants it.
                alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAtMillis, operation)
            }
        } catch (e: SecurityException) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAtMillis, operation)
        }
    }

    private fun reminderPendingIntent(id: Long, occurrenceDay: Long, snooze: Boolean): PendingIntent =
        PendingIntent.getBroadcast(
            context, 0,
            reminderIntent(id, snooze).putExtra(AlarmReceiver.EXTRA_DAY, occurrenceDay),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

    // The data URI makes every PendingIntent unique per reminder (extras don't count for matching).
    private fun reminderIntent(id: Long, snooze: Boolean) =
        Intent(context, AlarmReceiver::class.java)
            .setAction(AlarmReceiver.ACTION_REMINDER)
            .setData(Uri.parse("smartroutine://reminder/$id/${if (snooze) "snooze" else "main"}"))
            .putExtra(AlarmReceiver.EXTRA_ID, id)
            .putExtra(AlarmReceiver.EXTRA_SNOOZE, snooze)

    private fun intervalIntent(id: Long) =
        Intent(context, AlarmReceiver::class.java)
            .setAction(AlarmReceiver.ACTION_INTERVAL)
            .setData(Uri.parse("smartroutine://interval/$id"))
            .putExtra(AlarmReceiver.EXTRA_ID, id)

    private fun cancelPending(intent: Intent) {
        PendingIntent.getBroadcast(
            context, 0, intent,
            PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE,
        )?.let {
            alarmManager.cancel(it)
            it.cancel()
        }
    }

    companion object { private const val TAG = "AlarmScheduler" }
}
