@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package com.rish.smartroutine.ui.components

import android.content.Context
import android.content.Intent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.rish.smartroutine.alarm.Haptics
import com.rish.smartroutine.data.VibrationPattern
import com.rish.smartroutine.data.bit
import com.rish.smartroutine.data.hasDay

/** Animated circular progress ring with custom center content. */
@Composable
fun ProgressRing(
    progress: Float,
    modifier: Modifier = Modifier,
    size: Dp = 104.dp,
    stroke: Dp = 10.dp,
    trackColor: Color = MaterialTheme.colorScheme.surfaceContainerHigh,
    color: Color = MaterialTheme.colorScheme.primary,
    content: @Composable () -> Unit = {},
) {
    val animated by animateFloatAsState(
        targetValue = progress.coerceIn(0f, 1f),
        animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy, stiffness = Spring.StiffnessVeryLow),
        label = "ring",
    )
    Box(modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(size)) {
            val s = Stroke(width = stroke.toPx(), cap = StrokeCap.Round)
            drawArc(trackColor, 0f, 360f, useCenter = false, style = s)
            if (animated > 0f) drawArc(color, -90f, 360f * animated, useCenter = false, style = s)
        }
        content()
    }
}

@Composable
fun SectionCard(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
        shape = MaterialTheme.shapes.large,
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
            content()
        }
    }
}

/** M T W T F S S toggle circles. */
@Composable
fun DaySelector(mask: Int, onChange: (Int) -> Unit, accent: Color = MaterialTheme.colorScheme.primary) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        orderedDays.forEach { day ->
            val on = mask.hasDay(day)
            val bg by animateColorAsState(if (on) accent else Color.Transparent, label = "day")
            val fg = if (on) Color.White else MaterialTheme.colorScheme.onSurfaceVariant
            Box(
                Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(bg)
                    .border(1.dp, if (on) accent else MaterialTheme.colorScheme.outlineVariant, CircleShape)
                    .clickable { onChange(mask xor day.bit()) },
                contentAlignment = Alignment.Center,
            ) {
                Text(day.short().take(2), color = fg, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
fun ColorPickerRow(selected: Long, onSelect: (Long) -> Unit) {
    Row(
        Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Catalog.colors.forEach { c ->
            val isSel = c == selected
            val scale by animateFloatAsState(if (isSel) 1.12f else 1f, label = "colorScale")
            Box(
                Modifier
                    .scale(scale)
                    .size(38.dp)
                    .clip(CircleShape)
                    .background(c.asColor())
                    .clickable { onSelect(c) },
                contentAlignment = Alignment.Center,
            ) {
                if (isSel) Icon(Icons.Rounded.Check, null, tint = Color.White, modifier = Modifier.size(20.dp))
            }
        }
    }
}

@Composable
fun IconPicker(selectedKey: String, accent: Color, onSelect: (String) -> Unit) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Catalog.icons.forEach { (key, vector) ->
            val isSel = key == selectedKey
            val bg by animateColorAsState(
                if (isSel) accent else MaterialTheme.colorScheme.surfaceContainerHigh, label = "iconBg",
            )
            Box(
                Modifier
                    .size(46.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(bg)
                    .clickable { onSelect(key) },
                contentAlignment = Alignment.Center,
            ) {
                Icon(vector, key, tint = if (isSel) Color.White else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Pattern chips; tapping one also plays a short preview. */
@Composable
fun VibrationPatternPicker(selected: VibrationPattern, context: Context, onSelect: (VibrationPattern) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        VibrationPattern.entries.forEach { p ->
            FilterChip(
                selected = p == selected,
                onClick = { onSelect(p); Haptics.play(context, p, repeat = false) },
                label = { Text(p.label) },
            )
        }
    }
}

@Composable
fun AnimatedIconBadge(icon: androidx.compose.ui.graphics.vector.ImageVector, color: Color, size: Dp = 44.dp) {
    Box(
        Modifier
            .size(size)
            .clip(RoundedCornerShape(size / 3))
            .background(color.copy(alpha = 0.16f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = color, modifier = Modifier.size(size * 0.55f))
    }
}

@Composable
fun TimePickerDialog(
    initialHour: Int,
    initialMinute: Int,
    title: String = "Select time",
    onDismiss: () -> Unit,
    onConfirm: (hour: Int, minute: Int) -> Unit,
) {
    val state = rememberTimePickerState(initialHour = initialHour, initialMinute = initialMinute, is24Hour = false)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { TimePicker(state = state) },
        confirmButton = { TextButton(onClick = { onConfirm(state.hour, state.minute) }) { Text("OK") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

/** One permission line with status + action. */
@Composable
fun PermissionRow(title: String, why: String, granted: Boolean, onFix: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Icon(
            if (granted) Icons.Rounded.CheckCircle else Icons.Rounded.ErrorOutline,
            null,
            tint = if (granted) Color(0xFF10B981) else MaterialTheme.colorScheme.error,
        )
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(why, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (!granted) {
            Spacer(Modifier.width(8.dp))
            FilledTonalButton(onClick = onFix) { Text("Allow") }
        }
    }
}

@Composable
fun Pill(text: String, color: Color, icon: androidx.compose.ui.graphics.vector.ImageVector? = null) {
    Row(
        Modifier
            .clip(CircleShape)
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 8.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = color, modifier = Modifier.size(12.dp))
            Spacer(Modifier.width(4.dp))
        }
        Text(text, style = MaterialTheme.typography.labelSmall, color = color)
    }
}

/** Start an activity, falling back to the app's info page if the screen doesn't exist on this OEM build. */
fun Context.launchSafely(intent: Intent) {
    try {
        startActivity(intent)
    } catch (_: Exception) {
        runCatching { startActivity(com.rish.smartroutine.util.Permissions.appDetails(this)) }
    }
}
