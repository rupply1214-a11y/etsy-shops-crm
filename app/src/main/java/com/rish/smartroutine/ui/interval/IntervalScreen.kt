@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.rish.smartroutine.ui.interval

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.rish.smartroutine.alarm.NotificationHelper.formatMinuteOfDay
import com.rish.smartroutine.alarm.ScheduleMath
import com.rish.smartroutine.data.IntervalReminder
import com.rish.smartroutine.data.RoutineRepository
import com.rish.smartroutine.ui.components.AnimatedIconBadge
import com.rish.smartroutine.ui.components.Catalog
import com.rish.smartroutine.ui.components.ColorPickerRow
import com.rish.smartroutine.ui.components.DaySelector
import com.rish.smartroutine.ui.components.IconPicker
import com.rish.smartroutine.ui.components.Pill
import com.rish.smartroutine.ui.components.TimePickerDialog
import com.rish.smartroutine.ui.components.VibrationPatternPicker
import com.rish.smartroutine.ui.components.asColor
import com.rish.smartroutine.ui.components.daysSummary
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import kotlin.math.roundToInt
import java.time.format.DateTimeFormatter

class IntervalViewModel(private val repo: RoutineRepository) : ViewModel() {
    val items = repo.observeIntervals()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun save(item: IntervalReminder) = viewModelScope.launch { repo.saveInterval(item.copy(title = item.title.trim())) }
    fun delete(item: IntervalReminder) = viewModelScope.launch { repo.deleteInterval(item) }
    fun setEnabled(item: IntervalReminder, on: Boolean) = viewModelScope.launch { repo.setIntervalEnabled(item, on) }
}

@Composable
fun IntervalScreen(vm: IntervalViewModel, onBack: () -> Unit) {
    val items by vm.items.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<IntervalReminder?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back") } },
                title = { Text("Smart interval nudges") },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { editing = IntervalReminder() }) { Icon(Icons.Rounded.Add, "Add nudge") }
        },
    ) { padding ->
        val list = items
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp, 4.dp, 16.dp, 96.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text(
                    "Gentle, silent vibration nudges that repeat on an interval during your active hours — great for water, posture or eye breaks.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (list != null && list.isEmpty()) {
                item {
                    Column(Modifier.fillMaxWidth().padding(top = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Rounded.Timer, null, Modifier.padding(8.dp), tint = MaterialTheme.colorScheme.primary)
                        Text("No interval nudges yet", style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { editing = IntervalReminder() }) { Text("Create one") }
                    }
                }
            }
            items(list.orEmpty(), key = { it.id }) { item ->
                IntervalCard(item, onClick = { editing = item }, onToggle = { vm.setEnabled(item, it) }, modifier = Modifier.animateItem())
            }
        }
    }

    editing?.let { start ->
        IntervalEditorSheet(
            initial = start,
            onDismiss = { editing = null },
            onSave = { vm.save(it); editing = null },
            onDelete = if (start.id != 0L) ({ vm.delete(start); editing = null }) else null,
        )
    }
}

@Composable
private fun IntervalCard(item: IntervalReminder, onClick: () -> Unit, onToggle: (Boolean) -> Unit, modifier: Modifier) {
    val accent = item.colorArgb.asColor()
    val next = remember(item) { ScheduleMath.nextIntervalFire(item, LocalDateTime.now()) }
    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            AnimatedIconBadge(Catalog.icon(item.iconKey), accent)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(item.title, style = MaterialTheme.typography.titleMedium)
                Text(
                    "Every ${item.intervalMinutes} min · ${formatMinuteOfDay(item.startMinuteOfDay)} – ${formatMinuteOfDay(item.endMinuteOfDay)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Pill(daysSummary(item.daysMask), accent)
                    Pill(item.vibrationPattern.label, MaterialTheme.colorScheme.secondary)
                    if (item.enabled && next != null) {
                        Pill("Next ${next.format(DateTimeFormatter.ofPattern("h:mm a"))}", MaterialTheme.colorScheme.tertiary)
                    }
                }
            }
            Switch(checked = item.enabled, onCheckedChange = onToggle)
        }
    }
}

