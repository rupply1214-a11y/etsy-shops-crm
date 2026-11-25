package com.rish.smartroutine.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import com.rish.smartroutine.container
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.time.LocalDate

/** Entry point for every AlarmManager fire (reminders, snoozes and interval nudges). */
class AlarmReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getLongExtra(EXTRA_ID, -1L)
        if (id < 0) return
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                when (intent.action) {
                    ACTION_REMINDER -> handleReminder(context, intent, id)
                    ACTION_INTERVAL -> handleInterval(context, id)
                }
            } catch (t: Throwable) {
                Log.e(TAG, "Alarm handling failed", t)
            } finally {
                pending.finish()
            }
        }
    }

    private suspend fun handleReminder(context: Context, intent: Intent, id: Long) {
        val repo = context.container.repository
        val reminder = repo.getReminder(id) ?: return
        val isSnooze = intent.getBooleanExtra(EXTRA_SNOOZE, false)
        val day = intent.getLongExtra(EXTRA_DAY, LocalDate.now().toEpochDay())

        // Arm the next occurrence first, so the chain never breaks.
        if (!isSnooze) context.container.scheduler.schedule(reminder)

        if (!reminder.enabled) return
        // Already checked off from the list before it was due → stay quiet.
        if (repo.isCompleted(id, day)) return

        try {
            ContextCompat.startForegroundService(context, AlarmService.startIntent(context, reminder, day))
        } catch (e: Exception) {
            // e.g. ForegroundServiceStartNotAllowedException on aggressive OEM builds.
            Log.w(TAG, "Could not start AlarmService, using fallback notification", e)
            NotificationHelper.postFallback(context, reminder, day)
        }
    }

    private suspend fun handleInterval(context: Context, id: Long) {
        val item = context.container.repository.getInterval(id) ?: return
        context.container.scheduler.scheduleInterval(item) // next nudge
        if (item.enabled) NotificationHelper.postNudge(context, item)
    }

    companion object {
        private const val TAG = "AlarmReceiver"
        const val ACTION_REMINDER = "com.rish.smartroutine.FIRE_REMINDER"
        const val ACTION_INTERVAL = "com.rish.smartroutine.FIRE_INTERVAL"
        const val EXTRA_ID = "id"
        const val EXTRA_DAY = "day"
        const val EXTRA_SNOOZE = "snooze"
    }
}
