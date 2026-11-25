@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.rish.smartroutine.ui.editor

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Remove
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.rish.smartroutine.data.CourseStatus
import com.rish.smartroutine.ui.components.SectionCard
import com.rish.smartroutine.ui.components.courseBadge
import com.rish.smartroutine.ui.components.shortLabel
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** "Course duration" block of the editor: Ongoing vs fixed days, start date, tapering. */
@Composable
fun CourseSection(vm: EditorViewModel, accent: Color) {
    val d = vm.draft
    val finite = d.courseDays != null
    var pickDate by remember { mutableStateOf(false) }
    val today = LocalDate.now()

    SectionCard("Course duration") {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            SegmentedButton(
                selected = !finite,
                onClick = { vm.update { it.copy(courseDays = null, extraDays = 0) } },
                shape = SegmentedButtonDefaults.itemShape(0, 2),
                label = { Text("Ongoing habit") },
            )
            SegmentedButton(
                selected = finite,
                onClick = { vm.update { it.copy(courseDays = it.courseDays ?: 10, startEpochDay = if (it.courseDays == null) today.toEpochDay() else it.startEpochDay) } },
                shape = SegmentedButtonDefaults.itemShape(1, 2),
                label = { Text("Fixed days") },
            )
        }

        AnimatedVisibility(!finite) {
            Text(
                "Repeats every scheduled day with no end date.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        AnimatedVisibility(finite) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                val days = d.courseDays ?: 10
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(7, 10, 14, 15, 20, 30).forEach { n ->
                        FilterChip(
                            selected = days == n,
                            onClick = { vm.update { it.copy(courseDays = n) } },
                            label = { Text("$n days") },
                        )
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    FilledTonalIconButton(onClick = { vm.update { it.copy(courseDays = (days - 1).coerceAtLeast(1)) } }) {
                        Icon(Icons.Rounded.Remove, "One day less")
                    }
                    Text(
                        "$days days",
                        style = MaterialTheme.typography.titleLarge,
                        color = accent,
                        modifier = Modifier.weight(1f),
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                    FilledTonalIconButton(onClick = { vm.update { it.copy(courseDays = (days + 1).coerceAtMost(365)) } }) {
                        Icon(Icons.Rounded.Add, "One day more")
                    }
                }

                OutlinedButton(onClick = { pickDate = true }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Rounded.CalendarMonth, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Start date (Day 1): ${d.startDate.shortLabel()}")
                }

                val status = d.courseStatus(today)
                Text(
                    buildString {
                        append(
                            when (status) {
                                CourseStatus.ACTIVE -> "Today is ${d.courseBadge(today)}"
                                else -> d.courseBadge(today)
                            }
                        )
                        d.endDate?.let { append(" · Ends ${it.shortLabel()}") }
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                if (d.extraDays != 0) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "Includes +${d.extraDays} extended day${if (d.extraDays > 1) "s" else ""}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(onClick = { vm.update { it.copy(extraDays = 0) } }) { Text("Reset") }
                    }
                }

                OutlinedTextField(
                    value = d.courseNote,
                    onValueChange = { v -> vm.update { it.copy(courseNote = v.take(200)) } },
                    label = { Text("Duration / stopping note") },
                    placeholder = { Text("e.g. Adjustable: 7 to 14 days") },
                    modifier = Modifier.fillMaxWidth(),
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Tapering at the end", style = MaterialTheme.typography.titleSmall)
                        Text(
                            "Show a different instruction for the last days",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(
                        checked = d.taperFromDay != null,
                        onCheckedChange = { on ->
                            vm.update { it.copy(taperFromDay = if (on) ((it.courseDays ?: 7) - 1).coerceAtLeast(1) else null) }
                        },
                    )
                }
                AnimatedVisibility(d.taperFromDay != null) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        val from = d.taperFromDay ?: 1
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            FilledTonalIconButton(onClick = { vm.update { it.copy(taperFromDay = (from - 1).coerceAtLeast(1)) } }) {
                                Icon(Icons.Rounded.Remove, "Earlier")
                            }
                            Text(
                                "From Day $from",
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.weight(1f),
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            )
                            FilledTonalIconButton(onClick = { vm.update { it.copy(taperFromDay = (from + 1).coerceAtMost(days)) } }) {
                                Icon(Icons.Rounded.Add, "Later")
                            }
                        }
                        OutlinedTextField(
                            value = d.taperNote,
                            onValueChange = { v -> vm.update { it.copy(taperNote = v.take(200)) } },
                            label = { Text("Tapering instruction") },
                            placeholder = { Text("e.g. Reduce to 10 ml before stopping") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
    }

    if (pickDate) {
        val state = rememberDatePickerState(
            initialSelectedDateMillis = d.startDate.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { pickDate = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { ms ->
                        val date = Instant.ofEpochMilli(ms).atZone(ZoneOffset.UTC).toLocalDate()
                        vm.update { it.copy(startEpochDay = date.toEpochDay()) }
                    }
                    pickDate = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { pickDate = false }) { Text("Cancel") } },
        ) { DatePicker(state = state) }
    }
}
