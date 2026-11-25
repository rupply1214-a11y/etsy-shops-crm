package com.rish.smartroutine.ui.alarm

import android.app.KeyguardManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Snooze
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import com.rish.smartroutine.alarm.AlarmActions
import com.rish.smartroutine.alarm.AlarmState
import com.rish.smartroutine.alarm.RingingAlarm
import com.rish.smartroutine.container
import com.rish.smartroutine.ui.components.Catalog
import com.rish.smartroutine.ui.components.asColor
import com.rish.smartroutine.ui.components.courseBadge
import com.rish.smartroutine.ui.components.shortLabel
import com.rish.smartroutine.ui.theme.SmartRoutineTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalTime
import java.time.format.DateTimeFormatter

/** Full-screen alarm shown over the lock screen with Mark Done / Snooze / Dismiss. */
class AlarmActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enableEdgeToEdge()
        onBackPressedDispatcher.addCallback(this) { /* force an explicit choice */ }

        // Close when the alarm stops (done from the notification, timeout, etc.).
        lifecycleScope.launch {
            var seen = false
            AlarmState.ringing.collect { if (it != null) seen = true else if (seen) finish() }
        }
        lifecycleScope.launch { delay(4_000); if (AlarmState.ringing.value == null) finish() }

        val locked = getSystemService(KeyguardManager::class.java).isKeyguardLocked
        val settings = container.settings

        setContent {
            val mode by settings.themeMode.collectAsStateWithLifecycle()
            val ringing by AlarmState.ringing.collectAsStateWithLifecycle()
            SmartRoutineTheme(mode = mode, dynamicColor = false) {
                ringing?.let { alarm ->
                    AlarmScreen(
                        alarm = alarm,
                        locked = locked,
                        onDone = {
                            lifecycleScope.launch {
                                withContext(Dispatchers.IO) { AlarmActions.done(this@AlarmActivity, alarm.reminder.id, alarm.day) }
                                finish()
                            }
                        },
                        onSnooze = { m -> AlarmActions.snooze(this, alarm.reminder.id, alarm.day, m); finish() },
                        onDismiss = { AlarmActions.dismiss(this); finish() },
                    )
                } ?: Box(Modifier.fillMaxSize().background(Color.Black))
            }
        }
    }
}

@Composable
private fun AlarmScreen(
    alarm: RingingAlarm,
    locked: Boolean,
    onDone: () -> Unit,
    onSnooze: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    val r = alarm.reminder
    val accent = r.colorArgb.asColor()
    val title = if (locked) r.lockScreenTitle() else r.title
    val showNotes = r.notes.isNotBlank() && !(locked && r.discreetLabel.isNotBlank())

    var clock by remember { mutableStateOf(LocalTime.now()) }
    LaunchedEffect(Unit) { while (true) { clock = LocalTime.now(); delay(1_000) } }

    val transition = rememberInfiniteTransition(label = "alarm")
    val ring1 by transition.animateFloat(1f, 2.1f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "r1")
    val fade1 by transition.animateFloat(0.45f, 0f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "f1")
    val breathe by transition.animateFloat(0.96f, 1.04f, infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "b")

    Box(
        Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(accent.copy(alpha = 0.95f), Color(0xFF0E0F14))))
            .safeDrawingPadding()
            .padding(24.dp),
    ) {
        Column(
            Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Spacer(Modifier.height(24.dp))
                Text(
                    clock.format(DateTimeFormatter.ofPattern("h:mm")),
                    style = MaterialTheme.typography.displayLarge,
                    color = Color.White,
                )
                Text(clock.format(DateTimeFormatter.ofPattern("a")), color = Color.White.copy(alpha = 0.7f))
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(contentAlignment = Alignment.Center, modifier = Modifier.size(200.dp)) {
                    Box(Modifier.size(96.dp).scale(ring1).alpha(fade1).clip(CircleShape).background(Color.White))
                    Box(
                        Modifier.size(104.dp).scale(breathe).clip(CircleShape).background(Color.White),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Catalog.icon(r.iconKey), null, tint = accent, modifier = Modifier.size(52.dp))
                    }
                }
                Spacer(Modifier.height(16.dp))
                Text(
                    title,
                    style = MaterialTheme.typography.headlineMedium,
                    color = Color.White,
                    textAlign = TextAlign.Center,
                    fontWeight = FontWeight.Bold,
                )
                val today = java.time.LocalDate.ofEpochDay(alarm.day)
                if (r.isFiniteCourse) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        r.courseBadge(today) + (r.endDate?.let { " · ends ${it.shortLabel()}" } ?: ""),
                        color = Color.White,
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.18f))
                            .padding(horizontal = 14.dp, vertical = 6.dp),
                    )
                }
                val privateLocked = locked && r.discreetLabel.isNotBlank()
                if (r.isTaperingOn(today) && !privateLocked) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Tapering today: ${r.taperNote}",
                        color = Color(0xFFFFD27A),
                        fontWeight = FontWeight.SemiBold,
                        textAlign = TextAlign.Center,
                    )
                } else if (showNotes) {
                    Spacer(Modifier.height(8.dp))
                    Text(r.notes, color = Color.White.copy(alpha = 0.85f), textAlign = TextAlign.Center)
                }
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    listOf(5, 10, 15).forEach { m ->
                        val isDefault = m == r.snoozeMinutes
                        OutlinedButton(
                            onClick = { onSnooze(m) },
                            modifier = Modifier.weight(1f).height(52.dp),
                            colors = ButtonDefaults.outlinedButtonColors(
                                containerColor = if (isDefault) Color.White.copy(alpha = 0.18f) else Color.Transparent,
                                contentColor = Color.White,
                            ),
                        ) {
                            Icon(Icons.Rounded.Snooze, null, Modifier.size(18.dp))
                            Spacer(Modifier.size(4.dp))
                            Text("${m}m")
                        }
                    }
                }
                Spacer(Modifier.height(14.dp))
                Button(
                    onClick = onDone,
                    modifier = Modifier.fillMaxWidth().height(64.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = accent),
                ) {
                    Icon(Icons.Rounded.Check, null)
                    Spacer(Modifier.size(8.dp))
                    Text("Mark done", style = MaterialTheme.typography.titleMedium)
                }
                TextButton(onClick = onDismiss) { Text("Dismiss", color = Color.White.copy(alpha = 0.8f)) }
            }
        }
    }
}
