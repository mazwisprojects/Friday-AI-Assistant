package com.friday.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey

@Composable
fun DashboardScreen(socketManager: FridaySocketManager) {
    val metrics by socketManager.systemMetrics.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "System Monitor",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 24.dp)
        )

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item { MetricCard("CPU", pct(metrics?.cpuPercent), frac(metrics?.cpuPercent)) }
            item { MetricCard("RAM", pct(metrics?.ramPercent), frac(metrics?.ramPercent)) }
            item {
                val gpu = metrics?.gpuPercent
                MetricCard("GPU", if (gpu == null) "—" else pct(gpu), frac(gpu))
            }
            item {
                val used = metrics?.ramUsedGb
                val total = metrics?.ramTotalGb
                MetricCard(
                    "RAM Used",
                    if (used == null || total == null) "—" else "${fmt(used)} / ${fmt(total)} GB",
                    null
                )
            }
        }

        Text(
            text = "${metrics?.processCount ?: 0} processes · up ${metrics?.uptime ?: "—"}"
                + (if (metrics?.cpuTempC != null) " · ${metrics?.cpuTempC}°C" else ""),
            color = Color.LightGray,
            fontSize = 13.sp,
            modifier = Modifier.padding(top = 16.dp)
        )
    }
}

private fun pct(value: Double?): String = if (value == null) "—" else String.format("%.0f%%", value)

private fun fmt(value: Double?): String = if (value == null) "—" else String.format("%.1f", value)

private fun frac(value: Double?): Float? = value?.toFloat()?.div(100f)

@Composable
fun MetricCard(label: String, valueText: String, fraction: Float?) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Text(label, color = Color.LightGray, fontSize = 14.sp)

            Text(
                text = valueText,
                color = FridayAccent,
                fontSize = 30.sp
            )

            if (fraction != null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Color.DarkGray)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth(fraction.coerceIn(0f, 1f))
                            .fillMaxHeight()
                            .background(FridayAccent)
                    )
                }
            }
        }
    }
}
