package com.friday.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey

@Composable
fun ChatScreen(socketManager: FridaySocketManager) {
    val messages by socketManager.messages.collectAsState()
    var textState by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            reverseLayout = false
        ) {
            items(messages) { message ->
                ChatBubble(message)
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextField(
                value = textState,
                onValueChange = { textState = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask Friday...") },
                colors = TextFieldDefaults.colors(
                    unfocusedContainerColor = FridayGrey,
                    focusedContainerColor = FridayGrey
                ),
                shape = RoundedCornerShape(24.dp)
            )
            IconButton(
                onClick = {
                    if (textState.isNotBlank()) {
                        socketManager.sendUserInput(textState)
                        textState = ""
                    }
                },
                modifier = Modifier.padding(start = 8.dp)
            ) {
                Icon(Icons.Default.Send, contentDescription = "Send", tint = FridayAccent)
            }
        }
    }
}

@Composable
fun ChatBubble(message: FridaySocketManager.FridayMessage) {
    val alignment = if (message.isFromUser) Alignment.End else Alignment.Start
    val color = if (message.isFromUser) FridayAccent else if (message.isSystem) Color.DarkGray else FridayGrey
    val textColor = if (message.isFromUser) Color.Black else Color.White
    val prefix = if (message.isSystem) "• " else ""

    Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = alignment) {
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(12.dp))
                .background(color)
                .padding(12.dp)
        ) {
            Text(text = prefix + message.text, color = textColor, fontSize = 16.sp)
        }
    }
}
