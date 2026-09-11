package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Camera
import androidx.compose.material.icons.filled.TouchApp
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.security.SecurityManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey

@Composable
fun SettingsScreen(socketManager: FridaySocketManager, securityManager: SecurityManager) {
    var url by remember { mutableStateOf(securityManager.getServerUrl()) }
    var token by remember { mutableStateOf(securityManager.getToken()) }
    var tls by remember { mutableStateOf(securityManager.isTlsEnabled()) }
    
    // Server settings
    var faceAuthEnabled by remember { mutableStateOf(false) }
    var systemAlertsEnabled by remember { mutableStateOf(true) }
    var quietMode by remember { mutableStateOf(false) }
    var urgentOnly by remember { mutableStateOf(false) }
    var emergenciesOnly by remember { mutableStateOf(false) }
    var currentMode by remember { mutableStateOf("active") }
    
    // Provider routing
    var voiceVisionProvider by remember { mutableStateOf("Gemini Live") }
    var textReasoningProvider by remember { mutableStateOf("Gemini") }
    var codingProvider by remember { mutableStateOf("OpenClaw") }
    
    // Tool permissions
    val tools = listOf(
        "generate_cad" to "Generate CAD",
        "run_web_agent" to "Web Agent",
        "computer_control" to "Computer Control",
        "manage_files" to "Manage Files",
        "web_search" to "Web Search",
        "send_message" to "Send Message",
        "code_helper" to "Code Helper",
        "process_file" to "Process File"
    )
    var toolPermissions by remember { mutableStateOf(mapOf<String, Boolean>()) }

    // Load settings from socket
    LaunchedEffect(Unit) {
        socketManager.requestSettings()
    }

    // Listen for settings updates
    val settings by socketManager.settings.collectAsState()
    LaunchedEffect(settings) {
        settings?.let {
            faceAuthEnabled = it.faceAuthEnabled
            systemAlertsEnabled = it.systemAlertsEnabled
            quietMode = it.quietMode
            urgentOnly = it.urgentOnly
            emergenciesOnly = it.emergenciesOnly
            currentMode = it.currentMode
            voiceVisionProvider = it.voiceVisionProvider
            textReasoningProvider = it.textReasoningProvider
            codingProvider = it.codingProvider
            toolPermissions = it.toolPermissions
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Connection Section
        item {
            SettingSection(
                title = "Connection",
                icon = Icons.Default.Security,
                description = "Server URL, token and TLS for your F.R.I.D.A.Y home server."
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    TextField(
                        value = url,
                        onValueChange = { url = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Server URL") },
                        placeholder = { Text("http://192.168.1.100:8000") },
                        colors = TextFieldDefaults.colors(
                            unfocusedContainerColor = FridayGrey,
                            focusedContainerColor = FridayGrey
                        ),
                        shape = RoundedCornerShape(12.dp),
                        singleLine = true
                    )
                    TextField(
                        value = token,
                        onValueChange = { token = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Auth token") },
                        colors = TextFieldDefaults.colors(
                            unfocusedContainerColor = FridayGrey,
                            focusedContainerColor = FridayGrey
                        ),
                        shape = RoundedCornerShape(12.dp),
                        singleLine = true
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("HTTPS (TLS)", color = Color.White)
                        Switch(checked = tls, onCheckedChange = { tls = it })
                    }
                    Button(
                        onClick = {
                            val finalUrl = normalizeUrl(url, tls)
                            android.util.Log.d("FridaySettings", "Saving settings:")
                            android.util.Log.d("FridaySettings", "  URL: $finalUrl")
                            android.util.Log.d("FridaySettings", "  TLS: $tls")
                            android.util.Log.d("FridaySettings", "  Token: ${if (token.isNotEmpty()) "[SET]" else "[EMPTY]"}")
                            
                            securityManager.setServerUrl(finalUrl)
                            securityManager.setToken(token)
                            securityManager.setTlsEnabled(tls)
                            
                            android.util.Log.d("FridaySettings", "Disconnecting and reconnecting...")
                            socketManager.disconnect()
                            socketManager.connect()
                            
                            navController.navigate("dashboard")
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = FridayAccent)
                    ) {
                        Text("Save & Reconnect", color = Color.Black)
                    }
                }
            }
        }

        // Security Section
        item {
            SettingSection(
                title = "Security",
                icon = Icons.Default.Security,
                description = "Authentication and security settings"
            ) {
                SettingToggle(
                    label = "Face Authentication",
                    description = "Require face authentication for access",
                    enabled = faceAuthEnabled,
                    onToggle = {
                        faceAuthEnabled = it
                        socketManager.updateSettings(mapOf("face_auth_enabled" to it))
                    }
                )
            }
        }

        // System Alerts Section
        item {
            SettingSection(
                title = "System Alerts",
                icon = Icons.Default.Notifications,
                description = "Proactive monitoring and notifications"
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SettingToggle(
                        label = "Proactive Alerts",
                        description = "Enable system monitoring alerts",
                        enabled = systemAlertsEnabled,
                        onToggle = {
                            systemAlertsEnabled = it
                            socketManager.updateSettings(mapOf("system_alerts_enabled" to it))
                        }
                    )
                    SettingToggle(
                        label = "Urgent Alerts Only",
                        description = "Only show urgent notifications",
                        enabled = urgentOnly,
                        onToggle = {
                            urgentOnly = it
                            socketManager.updateSettings(mapOf("urgent_only" to it))
                        }
                    )
                    SettingToggle(
                        label = "Emergencies Only",
                        description = "Only show emergency notifications",
                        enabled = emergenciesOnly,
                        onToggle = {
                            emergenciesOnly = it
                            socketManager.updateSettings(mapOf("emergencies_only" to it))
                        }
                    )
                }
            }
        }

        // Assistant Behavior Section
        item {
            SettingSection(
                title = "Assistant Behavior",
                icon = Icons.Default.Psychology,
                description = "Friday's behavior and response settings"
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SettingToggle(
                        label = "Quiet Mode",
                        description = "Reduce voice responses",
                        enabled = quietMode,
                        onToggle = {
                            quietMode = it
                            socketManager.updateSettings(mapOf("quiet_mode" to it))
                        },
                        icon = if (quietMode) Icons.Default.VolumeOff else Icons.Default.VolumeUp
                    )
                    
                    Text("Current Mode", color = Color.White, fontSize = 14.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf("active", "focus", "away").forEach { mode ->
                            FilterChip(
                                selected = currentMode == mode,
                                onClick = {
                                    currentMode = mode
                                    socketManager.updateSettings(mapOf("current_mode" to mode))
                                },
                                label = { Text(mode.capitalize()) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = FridayAccent,
                                    selectedLabelColor = Color.Black
                                )
                            )
                        }
                    }
                }
            }
        }

        // Provider Routing Section
        item {
            SettingSection(
                title = "Provider Routing",
                icon = Icons.Default.AccountCircle,
                description = "AI provider selection for different tasks"
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    ProviderSelector(
                        label = "Voice + Vision",
                        value = voiceVisionProvider,
                        options = listOf("Gemini Live"),
                        onValueChange = {
                            voiceVisionProvider = it
                            socketManager.updateSettings(mapOf("voice_vision_provider" to it))
                        }
                    )
                    ProviderSelector(
                        label = "Text Reasoning",
                        value = textReasoningProvider,
                        options = listOf("Gemini", "OpenClaw"),
                        onValueChange = {
                            textReasoningProvider = it
                            socketManager.updateSettings(mapOf("text_reasoning_provider" to it))
                        }
                    )
                    ProviderSelector(
                        label = "Coding",
                        value = codingProvider,
                        options = listOf("Gemini", "OpenClaw"),
                        onValueChange = {
                            codingProvider = it
                            socketManager.updateSettings(mapOf("coding_provider" to it))
                        }
                    )
                }
            }
        }

        // Tool Permissions Section
        item {
            SettingSection(
                title = "Tool Confirmations",
                icon = Icons.Default.CheckCircle,
                description = "Configure which tools require approval"
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    tools.forEach { (id, label) ->
                        PermissionToggle(
                            label = label,
                            autoRun = toolPermissions[id] == true,
                            onToggle = {
                                toolPermissions = toolPermissions.toMutableMap().apply { this[id] = it }
                                socketManager.updateSettings(mapOf("tool_permissions" to toolPermissions))
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun SettingSection(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    description: String,
    content: @Composable () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 12.dp)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = FridayAccent,
                    modifier = Modifier.padding(end = 12.dp)
                )
                Column {
                    Text(
                        text = title,
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                    )
                    Text(
                        text = description,
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                }
            }
            content()
        }
    }
}

@Composable
fun SettingToggle(
    label: String,
    description: String,
    enabled: Boolean,
    onToggle: (Boolean) -> Unit,
    icon: androidx.compose.ui.graphics.vector.ImageVector? = null
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
            icon?.let {
                Icon(
                    imageVector = it,
                    contentDescription = null,
                    tint = Color.LightGray,
                    modifier = Modifier.padding(end = 8.dp)
                )
            }
            Column {
                Text(
                    text = label,
                    color = Color.White,
                    fontSize = 14.sp
                )
                Text(
                    text = description,
                    color = Color.LightGray,
                    fontSize = 12.sp
                )
            }
        }
        Switch(
            checked = enabled,
            onCheckedChange = onToggle,
            colors = SwitchDefaults.colors(
                checkedThumbColor = FridayAccent,
                checkedTrackColor = FridayAccent.copy(alpha = 0.5f)
            )
        )
    }
}

