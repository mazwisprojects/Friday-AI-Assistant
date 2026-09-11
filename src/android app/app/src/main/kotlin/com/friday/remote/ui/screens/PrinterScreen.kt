package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Print
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Thermostat
import androidx.compose.material.icons.filled.Schedule
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
fun PrinterScreen(socketManager: FridaySocketManager) {
    val printers by socketManager.printers.collectAsState()
    var isDiscovering by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "3D Printers",
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
                        text = "Printer Discovery",
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "${printers.size} printers found",
                        color = Color.LightGray,
                        fontSize = 13.sp
                    )
                }
                Button(
                    onClick = {
                        isDiscovering = true
                        socketManager.discoverPrinters()
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

        // Printers list
        if (printers.isEmpty()) {
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
                        Icons.Default.Print,
                        contentDescription = null,
                        tint = Color.LightGray,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "No printers found",
                        color = Color.LightGray,
                        fontSize = 14.sp
                    )
                    Text(
                        text = "Tap Discover to find 3D printers",
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                }
            }
        } else {
            Text(
                text = "Printers",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(printers) { printer ->
                    PrinterCard(printer, socketManager)
                }
            }
        }
    }
}

@Composable
fun PrinterCard(
    printer: FridaySocketManager.Printer,
    socketManager: FridaySocketManager
) {
    val statusColor = when (printer.status) {
        "printing" -> Color(0xFF4CAF50)
        "idle" -> Color(0xFF2196F3)
        "error" -> Color(0xFFFF5252)
        else -> Color.LightGray
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
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
                        Icons.Default.Print,
                        contentDescription = null,
                        tint = statusColor,
                        modifier = Modifier.padding(end = 12.dp)
                    )
                    Column {
                        Text(
                            text = printer.name,
                            color = Color.White,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = printer.type,
                            color = Color.LightGray,
                            fontSize = 12.sp
                        )
                    }
                }
                Text(
                    text = printer.status.uppercase(),
                    color = statusColor,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            if (printer.status == "printing" && printer.currentJob != null) {
                Spacer(modifier = Modifier.height(12.dp))
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.DarkGray),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = printer.currentJob!!.name,
                            color = Color.White,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        
                        // Progress bar
                        LinearProgressIndicator(
                            progress = printer.currentJob!!.progress / 100f,
                            color = FridayAccent,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "${printer.currentJob!!.progress}% - ${printer.currentJob!!.timeRemaining}",
                            color = Color.LightGray,
                            fontSize = 12.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Temperature info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                TempInfo("Nozzle", printer.nozzleTemp, printer.targetNozzleTemp)
                TempInfo("Bed", printer.bedTemp, printer.targetBedTemp)
            }
        }
    }
}

@Composable
fun TempInfo(label: String, current: Int, target: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.Default.Thermostat,
            contentDescription = null,
            tint = FridayAccent,
            modifier = Modifier.size(16.dp)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Column {
            Text(
                text = label,
                color = Color.LightGray,
                fontSize = 10.sp
            )
            Text(
                text = "${current}°C",
                color = Color.White,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold
            )
            if (target > 0) {
                Text(
                    text = "→ ${target}°C",
                    color = FridayAccent,
                    fontSize = 10.sp
                )
            }
        }
    }
}