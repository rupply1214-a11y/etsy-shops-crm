package com.rish.smartroutine.ui.editor

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rish.smartroutine.alarm.ScheduleMath
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.data.RepeatType
import com.rish.smartroutine.data.RoutineRepository
import com.rish.smartroutine.ui.components.Catalog
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.LocalDateTime

class EditorViewModel(
    private val repo: RoutineRepository,
    private val reminderId: Long?,
) : ViewModel() {

    val isNew = reminderId == null

    var draft by mutableStateOf(newDraft())
        private set

    var loaded by mutableStateOf(isNew)
        private set

    var saving by mutableStateOf(false)
        private set

    init {
        if (reminderId != null) viewModelScope.launch {
            repo.getReminder(reminderId)?.let { draft = it }
            loaded = true
        }
    }

    fun update(transform: (Reminder) -> Reminder) { draft = transform(draft) }

    val canSave: Boolean
        get() = loaded && !saving && draft.title.isNotBlank() &&
            (draft.repeatType != RepeatType.CUSTOM || draft.daysMask != 0)

    /** "Rings in 3h 20m" preview for the current draft. */
    fun ringsInText(now: LocalDateTime = LocalDateTime.now()): String {
        val preview = if (draft.repeatType == RepeatType.ONCE)
            draft.copy(onceDateEpochDay = ScheduleMath.onceDateFor(draft.hour, draft.minute, now).toEpochDay())
        else draft
        val next = ScheduleMath.nextOccurrence(preview, now) ?: return "Pick at least one day"
        val mins = Duration.between(now, next).toMinutes() + 1
        val d = mins / (24 * 60); val h = (mins % (24 * 60)) / 60; val m = mins % 60
        return buildString {
            append("Rings in ")
            if (d > 0) append("${d}d ")
            if (h > 0) append("${h}h ")
            append("${m}m")
        }
    }

    fun save(onDone: () -> Unit) {
        if (!canSave) return
        saving = true
        viewModelScope.launch {
            repo.saveReminder(
                draft.copy(
                    title = draft.title.trim(),
                    discreetLabel = draft.discreetLabel.trim(),
                    notes = draft.notes.trim(),
                    enabled = true,
                )
            )
            onDone()
        }
    }

    fun delete(onDone: () -> Unit) = viewModelScope.launch {
        repo.deleteReminder(draft)
        onDone()
    }

    private fun newDraft(): Reminder {
        val next = LocalDateTime.now().plusHours(1)
        return Reminder(
            hour = next.hour,
            minute = 0,
            colorArgb = Catalog.colors.random(),
        )
    }
}
