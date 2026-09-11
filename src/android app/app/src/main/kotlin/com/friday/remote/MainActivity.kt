package com.friday.remote

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.network.FridaySocketService
import com.friday.remote.security.SecurityManager
import com.friday.remote.ui.screens.AutonomyScreen
import com.friday.remote.ui.screens.CADScreen
import com.friday.remote.ui.screens.CameraScreen
import com.friday.remote.ui.screens.ChatScreen
import com.friday.remote.ui.screens.DashboardScreen
import com.friday.remote.ui.screens.FileManagementScreen
import com.friday.remote.ui.screens.GoogleServicesScreen
import com.friday.remote.ui.screens.KasaScreen
import com.friday.remote.ui.screens.PrinterScreen
import com.friday.remote.ui.screens.RemindersScreen
import com.friday.remote.ui.screens.SettingsScreen
import com.friday.remote.ui.screens.TasksScreen
import com.friday.remote.ui.screens.WeatherScreen
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayDark
import com.friday.remote.ui.theme.FridayGrey
import com.friday.remote.ui.theme.FridayTheme
import com.friday.remote.voice.VoiceSessionManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var socketManager: FridaySocketManager
    @Inject lateinit var voiceManager: VoiceSessionManager
    @Inject lateinit var securityManager: SecurityManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        android.util.Log.d("FridayApp", "MainActivity onCreate()")
        android.util.Log.d("FridayApp", "Server URL: ${securityManager.getServerUrl()}")
        android.util.Log.d("FridayApp", "TLS: ${securityManager.isTlsEnabled()}")
        
        val serviceIntent = Intent(this, FridaySocketService::class.java)
        android.util.Log.d("FridayApp", "Starting FridaySocketService...")
        startForegroundService(serviceIntent)

        setContent {
            FridayTheme {
                MainApp(socketManager, voiceManager, securityManager)
            }
        }
    }
    
    override fun onResume() {
        super.onResume()
        android.util.Log.d("FridayApp", "MainActivity onResume() - refreshing data")
        socketManager.refreshAll()
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
    val weatherData by socketManager.weatherData.collectAsState()
    val googleServices by socketManager.googleServices.collectAsState()
    val systemAlerts by socketManager.systemAlerts.collectAsState()
    var selectedTab by remember { mutableStateOf("dashboard") }
    var showNotifications by remember { mutableStateOf(false) }
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val coroutineScope = rememberCoroutineScope()

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

    ModalNavigationDrawer(
        drawerContent = {
            DrawerContent(
                navController = navController,
                onClose = { coroutineScope.launch { drawerState.close() } },
                currentTab = selectedTab,
                onTabSelect = { selectedTab = it }
            )
        },
        drawerState = drawerState,
        gesturesEnabled = true
    ) {
        Scaffold(
            topBar = {
                HUDTopBar(
                    connectionState = connectionState,
                    weatherData = weatherData,
                    googleServices = googleServices,
                    onMenuClick = { coroutineScope.launch { drawerState.open() } },
                    onNotificationClick = { showNotifications = true },
                    notificationCount = systemAlerts.size
                )
            },
            bottomBar = {
                NavigationBar {
                    listOf(
                        "Dashboard" to Icons.Default.Dashboard,
                        "Chat" to Icons.AutoMirrored.Filled.Chat,
                        "Files" to Icons.Default.FolderOpen,
                        "Camera" to Icons.Default.CameraAlt,
                        "Settings" to Icons.Default.Settings
                    ).forEach { (item, icon) ->
                        val tab = item.lowercase()
                        NavigationBarItem(
                            icon = { Icon(icon, contentDescription = item) },
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
            floatingActionButtonPosition = FabPosition.Center
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = "dashboard",
                modifier = Modifier.padding(innerPadding)
            ) {
                composable("dashboard") { DashboardScreen(socketManager) }
                composable("chat") { ChatScreen(socketManager) }
                composable("files") { FileManagementScreen(socketManager) }
                composable("camera") { CameraScreen(socketManager) }
                composable("settings") { SettingsScreen(socketManager, securityManager) }
                composable("weather") { WeatherScreen(socketManager) }
                composable("google") { GoogleServicesScreen(socketManager) }
                composable("kasa") { KasaScreen(socketManager) }
                composable("printers") { PrinterScreen(socketManager) }
                composable("cad") { CADScreen(socketManager) }
                composable("autonomy") { AutonomyScreen(socketManager) }
                composable("tasks") { TasksScreen(socketManager) }
                composable("reminders") { RemindersScreen(socketManager) }
            }
        }
    }

    if (showNotifications) {
        NotificationPanel(
            alerts = systemAlerts,
            onDismiss = { showNotifications = false },
            onClear = { socketManager.clearAlerts() }
        )
    }
}

@Composable
fun VoiceFAB(active: Boolean, onToggle: () -> Unit) {
    Box(
        modifier = Modifier.size(72.dp)
    ) {
        // Ripple effect when active
        if (active) {
            androidx.compose.foundation.Canvas(
                modifier = Modifier.fillMaxSize()
            ) {
                val currentTime = System.currentTimeMillis()
                val radius = ((currentTime % 1000) / 1000f) * size.width / 2
                val alpha = 1f - ((currentTime % 1000) / 1000f)
                
                drawCircle(
                    color = FridayAccent.copy(alpha = alpha * 0.5f),
                    radius = radius,
                    center = center
                )
            }
        }

        FloatingActionButton(
            onClick = { onToggle() },
            containerColor = if (active) FridayAccent else FridayGrey,
            modifier = Modifier.size(56.dp)
        ) {
            Icon(
                if (active) Icons.Default.Mic else Icons.Default.MicOff,
                contentDescription = if (active) "Stop Friday session" else "Start Friday session",
                tint = if (active) FridayDark else FridayAccent,
                modifier = Modifier.size(24.dp)
            )
        }
        
        // Status indicator
        if (active) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .background(Color.Red, CircleShape)
                    .align(Alignment.TopEnd)
            )
        }
    }
}

@Composable
fun HUDTopBar(
    connectionState: FridaySocketManager.ConnectionState,
    weatherData: FridaySocketManager.WeatherData?,
    googleServices: FridaySocketManager.GoogleServices?,
    onMenuClick: () -> Unit,
    onNotificationClick: () -> Unit,
    notificationCount: Int
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(60.dp)
            .background(Color.Black.copy(alpha = 0.8f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Menu button
            IconButton(onClick = onMenuClick) {
                Icon(Icons.Default.Menu, contentDescription = "Menu", tint = Color.White)
            }

            // Connection status and weather
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                // Connection indicator
                ConnectionIndicator(connectionState)
                
                // Weather display
                weatherData?.let { weather ->
                    WeatherMiniDisplay(weather)
                }
            }

            // Google services and notifications
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                googleServices?.let { services ->
                    GoogleServicesMiniIndicator(services)
                }
                
                // Notifications bell
                Box {
                    IconButton(onClick = onNotificationClick) {
                        Icon(Icons.Default.Notifications, contentDescription = "Notifications", tint = Color.White)
                    }
                    if (notificationCount > 0) {
                        Box(
                            modifier = Modifier
                                .size(16.dp)
                                .background(Color.Red, CircleShape)
                                .align(Alignment.TopEnd)
                        ) {
                            Text(
                                text = if (notificationCount > 9) "9+" else notificationCount.toString(),
                                color = Color.White,
                                fontSize = 10.sp,
                                modifier = Modifier.align(Alignment.Center)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ConnectionIndicator(state: FridaySocketManager.ConnectionState) {
    val (color, icon) = when (state) {
        FridaySocketManager.ConnectionState.CONNECTED -> Color(0xFF4CAF50) to Icons.Default.Wifi
        FridaySocketManager.ConnectionState.CONNECTING -> Color(0xFFFF9800) to Icons.Default.Wifi
        FridaySocketManager.ConnectionState.DISCONNECTED -> Color(0xFFFF5252) to Icons.Default.WifiOff
        FridaySocketManager.ConnectionState.ERROR -> Color(0xFFFF5252) to Icons.Default.Error
    }
    
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(16.dp))
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = state.name.lowercase(),
            color = color,
            fontSize = 11.sp,
            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
        )
    }
}

@Composable
fun WeatherMiniDisplay(weather: FridaySocketManager.WeatherData) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .background(Color.DarkGray, CircleShape)
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Icon(Icons.Default.Cloud, contentDescription = null, tint = Color.LightGray, modifier = Modifier.size(14.dp))
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = "${weather.temperature}°${weather.unit}",
            color = Color.White,
            fontSize = 11.sp
        )
    }
}

@Composable
fun GoogleServicesMiniIndicator(services: FridaySocketManager.GoogleServices) {
    if (services.connected) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .background(Color(0xFF4285F4), CircleShape)
                .padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color.White, modifier = Modifier.size(12.dp))
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = "G",
                color = Color.White,
                fontSize = 10.sp,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
            )
        }
    }
}

