package com.rish.smartroutine.util

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.content.ContextCompat

/** Everything the alarm engine needs, with a check and a "fix it" intent for each. */
enum class AlarmPermission(val title: String, val why: String) {
    NOTIFICATIONS(
        "Notifications",
        "Needed to show reminders and the Done / Snooze buttons.",
    ),
    EXACT_ALARMS(
        "Alarms & reminders",
        "Lets reminders fire at the exact second, even in Doze / deep sleep.",
    ),
    FULL_SCREEN(
        "Full-screen alerts",
        "Shows the alarm screen over the lock screen (Android 14+).",
    ),
    BATTERY(
        "Unrestricted battery",
        "Stops the system from delaying or killing reminders to save battery.",
    );
}

object Permissions {

    fun isGranted(context: Context, p: AlarmPermission): Boolean = when (p) {
        AlarmPermission.NOTIFICATIONS ->
            Build.VERSION.SDK_INT < 33 ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED

        AlarmPermission.EXACT_ALARMS ->
            Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
                context.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()

        AlarmPermission.FULL_SCREEN ->
            Build.VERSION.SDK_INT < 34 ||
                context.getSystemService(NotificationManager::class.java).canUseFullScreenIntent()

        AlarmPermission.BATTERY ->
            context.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(context.packageName)
    }

    /** Only the ones that apply to this Android version. */
    fun applicable(): List<AlarmPermission> = AlarmPermission.entries.filter {
        when (it) {
            AlarmPermission.NOTIFICATIONS -> Build.VERSION.SDK_INT >= 33
            AlarmPermission.EXACT_ALARMS -> Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
            AlarmPermission.FULL_SCREEN -> Build.VERSION.SDK_INT >= 34
            AlarmPermission.BATTERY -> true
        }
    }

    fun missing(context: Context) = applicable().filterNot { isGranted(context, it) }

    /** Settings screen intent for permissions that are not runtime dialogs. */
    @SuppressLint("BatteryLife")
    fun settingsIntent(context: Context, p: AlarmPermission): Intent {
        val pkg = Uri.parse("package:${context.packageName}")
        return when (p) {
            AlarmPermission.NOTIFICATIONS ->
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)

            AlarmPermission.EXACT_ALARMS ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                    Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, pkg)
                else appDetails(context)

            AlarmPermission.FULL_SCREEN ->
                if (Build.VERSION.SDK_INT >= 34)
                    Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, pkg)
                else appDetails(context)

            AlarmPermission.BATTERY ->
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, pkg)
        }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    fun appDetails(context: Context): Intent =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    /** Brands known for killing background apps (common in India). */
    fun aggressiveOem(): String? {
        val m = Build.MANUFACTURER.lowercase()
        return listOf("xiaomi", "redmi", "poco", "oppo", "realme", "vivo", "iqoo", "oneplus", "huawei", "honor", "samsung", "tecno", "infinix", "itel", "asus", "motorola")
            .firstOrNull { m.contains(it) }
    }
}
