package com.rish.smartroutine.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.data.RoutineRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime

data class TodayItem(val reminder: Reminder, val done: Boolean, val overdue: Boolean)

data class HomeUiState(
    val loading: Boolean = true,
    val now: LocalDateTime = LocalDateTime.now(),
    val today: List<TodayItem> = emptyList(),
    val others: List<Reminder> = emptyList(),
    val hasAnyReminder: Boolean = false,
) {
    val date: LocalDate get() = now.toLocalDate()
    private val active get() = today.filter { it.reminder.enabled }
    val doneCount get() = active.count { it.done }
    val totalCount get() = active.size
    val progress get() = if (totalCount == 0) 0f else doneCount.toFloat() / totalCount
    val nextUp: TodayItem?
        get() = active.firstOrNull { !it.done && it.reminder.minuteOfDay >= now.hour * 60 + now.minute }
}

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModel(private val repo: RoutineRepository) : ViewModel() {

    /** Ticks every 30 s and on resume, so "today" rolls over at midnight without touching the schedule. */
    private val now = MutableStateFlow(LocalDateTime.now())

    init {
        viewModelScope.launch {
            while (isActive) { delay(30_000); tick() }
        }
    }

    fun tick() { now.value = LocalDateTime.now() }

    private val completedToday = now
        .map { it.toLocalDate() }
        .distinctUntilChanged()
        .flatMapLatest { day -> repo.observeCompletedIds(day).map { day to it.toSet() } }

    val state: StateFlow<HomeUiState> =
        combine(repo.observeReminders(), completedToday, now) { reminders, (day, done), now ->
            val nowMinute = now.hour * 60 + now.minute
            val (todays, others) = reminders.partition { it.isScheduledOn(day) }
            HomeUiState(
                loading = false,
                now = now,
                today = todays.map {
                    val isDone = it.id in done
                    TodayItem(it, isDone, overdue = !isDone && it.enabled && it.minuteOfDay < nowMinute)
                },
                others = others,
                hasAnyReminder = reminders.isNotEmpty(),
            )
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), HomeUiState())

    fun toggleDone(item: TodayItem) = viewModelScope.launch {
        repo.setCompleted(item.reminder.id, state.value.date, !item.done)
    }

    fun setEnabled(r: Reminder, enabled: Boolean) = viewModelScope.launch { repo.setReminderEnabled(r, enabled) }

    fun delete(r: Reminder) = viewModelScope.launch { repo.deleteReminder(r) }

    fun undoDelete(r: Reminder) = viewModelScope.launch { repo.restoreReminder(r) }
}
