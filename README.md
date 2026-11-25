# Smart Routine: Reminder and Smart Routine Alarm (Android, Kotlin)

A fully offline reminder and routine alarm app built with **Kotlin, Jetpack Compose (Material 3), Room and AlarmManager**. The app starts empty, and you build every reminder yourself.

---

## 1. Open and run

1. Install **Android Studio Ladybug (2024.2) or newer**.
2. **File → Open** → select the `SmartRoutine` folder. Let Gradle sync finish. The first sync downloads Gradle 8.10.2, AGP 8.7.3 and the libraries.
3. Plug in a phone with USB debugging on (or start an emulator, API 26+) → press **Run ▶**.
4. Optional: run the scheduling tests with `./gradlew test`.

| | |
|---|---|
| minSdk | 26 (Android 8.0) |
| target/compileSdk | 35 (Android 15) |
| Language | Kotlin 2.0.21, Java 17 |
| UI | Jetpack Compose, Material 3, dynamic color, light/dark/system |
| Storage | Room (SQLite), 100% local |

---

## 2. Project structure

```
app/src/main/java/com/rish/smartroutine/
├── SmartRoutineApp.kt        App + tiny DI container (creates channels, re-arms alarms on start)
├── data/
│   ├── Models.kt             Reminder, IntervalReminder, CompletionLog, enums (repeat, vibration)
│   ├── Database.kt           Room DAOs + AppDatabase
│   ├── RoutineRepository.kt  Single source of truth; every write re-arms AlarmManager
│   └── SettingsStore.kt      Theme mode + dynamic color (SharedPreferences)
├── alarm/
│   ├── ScheduleMath.kt       Pure "next fire time" logic (unit-tested)
│   ├── AlarmScheduler.kt     setAlarmClock() for reminders, setExactAndAllowWhileIdle() for nudges
│   ├── AlarmReceiver.kt      Fires → arms next occurrence → starts ringing service / posts nudge
│   ├── AlarmService.kt       Foreground service: sound (or zero sound) + looping vibration, 3-min auto-silence
│   ├── AlarmActionReceiver.kt Mark done / Snooze / Dismiss (notification buttons + alarm screen)
│   ├── BootReceiver.kt       Re-arms after reboot, app update, time/timezone change, permission change
│   ├── Haptics.kt            Vibration patterns with ALARM usage (works on silent)
│   └── NotificationHelper.kt Channels, full-screen notification, discreet lock-screen version
├── ui/
│   ├── MainActivity.kt       Navigation (Home, Editor, Intervals, Settings)
│   ├── home/                 Summary card + progress ring + interactive timeline, swipe-to-delete + undo
│   ├── editor/               Create/edit: title, discreet label, notes, time, repeat, color, icon, alert style
│   ├── interval/             Smart Interval nudges (every N min between start/end hours)
│   ├── settings/             Theme, permission checklist, OEM battery tips
│   ├── alarm/AlarmActivity   Full-screen lock-screen alarm (Done, Snooze 5/10/15, Dismiss)
│   └── components/, theme/
└── util/Permissions.kt       Status check + settings shortcut for each permission
```

### How key requirements are met

- **Exact time in Doze and deep sleep.** Reminders use `AlarmManager.setAlarmClock()`. It is the highest-priority alarm API: it is exempt from Doze, wakes the device, and Android never batches or delays it. Interval nudges use `setExactAndAllowWhileIdle()`.
- **Each fire schedules the next one.** On every fire, `AlarmReceiver` arms the next occurrence before it rings. Reboots, app updates and clock or timezone changes all trigger `BootReceiver.rescheduleAll()`.
- **Daily reset at midnight with the schedule kept.** Check-offs are saved in `completion_log` with one row per reminder per day. A new day starts with no rows, so the progress ring resets on its own and no reminder is changed. If you tick a reminder off early, it won't ring later that day.
- **Silent office mode.** The ringing notification channel itself is silent. `AlarmService` plays the reminder's own sound (or none if **Vibrate only** is on) and loops its pattern with `USAGE_ALARM`, so it still vibrates when the phone is on silent.
- **Privacy.** If a *Discreet label* is set, the lock screen shows only that label, and the alarm screen hides the real title and notes until the phone is unlocked.

---

## 3. Android permission setup (important)

All of these are already declared in `AndroidManifest.xml`. In the app, **Settings → Alarm reliability** shows a green or red status for each one with an **Allow** button. Home also shows a red banner while anything is missing.

