package com.rish.smartroutine.alarm

import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import com.rish.smartroutine.container
import com.rish.smartroutine.data.Reminder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.ConcurrentHashMap

/** What is ringing right now — observed by the full-screen AlarmActivity. */
data class RingingAlarm(val reminder: Reminder, val day: Long)

object AlarmState {
    private val _ringing = MutableStateFlow<RingingAlarm?>(null)
    val ringing: StateFlow<RingingAlarm?> = _ringing.asStateFlow()
    internal fun set(value: RingingAlarm?) { _ringing.value = value }
}

/**
 * Foreground service that plays the reminder's sound (unless Vibrate-Only) and its vibration
 * pattern in a loop, shows the full-screen notification, and auto-silences after [RING_TIMEOUT_MS].
 */
class AlarmService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var player: MediaPlayer? = null
    private var timeoutJob: Job? = null
    private var volumeJob: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val id = intent?.getLongExtra(AlarmReceiver.EXTRA_ID, -1L) ?: -1L
        val day = intent?.getLongExtra(AlarmReceiver.EXTRA_DAY, 0L) ?: 0L
        val preloadedReminder = preloaded.remove(id)

        // Must go foreground immediately. Posting the real alarm notification first time (not as an
        // update) is what makes Android launch the full-screen intent over the lock screen.
        val first = preloadedReminder?.let { NotificationHelper.buildRinging(this, it, day) }
            ?: NotificationHelper.buildPlaceholder(this)
        ServiceCompat.startForeground(
            this,
            NotificationHelper.ID_RINGING,
            first,
            if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SYSTEM_EXEMPTED else 0,
        )
        if (id < 0) { stopSelf(); return START_NOT_STICKY }

        acquireWakeLock()
        if (preloadedReminder != null) {
            startRinging(preloadedReminder, day, alreadyPosted = true)
        } else {
            scope.launch {
                val reminder = withContext(Dispatchers.IO) { container.repository.getReminder(id) }
                if (reminder == null) { stopSelf(); return@launch }
                startRinging(reminder, day, alreadyPosted = false)
            }
        }
        return START_NOT_STICKY
    }

    @SuppressLint("MissingPermission")
    private fun startRinging(r: Reminder, day: Long, alreadyPosted: Boolean) {
        // A new alarm replaces whatever was ringing before; the old one becomes "missed".
        AlarmState.ringing.value?.let { old ->
            if (old.reminder.id != r.id) NotificationHelper.postMissed(this, old.reminder, old.day)
        }
        stopPlayback()

        AlarmState.set(RingingAlarm(r, day))
        if (!alreadyPosted) {
            try {
                NotificationManagerCompat.from(this)
                    .notify(NotificationHelper.ID_RINGING, NotificationHelper.buildRinging(this, r, day))
            } catch (_: SecurityException) { /* notifications denied; sound + vibration still work */ }
        }

        Haptics.play(this, r.vibrationPattern, repeat = true)
        if (!r.vibrateOnly) playSound(r.ringtoneUri)

        timeoutJob = scope.launch {
            delay(RING_TIMEOUT_MS)
            NotificationHelper.postMissed(this@AlarmService, r, day)
            stopSelf()
        }
    }

    private fun playSound(uriString: String?) {
        val uri: Uri = uriString?.let(Uri::parse)
            ?: RingtoneManager.getActualDefaultRingtoneUri(this, RingtoneManager.TYPE_ALARM)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
        player = createPlayer(uri) ?: createPlayer(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))
        player?.let { mp ->
            mp.setVolume(0.15f, 0.15f)
            mp.start()
            // Gentle fade-in over ~10 seconds.
            volumeJob = scope.launch {
                var v = 0.15f
                while (v < 1f) { delay(500); v = (v + 0.05f).coerceAtMost(1f); runCatching { mp.setVolume(v, v) } }
            }
        }
    }

    private fun createPlayer(uri: Uri): MediaPlayer? = try {
        MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            setDataSource(this@AlarmService, uri)
            isLooping = true
            prepare()
        }
    } catch (e: Exception) {
        Log.w(TAG, "Cannot play $uri", e); null
    }

    private fun stopPlayback() {
        timeoutJob?.cancel(); volumeJob?.cancel()
        player?.runCatching { stop(); release() }
        player = null
        Haptics.stop(this)
    }

    @Suppress("WakelockTimeout")
    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SmartRoutine:ringing")
            .apply { acquire(RING_TIMEOUT_MS + 10_000) }
    }

    override fun onDestroy() {
        stopPlayback()
        AlarmState.set(null)
        NotificationManagerCompat.from(this).cancel(NotificationHelper.ID_RINGING)
        wakeLock?.runCatching { if (isHeld) release() }
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "AlarmService"
        private const val RING_TIMEOUT_MS = 3 * 60_000L

        /** Reminder handed over from AlarmReceiver (same process) so no DB read is needed. */
        private val preloaded = ConcurrentHashMap<Long, Reminder>()

        fun startIntent(context: Context, reminder: Reminder, day: Long): Intent {
            preloaded[reminder.id] = reminder
            return Intent(context, AlarmService::class.java)
                .putExtra(AlarmReceiver.EXTRA_ID, reminder.id)
                .putExtra(AlarmReceiver.EXTRA_DAY, day)
        }

        /** stopService has no background restrictions, so it is safe from receivers. */
        fun stop(context: Context) {
            context.stopService(Intent(context, AlarmService::class.java))
        }
    }
}
