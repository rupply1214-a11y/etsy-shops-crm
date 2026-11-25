@file:OptIn(ExperimentalMaterial3Api::class)

package com.rish.smartroutine.ui.settings

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rish.smartroutine.data.SettingsStore
import com.rish.smartroutine.data.ThemeMode
import com.rish.smartroutine.ui.components.PermissionRow
import com.rish.smartroutine.ui.components.SectionCard
import com.rish.smartroutine.ui.components.launchSafely
import com.rish.smartroutine.util.AlarmPermission
import com.rish.smartroutine.util.Permissions

@Composable
fun SettingsScreen(settings: SettingsStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val theme by settings.themeMode.collectAsStateWithLifecycle()
    val dynamic by settings.dynamicColor.collectAsStateWithLifecycle()

    // Bumped on resume so permission rows refresh after returning from system settings.
    var refresh by remember { mutableIntStateOf(0) }
    LifecycleResumeEffect(Unit) { refresh++; onPauseOrDispose { } }

    val notifLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) context.launchSafely(Permissions.settingsIntent(context, AlarmPermission.NOTIFICATIONS))
        refresh++
    }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back") } },
                title = { Text("Settings") },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SectionCard("Appearance") {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    ThemeMode.entries.forEachIndexed { i, mode ->
                        SegmentedButton(
                            selected = theme == mode,
                            onClick = { settings.setThemeMode(mode) },
                            shape = SegmentedButtonDefaults.itemShape(i, ThemeMode.entries.size),
                            label = { Text(mode.label) },
                        )
                    }
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    ListItem(
                        headlineContent = { Text("Wallpaper colors (Material You)") },
                        trailingContent = { Switch(checked = dynamic, onCheckedChange = settings::setDynamicColor) },
                        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                    )
                }
            }

            SectionCard("Alarm reliability") {
                // key(refresh) re-reads every status after returning from system settings.
                key(refresh) {
                    Permissions.applicable().forEachIndexed { i, p ->
                        if (i > 0) HorizontalDivider()
                        PermissionRow(p.title, p.why, Permissions.isGranted(context, p)) {
                            if (p == AlarmPermission.NOTIFICATIONS && Build.VERSION.SDK_INT >= 33) {
                                notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                            } else {
                                context.launchSafely(Permissions.settingsIntent(context, p))
                            }
                        }
                    }
                }
            }

            Permissions.aggressiveOem()?.let { brand ->
                SectionCard("Extra step for ${brand.replaceFirstChar { it.uppercase() }} phones") {
                    Text(
                        "This brand may stop background apps even when battery optimization is off. Open App info and:\n" +
                            "• Turn ON Autostart / Auto-launch\n" +
                            "• Battery → No restrictions / Allow background activity\n" +
                            "• Lock the app in Recent apps (pull down on its card → lock icon)",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    OutlinedButton(onClick = { context.launchSafely(Permissions.appDetails(context)) }) {
                        Text("Open App info")
                    }
                }
            }

            SectionCard("Your data") {
                Text(
                    "Everything is stored only on this phone in a local database. No account, no internet, no tracking. " +
                        "Daily check-offs reset automatically at midnight; your schedule is never changed.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
