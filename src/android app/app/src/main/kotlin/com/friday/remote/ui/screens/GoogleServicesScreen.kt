package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey

@Composable
fun GoogleServicesScreen(socketManager: FridaySocketManager) {
    val googleServices by socketManager.googleServices.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Google Services",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        if (googleServices == null) {
            ConnectionCard(
                connected = false,
                onConnect = { socketManager.connectGoogleAccount() },
                onDisconnect = {}
            )
        } else {
            ConnectionCard(
                connected = googleServices!!.connected,
                onConnect = { socketManager.connectGoogleAccount() },
                onDisconnect = { socketManager.disconnectGoogleAccount() }
            )

            if (googleServices!!.connected) {
                Spacer(modifier = Modifier.height(16.dp))
                ServicesGrid(googleServices!!)
            }
        }
    }
}

@Composable
fun ConnectionCard(
    connected: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                if (connected) Icons.Default.CheckCircle else Icons.Default.Link,
                contentDescription = null,
                tint = if (connected) Color(0xFF4CAF50) else FridayAccent,
                modifier = Modifier.size(48.dp)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = if (connected) "Connected to Google" else "Connect Google Account",
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = if (connected) "Gmail, Calendar, Contacts, Drive" else "Access Gmail, Calendar, Contacts, and Drive",
                color = Color.LightGray,
                fontSize = 13.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            Button(
                onClick = if (connected) onDisconnect else onConnect,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (connected) Color(0xFFFF5252) else FridayAccent
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    if (connected) Icons.Default.LinkOff else Icons.Default.Link,
                    contentDescription = null,
                    modifier = Modifier.padding(end = 8.dp)
                )
                Text(if (connected) "Disconnect" else "Connect", color = Color.White)
            }
        }
    }
}

@Composable
fun ServicesGrid(services: FridaySocketManager.GoogleServices) {
    Text(
        text = "Available Services",
        color = Color.White,
        fontSize = 16.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(bottom = 12.dp)
    )

    val serviceItems = listOf(
        Triple("Gmail", Icons.Default.Email, services.gmailEnabled),
        Triple("Calendar", Icons.Default.CalendarToday, services.calendarEnabled),
        Triple("Contacts", Icons.Default.People, services.contactsEnabled),
        Triple("Drive", Icons.Default.Folder, services.driveEnabled)
    )

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(serviceItems) { (name, icon, enabled) ->
            ServiceCard(name, icon, enabled)
        }
    }
}

@Composable
fun ServiceCard(
    name: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    enabled: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (enabled) Color(0xFF2A4A2A) else FridayGrey
        ),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    icon,
                    contentDescription = null,
                    tint = if (enabled) Color(0xFF4CAF50) else Color.LightGray,
                    modifier = Modifier.padding(end = 12.dp)
                )
                Text(
                    text = name,
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            if (enabled) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = Color(0xFF4CAF50)
                )
            }
        }
    }
}