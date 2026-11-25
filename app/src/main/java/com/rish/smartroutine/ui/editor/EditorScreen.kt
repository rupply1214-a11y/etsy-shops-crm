@file:OptIn(ExperimentalMaterial3Api::class)

package com.rish.smartroutine.ui.editor

import android.app.Activity
import android.content.Intent
import android.media.RingtoneManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Notes
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Title
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.core.content.IntentCompat
import com.rish.smartroutine.data.ALL_DAYS
import com.rish.smartroutine.data.RepeatType
import com.rish.smartroutine.ui.components.AnimatedIconBadge
import com.rish.smartroutine.ui.components.Catalog
import com.rish.smartroutine.ui.components.ColorPickerRow
import com.rish.smartroutine.ui.components.DaySelector
import com.rish.smartroutine.ui.components.IconPicker
import com.rish.smartroutine.ui.components.SectionCard
import com.rish.smartroutine.ui.components.TimePickerDialog
import com.rish.smartroutine.ui.components.VibrationPatternPicker
import com.rish.smartroutine.ui.components.asColor
import java.time.LocalTime
import java.time.format.DateTimeFormatter

@Composable
fun EditorScreen(vm: EditorViewModel, onClose: () -> Unit) {
    val d = vm.draft
    val context = LocalContext.current
    val accent by animateColorAsState(d.colorArgb.asColor(), label = "accent")
    var showTime by rememberSaveable { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }

    val ringtoneLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
        if (res.resultCode == Activity.RESULT_OK) {
            val uri = res.data?.let { IntentCompat.getParcelableExtra(it, RingtoneManager.EXTRA_RINGTONE_PICKED_URI, Uri::class.java) }
            vm.update { it.copy(ringtoneUri = uri?.toString()) }
        }
    }
    val ringtoneName = remember(d.ringtoneUri) {
        d.ringtoneUri?.let { runCatching { RingtoneManager.getRingtone(context, Uri.parse(it))?.getTitle(context) }.getOrNull() }
            ?: "Default alarm sound"
    }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onClose) { Icon(Icons.Rounded.Close, "Close") } },
                title = { Text(if (vm.isNew) "New reminder" else "Edit reminder") },
                actions = {
                    if (!vm.isNew) IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Rounded.DeleteOutline, "Delete") }
                    TextButton(onClick = { vm.save(onClose) }, enabled = vm.canSave) {
                        Text("Save", fontWeight = FontWeight.Bold)
                    }
                },
            )
        },
    ) { padding ->
        if (!vm.loaded) {
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            // ---- Time hero ----
            Card(
                onClick = { showTime = true },
                shape = MaterialTheme.shapes.extraLarge,
                colors = CardDefaults.cardColors(containerColor = accent.copy(alpha = 0.14f)),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(Modifier.padding(22.dp), verticalAlignment = Alignment.CenterVertically) {
                    AnimatedIconBadge(Catalog.icon(d.iconKey), accent, size = 56.dp)
                    Spacer(Modifier.width(16.dp))
                    Column {
                        val t = LocalTime.of(d.hour, d.minute)
                        Row(verticalAlignment = Alignment.Bottom) {
                            Text(t.format(DateTimeFormatter.ofPattern("h:mm")), style = MaterialTheme.typography.displayMedium, color = accent)
                            Spacer(Modifier.width(6.dp))
                            Text(t.format(DateTimeFormatter.ofPattern("a")), style = MaterialTheme.typography.titleLarge, color = accent, modifier = Modifier.padding(bottom = 8.dp))
                        }
                        Text(vm.ringsInText(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Tap to change time", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }

            // ---- Details ----
            SectionCard("Details") {
                OutlinedTextField(
                    value = d.title,
                    onValueChange = { v -> vm.update { it.copy(title = v.take(60)) } },
                    label = { Text("Title *") },
                    leadingIcon = { Icon(Icons.Rounded.Title, null) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = d.discreetLabel,
                    onValueChange = { v -> vm.update { it.copy(discreetLabel = v.take(40)) } },
                    label = { Text("Discreet lock-screen label") },
                    placeholder = { Text("e.g. Quick task") },
                    supportingText = { Text("Shown instead of the title while the phone is locked. Leave blank to show the title.") },
                    leadingIcon = { Icon(Icons.Rounded.Lock, null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = d.notes,
                    onValueChange = { v -> vm.update { it.copy(notes = v.take(300)) } },
                    label = { Text("Notes / instructions") },
                    placeholder = { Text("e.g. 1 tablet after food") },
                    leadingIcon = { Icon(Icons.AutoMirrored.Rounded.Notes, null) },
                    minLines = 2,
                    maxLines = 5,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            // ---- Repeat ----
            SectionCard("Repeat") {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    RepeatType.entries.forEachIndexed { i, type ->
                        SegmentedButton(
                            selected = d.repeatType == type,
                            onClick = {
                                vm.update {
                                    it.copy(
                                        repeatType = type,
                                        daysMask = if (type == RepeatType.CUSTOM && it.daysMask == 0) ALL_DAYS else it.daysMask,
                                    )
                                }
                            },
                            shape = SegmentedButtonDefaults.itemShape(i, RepeatType.entries.size),
                            label = { Text(type.label, maxLines = 1) },
                        )
                    }
                }
                AnimatedVisibility(d.repeatType == RepeatType.CUSTOM) {
                    Column {
                        Spacer(Modifier.height(4.dp))
                        DaySelector(d.daysMask, { m -> vm.update { it.copy(daysMask = m) } }, accent)
                        if (d.daysMask == 0) {
                            Text("Pick at least one day", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            // ---- Look ----
            SectionCard("Color & icon") {
                ColorPickerRow(d.colorArgb) { c -> vm.update { it.copy(colorArgb = c) } }
                IconPicker(d.iconKey, accent) { k -> vm.update { it.copy(iconKey = k) } }
            }

            // ---- Alert ----
            SectionCard("Alert style") {
                ListItem(
                    headlineContent = { Text("Vibrate only (zero sound)") },
                    supportingContent = { Text("Silent office mode — buzzes even when the phone is on silent.") },
                    trailingContent = {
                        Switch(checked = d.vibrateOnly, onCheckedChange = { v -> vm.update { it.copy(vibrateOnly = v) } })
                    },
                    colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                )
                Text("Vibration pattern (tap to preview)", style = MaterialTheme.typography.labelLarge)
                VibrationPatternPicker(d.vibrationPattern, context) { p -> vm.update { it.copy(vibrationPattern = p) } }

                AnimatedVisibility(!d.vibrateOnly) {
                    ListItem(
                        headlineContent = { Text("Sound") },
                        supportingContent = { Text(ringtoneName) },
                        leadingContent = { Icon(Icons.Rounded.MusicNote, null) },
                        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                        modifier = Modifier.clickable {
                            ringtoneLauncher.launch(
                                Intent(RingtoneManager.ACTION_RINGTONE_PICKER)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, RingtoneManager.TYPE_ALL)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_TITLE, "Reminder sound")
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT, true)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT, false)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_DEFAULT_URI, Settings.System.DEFAULT_ALARM_ALERT_URI)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_EXISTING_URI, d.ringtoneUri?.let(Uri::parse))
                            )
                        },
                    )
                }

                Text("Snooze length", style = MaterialTheme.typography.labelLarge)
                val snoozeOptions = listOf(5, 10, 15)
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    snoozeOptions.forEachIndexed { i, m ->
                        SegmentedButton(
                            selected = d.snoozeMinutes == m,
                            onClick = { vm.update { it.copy(snoozeMinutes = m) } },
                            shape = SegmentedButtonDefaults.itemShape(i, snoozeOptions.size),
                            label = { Text("$m min") },
                        )
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }

    if (showTime) {
        TimePickerDialog(
            initialHour = d.hour,
            initialMinute = d.minute,
            onDismiss = { showTime = false },
            onConfirm = { h, m -> vm.update { it.copy(hour = h, minute = m) }; showTime = false },
        )
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete reminder?") },
            text = { Text("“${d.title}” and its alarm will be removed.") },
            confirmButton = { TextButton(onClick = { confirmDelete = false; vm.delete(onClose) }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}
