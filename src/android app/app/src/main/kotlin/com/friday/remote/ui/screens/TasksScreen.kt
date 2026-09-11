package com.friday.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue

import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
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
fun TasksScreen(socketManager: FridaySocketManager) {
    val tasks by socketManager.tasks.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Tasks",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        if (tasks.isEmpty()) {
            Text(
                text = "No open tasks",
                color = Color.LightGray,
                fontSize = 14.sp,
                modifier = Modifier.padding(top = 24.dp)
            )
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(tasks) { task ->
                    TaskCard(task, socketManager)
                }
            }
        }
    }
}

@Composable
fun TaskCard(task: FridaySocketManager.FridayTask, socketManager: FridaySocketManager) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = task.title,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp
            )
            Text(
                text = task.project,
                color = Color.LightGray,
                fontSize = 13.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                PriorityChip(task.priority)
                if (task.due.isNotEmpty()) {
                    Text(
                        text = "Due: ${task.due}",
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                }
                TaskActionMenu(task, socketManager)
            }
        }
    }
}

@Composable
fun PriorityChip(priority: String) {
    val color = when (priority.lowercase()) {
        "urgent" -> Color(0xFFFF5252)
        "high" -> Color(0xFFFF9800)
        "low" -> Color(0xFF4CAF50)
        else -> FridayAccent
    }
    Text(
        text = priority.uppercase(),
        color = color,
        fontSize = 11.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier
            .background(color.copy(alpha = 0.2f), RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    )
}

@Composable
fun TaskActionMenu(task: FridaySocketManager.FridayTask, socketManager: FridaySocketManager) {
    var menuExpanded by remember { mutableStateOf(false) }

    IconButton(onClick = { menuExpanded = true }) {
        Icon(
            imageVector = Icons.Default.Mic,
            contentDescription = "Task actions",
            tint = FridayAccent
        )
    }

    DropdownMenu(
        expanded = menuExpanded,
        onDismissRequest = { menuExpanded = false }
    ) {
        DropdownMenuItem(
            text = { Text("Complete") },
            onClick = {
                socketManager.performTaskAction(task.id, "complete")
                menuExpanded = false
            }
        )
        DropdownMenuItem(
            text = { Text("Cancel") },
            onClick = {
                socketManager.performTaskAction(task.id, "cancel")
                menuExpanded = false
            }
        )
    }
}
