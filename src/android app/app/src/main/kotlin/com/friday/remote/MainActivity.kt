package com.friday.remote

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.network.FridaySocketService
import com.friday.remote.security.SecurityManager
import com.friday.remote.ui.screens.CameraScreen
import com.friday.remote.ui.screens.ChatScreen
import com.friday.remote.ui.screens.DashboardScreen
import com.friday.remote.ui.screens.SettingsScreen
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayDark
import com.friday.remote.ui.theme.FridayGrey
import com.friday.remote.ui.theme.FridayTheme
import com.friday.remote.voice.VoiceSessionManager
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var socketManager: FridaySocketManager
    @Inject lateinit var voiceManager: VoiceSessionManager
    @Inject lateinit var securityManager: SecurityManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val serviceIntent = Intent(this, FridaySocketService::class.java)
        startForegroundService(serviceIntent)

        setContent {
            FridayTheme {
                MainApp(socketManager, voiceManager, securityManager)
            }
        }
    }
}

@Composable
fun MainApp(
    socketManager: FridaySocketManager,
    voiceManager: VoiceSessionManager,
    securityManager: SecurityManager
) {
    val navController = rememberNavController()
    val connectionState by socketManager.connectionState.collectAsState()
    val pendingApproval by socketManager.pendingApproval.collectAsState()
    val sessionActive by socketManager.sessionActive.collectAsState()
    var selectedTab by remember { mutableStateOf("dashboard") }

    if (pendingApproval != null) {
        AlertDialog(
            onDismissRequest = { },
            title = { Text(pendingApproval!!.title) },
            text = { Text(pendingApproval!!.message) },
            confirmButton = {
                Button(onClick = { socketManager.respondToApproval(pendingApproval!!.id, true) }) {
                    Text("Approve")
                }
            },
            dismissButton = {
                TextButton(onClick = { socketManager.respondToApproval(pendingApproval!!.id, false) }) {
                    Text("Deny")
                }
            }
        )
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                listOf("Dashboard", "Chat", "Camera", "Settings").forEach { item ->
                    val tab = item.lowercase()
                    NavigationBarItem(
                        icon = { },
                        label = { Text(item) },
                        selected = selectedTab == tab,
                        onClick = {
                            selectedTab = tab
                            navController.navigate(tab)
                        }
                    )
                }
            }
        },
        floatingActionButton = {
            VoiceFAB(active = sessionActive, onToggle = { voiceManager.toggleSession() })
        },
        floatingActionButtonPosition = FabPosition.Center,
        snackbarHost = {
            if (connectionState == FridaySocketManager.ConnectionState.DISCONNECTED) {
                Snackbar { Text("Disconnected from server") }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = "dashboard",
            modifier = Modifier.padding(innerPadding)
        ) {
            composable("dashboard") { DashboardScreen(socketManager) }
            composable("chat") { ChatScreen(socketManager) }
            composable("camera") { CameraScreen(socketManager) }
            composable("settings") { SettingsScreen(socketManager, securityManager) }
        }
    }
}

@Composable
fun VoiceFAB(active: Boolean, onToggle: () -> Unit) {
    FloatingActionButton(
        onClick = { onToggle() },
        containerColor = if (active) FridayAccent else FridayGrey
    ) {
        Icon(
            Icons.Default.Mic,
            contentDescription = if (active) "Stop Friday session" else "Start Friday session",
            tint = if (active) FridayDark else FridayAccent
        )
    }
}