@Composable
private fun IntervalEditorSheet(
    initial: IntervalReminder,
    onDismiss: () -> Unit,
    onSave: (IntervalReminder) -> Unit,
    onDelete: (() -> Unit)?,
) {
    val context = LocalContext.current
    var d by remember(initial) { mutableStateOf(initial) }
    var pickStart by remember { mutableStateOf(false) }
    var pickEnd by remember { mutableStateOf(false) }
    val accent = d.colorArgb.asColor()
    val validWindow = d.endMinuteOfDay > d.startMinuteOfDay
    val perDay = if (validWindow) (d.endMinuteOfDay - d.startMinuteOfDay) / d.intervalMinutes + 1 else 0

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(
            Modifier
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(if (initial.id == 0L) "New interval nudge" else "Edit interval nudge", style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(
                value = d.title, onValueChange = { d = d.copy(title = it.take(50)) },
                label = { Text("Title") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )

            Text("Repeat every ${d.intervalMinutes} minutes", style = MaterialTheme.typography.titleSmall)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(15, 30, 45, 60, 90, 120).forEach { m ->
                    FilterChip(selected = d.intervalMinutes == m, onClick = { d = d.copy(intervalMinutes = m) }, label = { Text("$m min") })
                }
            }
            Slider(
                value = d.intervalMinutes.toFloat(),
                onValueChange = { d = d.copy(intervalMinutes = (it / 5).roundToInt() * 5) },
                valueRange = 5f..180f,
                steps = 34,
            )

            Text("Active hours", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { pickStart = true }, modifier = Modifier.weight(1f)) {
                    Text("From ${formatMinuteOfDay(d.startMinuteOfDay)}")
                }
                OutlinedButton(onClick = { pickEnd = true }, modifier = Modifier.weight(1f)) {
                    Text("To ${formatMinuteOfDay(d.endMinuteOfDay)}")
                }
            }
            Text(
                if (validWindow) "≈ $perDay nudges per active day" else "End time must be after start time",
                style = MaterialTheme.typography.bodySmall,
                color = if (validWindow) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
            )

            Text("Active days", style = MaterialTheme.typography.titleSmall)
            DaySelector(d.daysMask, { d = d.copy(daysMask = it) }, accent)

            Text("Vibration (no sound)", style = MaterialTheme.typography.titleSmall)
            VibrationPatternPicker(d.vibrationPattern, context) { d = d.copy(vibrationPattern = it) }

            Text("Color & icon", style = MaterialTheme.typography.titleSmall)
            ColorPickerRow(d.colorArgb) { d = d.copy(colorArgb = it) }
            IconPicker(d.iconKey, accent) { d = d.copy(iconKey = it) }

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (onDelete != null) {
                    OutlinedButton(onClick = onDelete, modifier = Modifier.weight(1f)) { Text("Delete") }
                }
                Button(
                    onClick = { onSave(d.copy(enabled = true)) },
                    enabled = d.title.isNotBlank() && validWindow && d.daysMask != 0,
                    modifier = Modifier.weight(1f),
                ) { Text("Save", textAlign = TextAlign.Center) }
            }
            Spacer(Modifier.height(16.dp))
        }
    }

    if (pickStart) TimePickerDialog(d.startMinuteOfDay / 60, d.startMinuteOfDay % 60, "Start time", { pickStart = false }) { h, m ->
        d = d.copy(startMinuteOfDay = h * 60 + m); pickStart = false
    }
    if (pickEnd) TimePickerDialog((d.endMinuteOfDay / 60) % 24, d.endMinuteOfDay % 60, "End time", { pickEnd = false }) { h, m ->
        d = d.copy(endMinuteOfDay = h * 60 + m); pickEnd = false
    }
}
