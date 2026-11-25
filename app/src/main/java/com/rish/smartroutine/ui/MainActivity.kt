package com.rish.smartroutine.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.rish.smartroutine.container
import com.rish.smartroutine.ui.editor.EditorScreen
import com.rish.smartroutine.ui.editor.EditorViewModel
import com.rish.smartroutine.ui.home.HomeScreen
import com.rish.smartroutine.ui.home.HomeViewModel
import com.rish.smartroutine.ui.interval.IntervalScreen
import com.rish.smartroutine.ui.interval.IntervalViewModel
import com.rish.smartroutine.ui.settings.SettingsScreen
import com.rish.smartroutine.ui.theme.SmartRoutineTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val c = container

        setContent {
            val mode by c.settings.themeMode.collectAsStateWithLifecycle()
            val dynamic by c.settings.dynamicColor.collectAsStateWithLifecycle()

            // Ask for notification permission once on first launch (Android 13+).
            val notifLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
            LaunchedEffect(Unit) {
                if (Build.VERSION.SDK_INT >= 33 &&
                    ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.POST_NOTIFICATIONS) !=
                    PackageManager.PERMISSION_GRANTED
                ) notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }

            SmartRoutineTheme(mode = mode, dynamicColor = dynamic) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    val nav = rememberNavController()
                    NavHost(
                        navController = nav,
                        startDestination = "home",
                        enterTransition = { slideInHorizontally { it / 4 } + fadeIn() },
                        exitTransition = { fadeOut() },
                        popEnterTransition = { fadeIn() },
                        popExitTransition = { slideOutHorizontally { it / 4 } + fadeOut() },
                    ) {
                        composable("home") {
                            HomeScreen(
                                vm = viewModel { HomeViewModel(c.repository) },
                                onAdd = { nav.navigate("editor") },
                                onEdit = { id -> nav.navigate("editor?id=$id") },
                                onIntervals = { nav.navigate("intervals") },
                                onSettings = { nav.navigate("settings") },
                            )
                        }
                        composable(
                            "editor?id={id}",
                            arguments = listOf(navArgument("id") { type = NavType.LongType; defaultValue = -1L }),
                        ) { entry ->
                            val id = entry.arguments?.getLong("id")?.takeIf { it > 0 }
                            EditorScreen(
                                vm = viewModel(key = "editor_$id") { EditorViewModel(c.repository, id) },
                                onClose = { nav.popBackStack() },
                            )
                        }
                        composable("intervals") {
                            IntervalScreen(vm = viewModel { IntervalViewModel(c.repository) }, onBack = { nav.popBackStack() })
                        }
                        composable("settings") {
                            SettingsScreen(settings = c.settings, onBack = { nav.popBackStack() })
                        }
                    }
                }
            }
        }
    }
}
