@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.rish.smartroutine.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.RadioButtonUnchecked
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material.icons.rounded.Vibration
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Switch
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rish.smartroutine.data.Reminder
import com.rish.smartroutine.ui.components.AnimatedIconBadge
import com.rish.smartroutine.ui.components.Catalog
import com.rish.smartroutine.ui.components.Pill
import com.rish.smartroutine.ui.components.ProgressRing
import com.rish.smartroutine.ui.components.asColor
import com.rish.smartroutine.ui.components.repeatSummary
import com.rish.smartroutine.util.Permissions
import kotlinx.coroutines.launch
import java.time.format.DateTimeFormatter

private val timeFmt = DateTimeFormatter.ofPattern("h:mm")
private val ampmFmt = DateTimeFormatter.ofPattern("a")

@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onAdd: () -> Unit,
    onEdit: (Long) -> Unit,
    onIntervals: () -> Unit,
    onSettings: () -> Unit,
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val fabExpanded by remember { derivedStateOf { listState.firstVisibleItemIndex == 0 } }

    var missingPermissions by remember { mutableStateOf(Permissions.missing(context)) }
    LifecycleResumeEffect(Unit) {
        vm.tick()
        missingPermissions = Permissions.missing(context)
        onPauseOrDispose { }
    }

    val onDelete: (Reminder) -> Unit = { r ->
        vm.delete(r)
        scope.launch {
            val res = snackbar.showSnackbar("“${r.title}” deleted", actionLabel = "Undo", withDismissAction = true)
            if (res == SnackbarResult.ActionPerformed) vm.undoDelete(r)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Smart Routine", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onIntervals) { Icon(Icons.Rounded.Timer, "Interval nudges") }
                    IconButton(onClick = onSettings) { Icon(Icons.Rounded.Settings, "Settings") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onAdd,
                expanded = fabExpanded,
                icon = { Icon(Icons.Rounded.Add, null) },
                text = { Text("New reminder") },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 112.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item(key = "summary") { SummaryCard(state) }

            if (missingPermissions.isNotEmpty()) {
                item(key = "perm") { PermissionBanner(missingPermissions.size, onSettings) }
            }

            if (!state.loading && !state.hasAnyReminder) {
                item(key = "empty") { EmptyState(onAdd, onIntervals) }
            } else {
                item(key = "h_today") { SectionHeader("Today's timeline") }
                if (state.today.isEmpty() && !state.loading) {
                    item(key = "none_today") {
                        Text(
                            "Nothing scheduled for today.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(8.dp),
                        )
                    }
                }
                items(state.today, key = { it.reminder.id }) { item ->
                    SwipeToDelete(item.reminder, onDelete, Modifier.animateItem()) {
                        TimelineRow(
                            reminder = item.reminder,
                            done = item.done,
                            overdue = item.overdue,
                            isNext = state.nextUp?.reminder?.id == item.reminder.id,
                            showCheck = true,
                            onToggleDone = { vm.toggleDone(item) },
                            onToggleEnabled = { vm.setEnabled(item.reminder, it) },
                            onClick = { onEdit(item.reminder.id) },
                        )
                    }
                }
                if (state.others.isNotEmpty()) {
                    item(key = "h_other") { SectionHeader("Other days") }
                    items(state.others, key = { "o${it.id}" }) { r ->
                        SwipeToDelete(r, onDelete, Modifier.animateItem()) {
                            TimelineRow(
                                reminder = r, done = false, overdue = false, isNext = false, showCheck = false,
                                onToggleDone = {}, onToggleEnabled = { vm.setEnabled(r, it) },
                                onClick = { onEdit(r.id) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryCard(state: HomeUiState) {
    val greeting = when (state.now.hour) {
        in 5..11 -> "Good morning"
        in 12..16 -> "Good afternoon"
        else -> "Good evening"
    }
    val gradient = Brush.linearGradient(
        listOf(MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.tertiaryContainer),
    )
    Card(shape = MaterialTheme.shapes.extraLarge, colors = CardDefaults.cardColors(containerColor = Color.Transparent)) {
        Row(
            Modifier.fillMaxWidth().background(gradient).padding(22.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(greeting, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.75f))
                Text(
                    state.date.format(DateTimeFormatter.ofPattern("EEEE")),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
                Text(
                    state.date.format(DateTimeFormatter.ofPattern("d MMMM yyyy")),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.8f),
                )
                Spacer(Modifier.height(12.dp))
                val next = state.nextUp
                val line = when {
                    state.totalCount == 0 -> "No reminders today"
                    state.doneCount == state.totalCount -> "All done for today 🎉"
                    next != null -> "Next: ${next.reminder.title} · ${next.reminder.let { java.time.LocalTime.of(it.hour, it.minute).format(DateTimeFormatter.ofPattern("h:mm a")) }}"
                    else -> "${state.totalCount - state.doneCount} left to check off"
                }
                Text(
                    line,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(12.dp))
            ProgressRing(
                progress = state.progress,
                trackColor = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.12f),
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        "${state.doneCount}/${state.totalCount}",
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                    Text("done", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
            }
        }
    }
}

@Composable
private fun PermissionBanner(count: Int, onFix: () -> Unit) {
    Card(
        onClick = onFix,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
        shape = MaterialTheme.shapes.large,
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.WarningAmber, null, tint = MaterialTheme.colorScheme.onErrorContainer)
            Spacer(Modifier.width(12.dp))
            Text(
                "$count setting${if (count > 1) "s" else ""} needed so alarms fire on time. Tap to fix.",
                color = MaterialTheme.colorScheme.onErrorContainer,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(start = 4.dp, top = 12.dp, bottom = 2.dp),
    )
}

@Composable
private fun SwipeToDelete(
    reminder: Reminder,
    onDelete: (Reminder) -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val state = rememberSwipeToDismissBoxState(
        confirmValueChange = {
            if (it == SwipeToDismissBoxValue.EndToStart) { onDelete(reminder); true } else false
        },
    )
    SwipeToDismissBox(
        state = state,
        modifier = modifier,
        enableDismissFromStartToEnd = false,
        backgroundContent = {
            Box(
                Modifier
                    .fillMaxSize()
                    .clip(MaterialTheme.shapes.large)
                    .background(MaterialTheme.colorScheme.errorContainer)
                    .padding(end = 24.dp),
                contentAlignment = Alignment.CenterEnd,
            ) {
                Icon(Icons.Rounded.DeleteOutline, "Delete", tint = MaterialTheme.colorScheme.onErrorContainer)
            }
        },
    ) { content() }
}

@Composable
private fun TimelineRow(
    reminder: Reminder,
    done: Boolean,
    overdue: Boolean,
    isNext: Boolean,
    showCheck: Boolean,
    onToggleDone: () -> Unit,
    onToggleEnabled: (Boolean) -> Unit,
    onClick: () -> Unit,
) {
    val accent = reminder.colorArgb.asColor()
    val haptics = LocalHapticFeedback.current
    val contentAlpha by animateFloatAsState(if (reminder.enabled) 1f else 0.45f, label = "alpha")
    val time = java.time.LocalTime.of(reminder.hour, reminder.minute)

    Row(
        Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .background(MaterialTheme.colorScheme.background)
            .alpha(contentAlpha),
    ) {
        // Time column
        Column(Modifier.width(54.dp).padding(top = 18.dp), horizontalAlignment = Alignment.End) {
            Text(time.format(timeFmt), style = MaterialTheme.typography.titleMedium)
            Text(time.format(ampmFmt), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        // Timeline rail + dot
        Box(Modifier.width(28.dp).fillMaxHeight(), contentAlignment = Alignment.TopCenter) {
            Box(Modifier.width(2.dp).fillMaxHeight().background(MaterialTheme.colorScheme.outlineVariant))
            TimelineDot(accent, done, isNext, Modifier.padding(top = 22.dp))
        }
        // Card
        Card(
            onClick = onClick,
            modifier = Modifier.weight(1f).padding(vertical = 2.dp),
            shape = MaterialTheme.shapes.large,
            colors = CardDefaults.cardColors(
                containerColor = if (isNext) accent.copy(alpha = 0.10f) else MaterialTheme.colorScheme.surfaceContainerLow,
            ),
        ) {
            Row(Modifier.padding(start = 12.dp, top = 12.dp, bottom = 12.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                AnimatedIconBadge(Catalog.icon(reminder.iconKey), accent)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        reminder.title,
                        style = MaterialTheme.typography.titleMedium,
                        textDecoration = if (done) TextDecoration.LineThrough else null,
                        color = if (done) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                    )
                    if (reminder.notes.isNotBlank()) {
                        Text(
                            reminder.notes, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        )
                    }
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Pill(reminder.repeatSummary(), accent)
                        if (reminder.vibrateOnly) Pill("Silent", MaterialTheme.colorScheme.secondary, Icons.Rounded.Vibration)
                        if (reminder.discreetLabel.isNotBlank()) Pill("Private", MaterialTheme.colorScheme.secondary, Icons.Rounded.Lock)
                        if (overdue && showCheck) Pill("Overdue", MaterialTheme.colorScheme.error)
                    }
                }
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Switch(
                        checked = reminder.enabled,
                        onCheckedChange = onToggleEnabled,
                        modifier = Modifier.scale(0.8f),
                    )
                    AnimatedVisibility(showCheck && reminder.enabled) {
                        CheckButton(done, accent) {
                            haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                            onToggleDone()
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TimelineDot(color: Color, done: Boolean, pulsing: Boolean, modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "dot")
    val pulse by transition.animateFloat(
        initialValue = 1f, targetValue = if (pulsing) 1.6f else 1f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "pulse",
    )
    Box(modifier.size(22.dp), contentAlignment = Alignment.Center) {
        if (pulsing) Box(Modifier.size(12.dp).scale(pulse).clip(CircleShape).background(color.copy(alpha = 0.25f)))
        Box(Modifier.size(12.dp).clip(CircleShape).background(color), contentAlignment = Alignment.Center) {
            if (!done) Box(Modifier.size(7.dp).clip(CircleShape).background(MaterialTheme.colorScheme.background))
        }
    }
}

@Composable
private fun CheckButton(done: Boolean, accent: Color, onClick: () -> Unit) {
    val scale by animateFloatAsState(if (done) 1.15f else 1f, label = "checkScale")
    val tint by animateColorAsState(if (done) accent else MaterialTheme.colorScheme.outline, label = "checkTint")
    IconButton(onClick = onClick, modifier = Modifier.size(40.dp)) {
        Icon(
            if (done) Icons.Rounded.CheckCircle else Icons.Rounded.RadioButtonUnchecked,
            contentDescription = if (done) "Mark not done" else "Mark done",
            tint = tint,
            modifier = Modifier.scale(scale).size(28.dp),
        )
    }
}

@Composable
private fun EmptyState(onAdd: () -> Unit, onIntervals: () -> Unit) {
    val transition = rememberInfiniteTransition(label = "empty")
    val bob by transition.animateFloat(
        0.94f, 1.06f, infiniteRepeatable(tween(1400), RepeatMode.Reverse), label = "bob",
    )
    Column(
        Modifier.fillMaxWidth().padding(top = 40.dp, start = 24.dp, end = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(
            Modifier.size(120.dp).scale(bob).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Rounded.Add, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(56.dp))
        }
        Text("Build your routine", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Nothing is pre-set. Add your first reminder — pick the time, repeat days, color, icon and how it should alert you.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Button(onClick = onAdd) { Icon(Icons.Rounded.Add, null); Spacer(Modifier.width(6.dp)); Text("Create first reminder") }
        OutlinedButton(onClick = onIntervals) { Icon(Icons.Rounded.Timer, null); Spacer(Modifier.width(6.dp)); Text("Add interval nudge") }
    }
}
