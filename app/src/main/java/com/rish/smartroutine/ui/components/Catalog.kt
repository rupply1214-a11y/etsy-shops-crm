package com.rish.smartroutine.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.DirectionsWalk
import androidx.compose.material.icons.automirrored.rounded.MenuBook
import androidx.compose.material.icons.rounded.AccessibilityNew
import androidx.compose.material.icons.rounded.Alarm
import androidx.compose.material.icons.rounded.Bedtime
import androidx.compose.material.icons.rounded.Call
import androidx.compose.material.icons.rounded.ContentCut
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FitnessCenter
import androidx.compose.material.icons.rounded.Lightbulb
import androidx.compose.material.icons.rounded.LocalCafe
import androidx.compose.material.icons.rounded.Medication
import androidx.compose.material.icons.rounded.Pets
import androidx.compose.material.icons.rounded.Restaurant
import androidx.compose.material.icons.rounded.School
import androidx.compose.material.icons.rounded.SelfImprovement
import androidx.compose.material.icons.rounded.ShoppingCart
import androidx.compose.material.icons.rounded.Spa
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material.icons.rounded.Visibility
import androidx.compose.material.icons.rounded.WaterDrop
import androidx.compose.material.icons.rounded.Work
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.data.RepeatType
import com.rish.smartroutine.data.hasDay
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

object Catalog {
    val colors: List<Long> = listOf(
        0xFF5B5BD6, 0xFF0EA5E9, 0xFF10B981, 0xFF14B8A6, 0xFFF59E0B,
        0xFFF97316, 0xFFEF4444, 0xFFEC4899, 0xFF8B5CF6, 0xFF64748B,
    )

    val icons: List<Pair<String, ImageVector>> = listOf(
        "alarm" to Icons.Rounded.Alarm,
        "medication" to Icons.Rounded.Medication,
        "water" to Icons.Rounded.WaterDrop,
        "fitness" to Icons.Rounded.FitnessCenter,
        "meditate" to Icons.Rounded.SelfImprovement,
        "posture" to Icons.Rounded.AccessibilityNew,
        "eyes" to Icons.Rounded.Visibility,
        "walk" to Icons.AutoMirrored.Rounded.DirectionsWalk,
        "food" to Icons.Rounded.Restaurant,
        "coffee" to Icons.Rounded.LocalCafe,
        "work" to Icons.Rounded.Work,
        "sewing" to Icons.Rounded.ContentCut,
        "read" to Icons.AutoMirrored.Rounded.MenuBook,
        "study" to Icons.Rounded.School,
        "call" to Icons.Rounded.Call,
        "shopping" to Icons.Rounded.ShoppingCart,
        "sleep" to Icons.Rounded.Bedtime,
        "selfcare" to Icons.Rounded.Spa,
        "pets" to Icons.Rounded.Pets,
        "idea" to Icons.Rounded.Lightbulb,
        "heart" to Icons.Rounded.Favorite,
        "star" to Icons.Rounded.Star,
    )

    fun icon(key: String): ImageVector = icons.firstOrNull { it.first == key }?.second ?: Icons.Rounded.Alarm
}

fun Long.asColor() = Color(this.toInt())

val orderedDays: List<DayOfWeek> = DayOfWeek.entries // Monday..Sunday

fun DayOfWeek.short(): String = getDisplayName(TextStyle.SHORT, Locale.getDefault())

fun Reminder.repeatSummary(today: LocalDate = LocalDate.now()): String = when (repeatType) {
    RepeatType.ONCE -> {
        val d = onceDateEpochDay
        when {
            d == null -> "Once"
            d == today.toEpochDay() -> "Once · today"
            d == today.toEpochDay() + 1 -> "Once · tomorrow"
            else -> LocalDate.ofEpochDay(d).let {
                "Once · ${it.dayOfMonth} ${it.month.getDisplayName(TextStyle.SHORT, Locale.getDefault())}"
            }
        }
    }
    RepeatType.DAILY -> "Every day"
    RepeatType.WEEKDAYS -> "Weekdays"
    RepeatType.CUSTOM -> daysSummary(daysMask)
}

fun daysSummary(mask: Int): String = when (mask) {
    0b1111111 -> "Every day"
    0b0011111 -> "Weekdays"
    0b1100000 -> "Weekends"
    0 -> "No days"
    else -> orderedDays.filter { mask.hasDay(it) }.joinToString(", ") { it.short() }
}
