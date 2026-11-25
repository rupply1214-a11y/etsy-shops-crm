package com.rish.smartroutine.alarm

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.rish.smartroutine.R
import com.rish.smartroutine.data.IntervalReminder
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.data.VibrationPattern
import com.rish.smartroutine.ui.MainActivity
import com.rish.smartroutine.ui.alarm.AlarmActivity
import java.time.LocalTime
import java.time.format.DateTimeFormatter

object NotificationHelper {

    /** Silent channel — the AlarmService plays sound + vibration itself (per-reminder settings). */
    const val CH_ALARM = "alarm_ringing"
    /** Used only if the ringing service can't start: lets the system ring + vibrate instead. */
    const val CH_ALARM_FALLBACK = "alarm_fallback"
    const val CH_MISSED = "alarm_missed"
    private const val CH_NUDGE_PREFIX = "nudge_"

    const val ID_RINGING = 1001
    private const val ID_MISSED_BASE = 20_000
    private const val ID_NUDGE_BASE = 30_000

    fun nudgeChannelId(p: VibrationPattern) = CH_NUDGE_PREFIX + p.name.lowercase()

    fun createChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java)
        val alarm = NotificationChannel(CH_ALARM, "Reminders (ringing)", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Full-screen reminder alarms. Sound and vibration are set per reminder inside the app."
            setSound(null, null)
            enableVibration(false)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        val fallback = NotificationChannel(CH_ALARM_FALLBACK, "Reminders (backup alert)", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Used only when the alarm screen can't be shown."
            setSound(
                RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build(),
            )
            enableVibration(true)
            vibrationPattern = VibrationPattern.STRONG_ALERT.fallbackTimings
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        val missed = NotificationChannel(CH_MISSED, "Missed reminders", NotificationManager.IMPORTANCE_DEFAULT).apply {
            setSound(null, null)
            enableVibration(false)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        // One silent channel per vibration pattern for interval nudges (vibrate-only, zero sound).
        val nudges = VibrationPattern.entries.map { p ->
            NotificationChannel(nudgeChannelId(p), "Interval nudge – ${p.label}", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Silent vibration nudges (hydration, posture, breaks)."
                setSound(null, null)
                enableVibration(true)
                vibrationPattern = p.fallbackTimings
            }
        }
        nm.createNotificationChannels(listOf(alarm, fallback, missed) + nudges)
    }

    // ---------- Ringing alarm ----------

    fun alarmActivityIntent(context: Context, reminderId: Long, day: Long): PendingIntent {
        val intent = Intent(context, AlarmActivity::class.java)
            .putExtra(AlarmReceiver.EXTRA_ID, reminderId)
            .putExtra(AlarmReceiver.EXTRA_DAY, day)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_USER_ACTION)
        return PendingIntent.getActivity(
            context, 1, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    fun buildRinging(context: Context, r: Reminder, day: Long, channel: String = CH_ALARM): Notification {
        val fullScreen = alarmActivityIntent(context, r.id, day)
        val timeText = formatTime(r.hour, r.minute)
        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setColor(r.colorArgb.toInt())
            .setContentTitle(r.title)
            .setContentText(r.notes.ifBlank { "Reminder · $timeText" })
            .setStyle(NotificationCompat.BigTextStyle().bigText(r.notes.ifBlank { "Reminder · $timeText" }))
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(fullScreen)
            .setFullScreenIntent(fullScreen, true)
            .addAction(0, "Mark done", actionIntent(context, AlarmActionReceiver.ACTION_DONE, r.id, day))
            .addAction(0, "Snooze ${r.snoozeMinutes}m", actionIntent(context, AlarmActionReceiver.ACTION_SNOOZE, r.id, day, r.snoozeMinutes))
            .addAction(0, "Dismiss", actionIntent(context, AlarmActionReceiver.ACTION_DISMISS, r.id, day))
        applyPrivacy(context, builder, r, channel)
        return builder.build()
    }

    fun buildPlaceholder(context: Context): Notification =
        NotificationCompat.Builder(context, CH_ALARM)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setContentTitle("Reminder")
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()

    /** If the service cannot start (rare OEM restriction), post a loud system-handled notification. */
    fun postFallback(context: Context, r: Reminder, day: Long) =
        notify(context, ID_RINGING, buildRinging(context, r, day, CH_ALARM_FALLBACK))

    // ---------- Missed ----------

    fun postMissed(context: Context, r: Reminder, day: Long) {
        val builder = NotificationCompat.Builder(context, CH_MISSED)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setColor(r.colorArgb.toInt())
            .setContentTitle("Missed: ${r.title}")
            .setContentText("Was due at ${formatTime(r.hour, r.minute)}")
            .setContentIntent(openAppIntent(context))
            .setAutoCancel(true)
            .addAction(0, "Mark done", actionIntent(context, AlarmActionReceiver.ACTION_DONE, r.id, day))
        applyPrivacy(context, builder, r, CH_MISSED)
        notify(context, missedId(r.id), builder.build())
    }

    fun cancelMissed(context: Context, reminderId: Long) =
        NotificationManagerCompat.from(context).cancel(missedId(reminderId))

    private fun missedId(id: Long) = ID_MISSED_BASE + (id % 10_000).toInt()

    // ---------- Interval nudge ----------

    fun postNudge(context: Context, item: IntervalReminder) {
        val n = NotificationCompat.Builder(context, nudgeChannelId(item.vibrationPattern))
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setColor(item.colorArgb.toInt())
            .setContentTitle(item.title)
            .setContentText("Every ${item.intervalMinutes} min · ${formatMinuteOfDay(item.startMinuteOfDay)}–${formatMinuteOfDay(item.endMinuteOfDay)}")
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(openAppIntent(context))
            .setAutoCancel(true)
            .setTimeoutAfter(10 * 60_000L)
            .build()
        notify(context, ID_NUDGE_BASE + (item.id % 10_000).toInt(), n)
    }

    // ---------- Helpers ----------

    /** Lock screen shows only the discreet label; the real title appears after unlocking. */
    private fun applyPrivacy(context: Context, b: NotificationCompat.Builder, r: Reminder, channel: String) {
        if (r.discreetLabel.isBlank()) {
            b.setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            return
        }
        val publicVersion = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setColor(r.colorArgb.toInt())
            .setContentTitle(r.discreetLabel)
            .setContentText(formatTime(r.hour, r.minute))
            .build()
        b.setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setPublicVersion(publicVersion)
    }

    private fun actionIntent(context: Context, action: String, id: Long, day: Long, minutes: Int = 0): PendingIntent {
        val intent = Intent(context, AlarmActionReceiver::class.java)
            .setAction(action)
            .setData(Uri.parse("smartroutine://action/$action/$id"))
            .putExtra(AlarmReceiver.EXTRA_ID, id)
            .putExtra(AlarmReceiver.EXTRA_DAY, day)
            .putExtra(AlarmActionReceiver.EXTRA_MINUTES, minutes)
        return PendingIntent.getBroadcast(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun openAppIntent(context: Context) = PendingIntent.getActivity(
        context, 0, Intent(context, MainActivity::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    @SuppressLint("MissingPermission")
    private fun notify(context: Context, id: Int, n: Notification) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED || android.os.Build.VERSION.SDK_INT < 33
        ) {
            NotificationManagerCompat.from(context).notify(id, n)
        }
    }

    private val timeFmt = DateTimeFormatter.ofPattern("h:mm a")
    fun formatTime(hour: Int, minute: Int): String = LocalTime.of(hour, minute).format(timeFmt)
    fun formatMinuteOfDay(m: Int): String = formatTime((m / 60) % 24, m % 60)
}
