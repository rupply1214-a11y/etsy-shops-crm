package com.rish.smartroutine.data

import java.time.LocalDate

/**
 * The pre-loaded routine, added once on first launch (and again from Settings → "Add pre-loaded
 * routine", which skips tasks that already exist). Every field stays fully editable in the app.
 * Day 1 of each course = the day the routine is added; change "Start date" in the editor if the
 * course actually began earlier.
 */
object StarterRoutine {

    fun reminders(today: LocalDate): List<Reminder> {
        val start = today.toEpochDay()
        return listOf(
            Reminder(
                title = "Morning Hydration & Soaked Dry Fruits",
                notes = "Drink 1–2 glasses of water and eat 8–10 overnight-soaked black raisins + 5–6 peeled almonds.",
                hour = 7, minute = 30,
                colorArgb = 0xFF0EA5E9, iconKey = "water",
                courseDays = null, startEpochDay = start,
            ),
            Reminder(
                title = "Morning Topical Cream & Light Breakfast",
                discreetLabel = "Morning routine",
                notes = "Apply pea-sized Anobliss cream externally using a new finger cot after bowel movement. " +
                    "Eat non-spicy breakfast. Continue for 3–4 extra days even after pain stops; " +
                    "do not exceed 14 days without doctor advice.",
                hour = 9, minute = 30,
                colorArgb = 0xFF8B5CF6, iconKey = "selfcare",
                courseDays = 10, startEpochDay = start,
                courseNote = "Adjustable: 7 to 14 days. Do not exceed 14 days without doctor advice.",
            ),
            Reminder(
                title = "Mid-Morning Cooling Dose (Gulkand)",
                notes = "Take 1 tsp Gulkand (use a dry spoon) with 1 glass of normal water.",
                hour = 11, minute = 0,
                colorArgb = 0xFFEC4899, iconKey = "medication",
                courseDays = 15, startEpochDay = start,
                courseNote = "Adjustable: 15 to 20 days.",
            ),
            Reminder(
                title = "Healthy Lunch with Curd",
                notes = "Eat roti-sabzi with 1 bowl of curd (dahi) or buttermilk. " +
                    "Avoid spicy food, deep-fried items, and raw green onions.",
                hour = 13, minute = 15,
                colorArgb = 0xFF10B981, iconKey = "food",
                courseDays = null, startEpochDay = start,
            ),
            Reminder(
                title = "Afternoon Cooling Dose (Gulkand)",
                notes = "Take 1 tsp Gulkand (use a dry spoon) with 1 glass of normal water (1.5–2 hours after lunch).",
                hour = 15, minute = 30,
                colorArgb = 0xFFEC4899, iconKey = "medication",
                courseDays = 15, startEpochDay = start,
                courseNote = "Adjustable: 15 to 20 days.",
            ),
            Reminder(
                title = "Evening Stool Softener Syrup (Duphalac)",
                discreetLabel = "Evening routine",
                notes = "Days 1–5: Take 15–20 ml with 1 full glass of water.",
                hour = 19, minute = 0,
                colorArgb = 0xFFF59E0B, iconKey = "medication",
                courseDays = 7, startEpochDay = start,
                courseNote = "7 days with tapering.",
                taperFromDay = 6,
                taperNote = "Days 6–7 (Tapering): Reduce to 10 ml before stopping gradually—do not stop abruptly.",
            ),
            Reminder(
                title = "Night Topical Cream & Next-Day Prep",
                discreetLabel = "Night routine",
                notes = "Apply pea-sized Anobliss cream gently using a new finger cot before sleep. " +
                    "Soak 8–10 black raisins and 5–6 almonds in water for tomorrow morning.",
                hour = 21, minute = 45,
                colorArgb = 0xFF5B5BD6, iconKey = "sleep",
                courseDays = 10, startEpochDay = start,
                courseNote = "Adjustable: 7 to 14 days. Do not exceed 14 days without doctor advice.",
            ),
        )
    }

    fun nudges(): List<IntervalReminder> = listOf(
        IntervalReminder(
            title = "Drink water & stand/walk 1–2 min",
            intervalMinutes = 60,
            startMinuteOfDay = 9 * 60 + 30,
            endMinuteOfDay = 18 * 60 + 30,
            daysMask = ALL_DAYS,
            vibrationPattern = VibrationPattern.GENTLE_PULSE,
            colorArgb = 0xFF0EA5E9,
            iconKey = "water",
        )
    )
}