### 3.1 Exact alarms
```xml
<uses-permission android:name="android.permission.USE_EXACT_ALARM" />
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" android:maxSdkVersion="32" />
```
- **Android 13+**: `USE_EXACT_ALARM` is granted automatically and the user can't revoke it.
- **Android 12/12L**: `SCHEDULE_EXACT_ALARM` is used. If the user revokes it, the app falls back to inexact alarms and the banner asks them to turn it back on (*Settings → Apps → Smart Routine → Alarms & reminders*).
- **Google Play policy**: `USE_EXACT_ALARM` is only allowed for apps whose **core function is alarms, timers or calendar reminders**, which fits this app. In the Play Console declaration, describe it as an alarm/reminder app.

### 3.2 Notifications (Android 13+)
`POST_NOTIFICATIONS` is requested on first launch. If the user denies it, the **Allow** button opens the app's notification settings.

### 3.3 Full-screen alarm over the lock screen (Android 14+)
`USE_FULL_SCREEN_INTENT` is granted automatically to apps that Play treats as alarm/calling apps. If it isn't granted, **Allow** opens *Settings → Apps → Special app access → Full screen notifications*. Without it, the alarm still rings and vibrates as a heads-up notification.

### 3.4 Vibration
`VIBRATE` is a normal permission and is granted automatically. Vibration uses `USAGE_ALARM`, so it works in silent mode. Do Not Disturb can still block it unless the user allows **Alarms** in their DND settings, which is on by default on most phones.

### 3.5 Battery optimization
`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` lets the **Allow** button show the system "Let app always run in background?" dialog.
> Play allows this permission for apps that need exact alarms to work. If a reviewer objects, remove the permission and switch `Permissions.settingsIntent(BATTERY)` to `Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS`.

### 3.6 Foreground service (ringing)
```xml
<service android:name=".alarm.AlarmService" android:foregroundServiceType="systemExempted" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_SYSTEM_EXEMPTED" />
```
`systemExempted` is the foreground service type Android 14+ allows for apps that hold exact-alarm permission. If a phone still blocks the service from starting, the app posts a loud backup notification on the `alarm_fallback` channel instead.

### 3.7 Brand-specific steps (Xiaomi/Redmi/POCO, Oppo, Realme, Vivo/iQOO, OnePlus, Samsung…)
These brands can kill background apps even when battery optimization is off. On those phones the app shows an extra card in Settings. Ask users to:
1. **App info → Autostart / Auto-launch → ON**
2. **Battery → No restrictions / Allow background activity**
3. **Recent apps → pull down on the app card → Lock**
4. Samsung: **Battery → Background usage limits →** remove from "Sleeping apps"

See https://dontkillmyapp.com for each brand's steps.

---

## 4. Test checklist

1. Create a reminder 2 minutes ahead → lock the phone → it should turn on the screen with the full-screen alarm.
2. Turn on **Vibrate only** and set the phone to silent → it should vibrate with no sound.
3. Set a **Discreet label** → the locked screen should show only the label.
4. Tap **Snooze 5m** → it should ring again 5 minutes later.
5. Force Doze over adb:
   ```
   adb shell dumpsys deviceidle force-idle
   adb shell dumpsys alarm | grep smartroutine   # check that the alarm is registered
   ```
6. Reboot the phone → the next reminder should still ring.
7. Interval nudge: set it to every 15 min with a window that includes now → you should get a silent vibration nudge.

## 5. Customizing

- Add icons: `ui/components/Catalog.kt → icons`
- Add colors: `Catalog.colors`
- Add vibration patterns: `data/Models.kt → VibrationPattern`. New patterns also get a nudge channel automatically. Android won't change an existing channel's pattern, so if you edit one, rename it.
- Change the ring timeout: `AlarmService.RING_TIMEOUT_MS` (default 3 minutes; after that the reminder shows as "Missed").

## 6. Course duration (v1.1)

- Each reminder is either an **Ongoing habit** or a course with a **fixed number of days**. A course has a start date (Day 1), an optional stopping note, and an optional tapering note that applies from a chosen day.
- Task cards show **Day X of N**, a progress bar, the end date and the tapering note. The alarm screen and the notification also show the course day.
- After the last day, a course stops ringing and moves to **Completed courses**, where you can extend it by **+2 or +3 days**. A course that is still running has a **+1 day** button.
- On first launch the app adds the pre-loaded routine once (7 tasks plus the hourly water/walk nudge). **Settings → Add pre-loaded routine** adds it again and skips tasks you already have.
- Database v2 includes a migration from v1, so existing reminders become "Ongoing".
- The APK is signed with `app/smartroutine.keystore`, so future builds install over the existing app as updates.
