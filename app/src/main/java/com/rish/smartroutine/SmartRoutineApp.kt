package com.rish.smartroutine

import android.app.Application
import android.content.Context
import com.rish.smartroutine.alarm.AlarmScheduler
import com.rish.smartroutine.alarm.NotificationHelper
import com.rish.smartroutine.data.AppDatabase
import com.rish.smartroutine.data.RoutineRepository
import com.rish.smartroutine.data.SettingsStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Minimal manual dependency container (no DI framework needed). */
class AppContainer(context: Context) {
    val scheduler = AlarmScheduler(context)
    val repository = RoutineRepository(AppDatabase.get(context), scheduler)
    val settings = SettingsStore(context)
    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}

class SmartRoutineApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        NotificationHelper.createChannels(this)
        // Cheap safety net: make sure every alarm is armed whenever the process starts.
        container.appScope.launch(Dispatchers.IO) { container.repository.rescheduleAll() }
    }
}

val Context.container: AppContainer get() = (applicationContext as SmartRoutineApp).container
