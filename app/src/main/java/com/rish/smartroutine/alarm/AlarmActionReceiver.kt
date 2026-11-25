package com.rish.smartroutine.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.rish.smartroutine.container
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Shared logic for Done / Snooze / Dismiss, used by notification buttons and the alarm screen. */
object AlarmActions {
    suspend fun done(context: Context, id: Long, day: Long) {
        context.container.repository.markDone(id, day)
        AlarmService.stop(context)
        NotificationHelper.cancelMissed(context, id)
    }

    fun snooze(context: Context, id: Long, day: Long, minutes: Int) {
        context.container.scheduler.scheduleSnooze(id, day, minutes)
        AlarmService.stop(context)
    }

    fun dismiss(context: Context) = AlarmService.stop(context)
}

class AlarmActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getLongExtra(AlarmReceiver.EXTRA_ID, -1L)
        val day = intent.getLongExtra(AlarmReceiver.EXTRA_DAY, 0L)
        if (id < 0) return
        when (intent.action) {
            ACTION_DONE -> {
                val pending = goAsync()
                CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
                    try { AlarmActions.done(context, id, day) } finally { pending.finish() }
                }
            }
            ACTION_SNOOZE -> AlarmActions.snooze(
                context, id, day, intent.getIntExtra(EXTRA_MINUTES, 10).takeIf { it > 0 } ?: 10,
            )
            ACTION_DISMISS -> AlarmActions.dismiss(context)
        }
    }

    companion object {
        const val ACTION_DONE = "com.rish.smartroutine.ACTION_DONE"
        const val ACTION_SNOOZE = "com.rish.smartroutine.ACTION_SNOOZE"
        const val ACTION_DISMISS = "com.rish.smartroutine.ACTION_DISMISS"
        const val EXTRA_MINUTES = "minutes"
    }
}
