package com.rish.smartroutine.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.rish.smartroutine.container
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * AlarmManager forgets every alarm on reboot, and a time / timezone change shifts them.
 * Re-arm everything from the database.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try { context.container.repository.rescheduleAll() } finally { pending.finish() }
        }
    }
}