@Composable
fun DrawerContent(
    navController: androidx.navigation.NavController,
    onClose: () -> Unit,
    currentTab: String,
    onTabSelect: (String) -> Unit
) {
    val navigationItems = listOf(
        Triple("Dashboard", Icons.Default.Dashboard, "dashboard"),
        Triple("Chat", Icons.AutoMirrored.Filled.Chat, "chat"),
        Triple("Files", Icons.Default.FolderOpen, "files"),
        Triple("Camera", Icons.Default.CameraAlt, "camera"),
        Triple("Settings", Icons.Default.Settings, "settings"),
        Triple("Weather", Icons.Default.Cloud, "weather"),
        Triple("Google Services", Icons.Default.Assistant, "google"),
        Triple("Smart Home", Icons.Default.Lightbulb, "kasa"),
        Triple("Printers", Icons.Default.Print, "printers"),
        Triple("CAD & 3D", Icons.Default.Extension, "cad"),
        Triple("Autonomy", Icons.Default.Memory, "autonomy"),
        Triple("Tasks", Icons.Default.Assistant, "tasks"),
        Triple("Reminders", Icons.Default.Notifications, "reminders")
    )

    Column(
        modifier = Modifier
            .fillMaxHeight()
            .width(280.dp)
            .background(Color.Black.copy(alpha = 0.95f))
            .padding(16.dp)
    ) {
        Text(
            text = "F.R.I.D.A.Y",
            color = FridayAccent,
            fontSize = 24.sp,
            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
            modifier = Modifier.padding(bottom = 24.dp)
        )

        LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(navigationItems) { (label, icon, route) ->
                NavigationDrawerItem(
                    icon = { Icon(icon, contentDescription = label) },
                    label = { Text(label) },
                    selected = currentTab == route,
                    onClick = {
                        onTabSelect(route)
                        navController.navigate(route)
                        onClose()
                    },
                    colors = NavigationDrawerItemDefaults.colors(
                        selectedContainerColor = FridayAccent.copy(alpha = 0.2f),
                        selectedTextColor = FridayAccent
                    )
                )
            }
        }
    }
}

@Composable
fun NotificationPanel(
    alerts: List<FridaySocketManager.SystemAlert>,
    onDismiss: () -> Unit,
    onClear: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { 
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("System Alerts", color = Color.White)
                TextButton(onClick = onClear) {
                    Text("Clear All", color = FridayAccent, fontSize = 12.sp)
                }
            }
        },
        text = {
            if (alerts.isEmpty()) {
                Text("No active alerts", color = Color.LightGray)
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(alerts) { alert ->
                        AlertCard(alert)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Close", color = Color.LightGray)
            }
        }
    )
}

@Composable
fun AlertCard(alert: FridaySocketManager.SystemAlert) {
    val (color, icon) = when (alert.severity) {
        "urgent" -> Color(0xFFFF5252) to Icons.Default.Error
        "warning" -> Color(0xFFFF9800) to Icons.Default.Notifications
        else -> Color(0xFF4CAF50) to Icons.Default.CheckCircle
    }
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color.DarkGray),
        shape = RoundedCornerShape(8.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = alert.title,
                    color = Color.White,
                    fontSize = 14.sp,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                )
                Text(
                    text = alert.message,
                    color = Color.LightGray,
                    fontSize = 12.sp
                )
            }
        }
    }
}
