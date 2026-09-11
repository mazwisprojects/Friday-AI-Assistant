package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Power
import androidx.compose.material.icons.filled.BrightnessHigh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
fun KasaScreen(socketManager: FridaySocketManager) {
    val kasaDevices by socketManager.kasaDevices.collectAsState()
    var isDiscovering by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Smart Home",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        // Discovery section
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = FridayGrey),
            shape = RoundedCornerShape(12.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Device Discovery",
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "${kasaDevices.size} devices found",
                        color = Color.LightGray,
                        fontSize = 13.sp
                    )
                }
                Button(
                    onClick = {
                        isDiscovering = true
                        socketManager.discoverKasaDevices()
                        // Simulate discovery completion
                        isDiscovering = false
                    },
                    enabled = !isDiscovering,
                    colors = ButtonDefaults.buttonColors(containerColor = FridayAccent)
                ) {
                    Icon(
                        Icons.Default.Search,
                        contentDescription = null,
                        tint = Color.Black,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text(if (isDiscovering) "Discovering..." else "Discover", color = Color.Black)
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Devices list
        if (kasaDevices.isEmpty()) {
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
                        Icons.Default.Lightbulb,
                        contentDescription = null,
                        tint = Color.LightGray,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "No devices found",
                        color = Color.LightGray,
                        fontSize = 14.sp
                    )
                    Text(
                        text = "Tap Discover to find Kasa devices",
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                }
            }
        } else {
            Text(
                text = "Devices",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(kasaDevices) { device ->
                    KasaDeviceCard(device, socketManager)
                }
            }
        }
    }
}

@Composable
fun KasaDeviceCard(
    device: FridaySocketManager.KasaDevice,
    socketManager: FridaySocketManager
) {
    var brightness by remember { mutableStateOf(device.brightness) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (device.isOn) Color(0xFF2A4A2A) else FridayGrey
        ),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Lightbulb,
                        contentDescription = null,
                        tint = if (device.isOn) Color(0xFF4CAF50) else Color.LightGray,
                        modifier = Modifier.padding(end = 12.dp)
                    )
                    Column {
                        Text(
                            text = device.name,
                            color = Color.White,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = device.type,
                            color = Color.LightGray,
                            fontSize = 12.sp
                        )
                    }
                }
                Switch(
                    checked = device.isOn,
                    onCheckedChange = { 
                        socketManager.controlKasaDevice(device.id, if (it) "on" else "off")
                    },
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = FridayAccent,
                        checkedTrackColor = FridayAccent.copy(alpha = 0.5f)
                    )
                )
            }

            if (device.isOn && device.type == "light") {
                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.BrightnessHigh,
                        contentDescription = null,
                        tint = FridayAccent,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text(
                        text = "Brightness: ${brightness}%",
                        color = Color.White,
                        fontSize = 14.sp
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Slider(
                        value = brightness.toFloat(),
                        onValueChange = { 
                            brightness = it.toInt()
                            socketManager.controlKasaDevice(device.id, "brightness", brightness)
                        },
                        valueRange = 0f..100f,
                        modifier = Modifier.weight(1f),
                        colors = SliderDefaults.colors(
                            activeTrackColor = FridayAccent,
                            thumbColor = FridayAccent
                        )
                    )
                }
            }
        }
    }
}