@Composable
fun ProviderSelector(
    label: String,
    value: String,
    options: List<String>,
    onValueChange: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    
    Box {
        Button(
            onClick = { expanded = true },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Color.DarkGray)
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = label,
                    color = Color.LightGray,
                    fontSize = 12.sp
                )
                Text(
                    text = value,
                    color = Color.White,
                    fontSize = 14.sp
                )
            }
        }
        
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    onClick = {
                        onValueChange(option)
                        expanded = false
                    },
                    text = { Text(option) }
                )
            }
        }
    }
}

@Composable
fun PermissionToggle(
    label: String,
    autoRun: Boolean,
    onToggle: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            color = Color.White,
            fontSize = 13.sp,
            modifier = Modifier.weight(1f)
        )
        FilterChip(
            selected = autoRun,
            onClick = { onToggle(!autoRun) },
            label = { Text(if (autoRun) "AUTO" else "CONFIRM") },
            colors = FilterChipDefaults.filterChipColors(
                selectedContainerColor = FridayAccent,
                selectedLabelColor = Color.Black
            )
        )
    }
}

private fun normalizeUrl(raw: String, tls: Boolean): String {
    var clean = raw.trim()
    if (clean.isEmpty()) {
        val defaultUrl = if (tls) "https://192.168.1.100:8000" else "http://192.168.1.100:8000"
        android.util.Log.d("FridaySettings", "normalizeUrl: empty input, returning default: $defaultUrl")
        return defaultUrl
    }
    val lower = clean.lowercase()
    if (!lower.startsWith("http://") && !lower.startsWith("https://")) {
        clean = (if (tls) "https://" else "http://") + clean
    }
    if (tls && lower.startsWith("http://")) clean = "https://" + clean.substring(7)
    android.util.Log.d("FridaySettings", "normalizeUrl('$raw', tls=$tls) = '$clean'")
    return clean
}
