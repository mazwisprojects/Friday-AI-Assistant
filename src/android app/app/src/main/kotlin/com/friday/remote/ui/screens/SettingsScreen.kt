package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
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

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text(
            text = "Connection",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Text(
            text = "Server URL, token and TLS for your F.R.I.D.A.Y home server.",
            color = Color.LightGray,
            fontSize = 13.sp,
            modifier = Modifier.padding(bottom = 24.dp)
        )

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
            shape = RoundedCornerShape(12.dp)
        )
        TextField(
            value = token,
            onValueChange = { token = it },
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            label = { Text("Auth token") },
            colors = TextFieldDefaults.colors(
                unfocusedContainerColor = FridayGrey,
                focusedContainerColor = FridayGrey
            ),
            shape = RoundedCornerShape(12.dp)
        )

        Row(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
            Text("HTTPS (TLS)", color = Color.White, modifier = Modifier.padding(end = 8.dp))
            Switch(checked = tls, onCheckedChange = { tls = it })
        }

        Button(
            onClick = {
                securityManager.setServerUrl(normalizeUrl(url, tls))
                securityManager.setToken(token)
                securityManager.setTlsEnabled(tls)
                socketManager.disconnect()
                socketManager.connect()
            },
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
            colors = ButtonDefaults.buttonColors(containerColor = FridayAccent)
        ) {
            Text("Save & Reconnect")
        }

        Text(
            text = "Friday replies arrive on `transcription`; tool-approval dialogs appear automatically.",
            color = Color.LightGray,
            fontSize = 12.sp,
            modifier = Modifier.padding(top = 16.dp)
        )
    }
}

private fun normalizeUrl(raw: String, tls: Boolean): String {
    var clean = raw.trim()
    if (clean.isEmpty()) return if (tls) "https://192.168.1.100:8000" else "http://192.168.1.100:8000"
    val lower = clean.lowercase()
    if (!lower.startsWith("http://") && !lower.startsWith("https://")) {
        return (if (tls) "https://" else "http://") + clean
    }
    if (tls && lower.startsWith("http://")) return "https://" + clean.substring(7)
    return clean
}
