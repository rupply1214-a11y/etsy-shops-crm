package com.rish.smartroutine.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import java.time.DayOfWeek
import java.time.LocalDate

/** Bit 0 = Monday ... bit 6 = Sunday. */
const val ALL_DAYS = 0b1111111
const val WEEKDAYS = 0b0011111

fun DayOfWeek.bit(): Int = 1 shl (value - 1)
fun Int.hasDay(day: DayOfWeek): Boolean = this and day.bit() != 0

enum class RepeatType(val label: String) {
    ONCE("Once"), DAILY("Daily"), WEEKDAYS("Weekdays"), CUSTOM("Custom")
}

/**
 * Vibration patterns.
 * [timings]/[amplitudes] are used on devices with amplitude control.
 * [fallbackTimings] is an off/on/off/on... pattern for other devices and for notification channels.
 */
enum class VibrationPattern(
    val label: String,
    val timings: LongArray,
    val amplitudes: IntArray,
    val fallbackTimings: LongArray,
) {
    GENTLE_PULSE(
        "Gentle Pulse",
        longArrayOf(0, 220, 900),
        intArrayOf(0, 90, 0),
        longArrayOf(0, 220, 900),
    ),
    DOUBLE_BUZZ(
        "Double Buzz",
        longArrayOf(0, 250, 150, 250, 1100),
        intArrayOf(0, 200, 0, 200, 0),
        longArrayOf(0, 250, 150, 250, 1100),
    ),
    CONTINUOUS_WAVE(
        "Continuous Wave",
        longArrayOf(300, 300, 300, 300, 300, 300, 300, 300),
        intArrayOf(30, 80, 140, 210, 255, 210, 140, 80),
        longArrayOf(0, 2000, 300),
    ),
    STRONG_ALERT(
        "Strong Alert",
        longArrayOf(0, 600, 200, 600, 200, 600, 800),
        intArrayOf(0, 255, 0, 255, 0, 255, 0),
        longArrayOf(0, 600, 200, 600, 200, 600, 800),
    );
}

@Entity(tableName = "reminders")
data class Reminder(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String = "",
    /** Neutral text shown on the lock screen instead of the real title (blank = no privacy). */
    val discreetLabel: String = "",
    val notes: String = "",
    val hour: Int = 9,
    val minute: Int = 0,
    val repeatType: RepeatType = RepeatType.DAILY,
    val daysMask: Int = ALL_DAYS,
    /** Only used for [RepeatType.ONCE]. */
    val onceDateEpochDay: Long? = null,
    val colorArgb: Long = 0xFF5B5BD6,
    val iconKey: String = "alarm",
    val enabled: Boolean = true,
    val vibrateOnly: Boolean = false,
    val vibrationPattern: VibrationPattern = VibrationPattern.GENTLE_PULSE,
    /** null = system default alarm sound. */
    val ringtoneUri: String? = null,
    val snoozeMinutes: Int = 10,
    val createdAt: Long = System.currentTimeMillis(),
) {
    val effectiveMask: Int
        get() = when (repeatType) {
            RepeatType.ONCE -> 0
            RepeatType.DAILY -> ALL_DAYS
            RepeatType.WEEKDAYS -> WEEKDAYS
            RepeatType.CUSTOM -> daysMask
        }

    val minuteOfDay: Int get() = hour * 60 + minute

    fun isScheduledOn(date: LocalDate): Boolean =
        if (repeatType == RepeatType.ONCE) onceDateEpochDay == date.toEpochDay()
        else effectiveMask.hasDay(date.dayOfWeek)

    /** Title safe to show while the device is locked. */
    fun lockScreenTitle(): String = discreetLabel.ifBlank { title }
}

/** One row per reminder per day it was completed. "Reset at midnight" happens automatically:
 *  a new day simply has no rows yet, while the schedule itself is never touched. */
@Entity(
    tableName = "completion_log",
    primaryKeys = ["reminderId", "epochDay"],
    foreignKeys = [
        ForeignKey(
            entity = Reminder::class,
            parentColumns = ["id"],
            childColumns = ["reminderId"],
            onDelete = ForeignKey.CASCADE,
        )
    ],
    indices = [Index("epochDay")],
)
data class CompletionLog(
    val reminderId: Long,
    val epochDay: Long,
    val completedAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "interval_reminders")
data class IntervalReminder(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String = "Drink water",
    val intervalMinutes: Int = 45,
    val startMinuteOfDay: Int = 9 * 60,
    val endMinuteOfDay: Int = 19 * 60,
    val daysMask: Int = ALL_DAYS,
    val vibrationPattern: VibrationPattern = VibrationPattern.GENTLE_PULSE,
    val colorArgb: Long = 0xFF0EA5E9,
    val iconKey: String = "water",
    val enabled: Boolean = true,
)
