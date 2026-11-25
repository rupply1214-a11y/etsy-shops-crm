package com.rish.smartroutine.alarm

import android.content.Context
import android.media.AudioAttributes
import android.os.Build
import android.os.VibrationAttributes
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.rish.smartroutine.data.VibrationPattern

object Haptics {

    fun vibrator(context: Context): Vibrator =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(VibratorManager::class.java).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Vibrator::class.java)
        }

    /**
     * Plays [pattern] with ALARM usage so it still vibrates when the phone is on silent.
     * @param repeat true = loop until [stop] is called (alarm ringing), false = play once (preview).
     */
    fun play(context: Context, pattern: VibrationPattern, repeat: Boolean) {
        val v = vibrator(context)
        if (!v.hasVibrator()) return
        val repeatIndex = if (repeat) 0 else -1
        val effect = if (v.hasAmplitudeControl()) {
            VibrationEffect.createWaveform(pattern.timings, pattern.amplitudes, repeatIndex)
        } else {
            VibrationEffect.createWaveform(pattern.fallbackTimings, repeatIndex)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            v.vibrate(effect, VibrationAttributes.createForUsage(VibrationAttributes.USAGE_ALARM))
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(
                effect,
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build(),
            )
        }
    }

    fun stop(context: Context) = vibrator(context).cancel()
}
