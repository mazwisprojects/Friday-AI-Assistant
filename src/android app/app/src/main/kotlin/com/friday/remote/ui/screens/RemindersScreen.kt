package com.friday.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
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
fun RemindersScreen(socketManager: FridaySocketManager) {
    val reminders by socketManager.reminders.collectAsState()
    var newText by remember { mutableStateOf("") }
    var showAddDialog by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Reminders",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        if (reminders.isEmpty()) {
            Text(
                text = "No reminders",
                color = Color.LightGray,
                fontSize = 14.sp,
                modifier = Modifier.padding(top = 24.dp)
            )
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(reminders, key = { it.id }) { reminder ->
                    ReminderCard(reminder, socketManager)
                }
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        FloatingActionButton(
            onClick = { showAddDialog = true },
            containerColor = FridayAccent,
            modifier = Modifier.align(Alignment.End)
        ) {
            Icon(
                imageVector = Icons.Default.Add,
                contentDescription = "Add reminder",
                tint = Color.Black
            )
        }
    }

    if (showAddDialog) {
        AddReminderDialog(
            text = newText,
            onTextChange = { newText = it },
            onDismiss = { showAddDialog = false },
            onAdd = { remindAt ->
                socketManager.addReminder(newText.trim(), remindAt)
                newText = ""
                showAddDialog = false
            }
        )
    }
}

@Composable
fun ReminderCard(reminder: FridaySocketManager.FridayReminder, socketManager: FridaySocketManager) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = reminder.text,
                color = Color.White,
                fontSize = 15.sp
            )
            Text(
                text = "At: " + reminder.at,
                color = Color.LightGray,
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
            TextButton(
                onClick = { socketManager.deleteReminder(reminder.id) },
                modifier = Modifier.align(Alignment.End)
            ) {
                Icon(
                    imageVector = Icons.Default.Delete,
                    contentDescription = "Delete",
                    tint = Color(0xFFFF5252)
                )
            }
        }
    }
}

@Composable
fun AddReminderDialog(
    text: String,
    onTextChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onAdd: (String) -> Unit
) {
    var remindAt by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New Reminder", color = Color.White) },
        text = {
            Column {
                OutlinedTextField(
                    value = text,
                    onValueChange = onTextChange,
                    label = { Text("What to remember") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedBorderColor = FridayGrey,
                        focusedBorderColor = FridayAccent
                    )
                )
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = remindAt,
                    onValueChange = { if (it.length <= 30) remindAt = it },
                    label = { Text("When (e.g. in 1 hour)") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedBorderColor = FridayGrey,
                        focusedBorderColor = FridayAccent
                    )
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (text.isNotBlank() && remindAt.isNotBlank()) {
                    onAdd(remindAt)
                }
            }) {
                Text("Add", color = FridayAccent)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = Color.LightGray)
            }
        }
    )
}
