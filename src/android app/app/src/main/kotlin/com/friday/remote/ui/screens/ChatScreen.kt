package com.friday.remote.ui.screens

import android.content.Context
import android.net.Uri
import com.friday.remote.utils.getFileName
import com.friday.remote.utils.readFileBytes
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey
import java.io.InputStream

@Composable
fun ChatScreen(socketManager: FridaySocketManager) {
    val messages by socketManager.messages.collectAsState()
    val actionPlan by socketManager.actionPlan.collectAsState()
    var textState by remember { mutableStateOf("") }
    var selectedFileUri by remember { mutableStateOf<Uri?>(null) }
    var attachedFileName by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            selectedFileUri = it
            attachedFileName = getFileName(context, it)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Action Plan Display
        actionPlan?.let { plan ->
            ActionPlanCard(plan, socketManager)
        }

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

        // Attachment Preview
        attachedFileName?.let { fileName ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                colors = CardDefaults.cardColors(containerColor = FridayGrey),
                shape = RoundedCornerShape(12.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.AttachFile,
                            contentDescription = "Attachment",
                            tint = FridayAccent,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text(
                            text = fileName,
                            color = Color.White,
                            fontSize = 13.sp,
                            maxLines = 1
                        )
                    }
                    IconButton(onClick = {
                        selectedFileUri = null
                        attachedFileName = null
                    }) {
                        Icon(Icons.Default.Close, contentDescription = "Remove", tint = Color.LightGray)
                    }
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { filePickerLauncher.launch("*/*") }) {
                Icon(Icons.Default.AttachFile, contentDescription = "Attach file", tint = FridayAccent)
            }
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
                    if (textState.isNotBlank() || selectedFileUri != null) {
                        if (selectedFileUri != null) {
                            // Upload file first
                            val fileData = readFileBytes(context, selectedFileUri!!)
                            val mimeType = context.contentResolver.getType(selectedFileUri!!) ?: "application/octet-stream"
                            socketManager.uploadFile(attachedFileName ?: "file", fileData, mimeType, "chat")
                            selectedFileUri = null
                            attachedFileName = null
                        }
                        if (textState.isNotBlank()) {
                            socketManager.sendUserInput(textState)
                            textState = ""
                        }
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
            Column {
                // Check for rich media content
                if (message.text.contains("[IMAGE:") || message.text.contains("[VIDEO:") || message.text.contains("[AUDIO:")) {
                    RichMediaContent(message.text, textColor)
                } else {
                    Text(text = prefix + message.text, color = textColor, fontSize = 16.sp)
                }
            }
        }
    }
}

@Composable
fun RichMediaContent(text: String, textColor: Color) {
    val parts = text.split(Regex("(\\[IMAGE:|\\[VIDEO:|\\[AUDIO:|\\])"))
    
    Column {
        parts.forEach { part ->
            when {
                part.endsWith(".jpg") || part.endsWith(".png") || part.endsWith(".jpeg") -> {
                    // Image placeholder
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .padding(vertical = 8.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.DarkGray)
                    ) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Default.Image, contentDescription = "Image", tint = Color.LightGray)
                                Text(part, color = Color.LightGray, fontSize = 12.sp)
                            }
                        }
                    }
                }
                part.endsWith(".mp4") || part.endsWith(".mov") -> {
                    // Video placeholder
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .padding(vertical = 8.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.DarkGray)
                    ) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Default.Image, contentDescription = "Video", tint = Color.LightGray)
                                Text("Video: $part", color = Color.LightGray, fontSize = 12.sp)
                            }
                        }
                    }
                }
                part.endsWith(".mp3") || part.endsWith(".wav") -> {
                    // Audio placeholder
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.DarkGray)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Image, contentDescription = "Audio", tint = Color.LightGray)
                            Text("Audio: $part", color = Color.LightGray, fontSize = 12.sp)
                        }
                    }
                }
                else -> {
                    if (part.isNotEmpty() && !part.startsWith("http")) {
                        Text(part, color = textColor, fontSize = 16.sp)
                    }
                }
            }
        }
    }
}

@Composable
fun ActionPlanCard(plan: FridaySocketManager.ActionPlan, socketManager: FridaySocketManager) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF2A2A3A)),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Action Plan",
                color = FridayAccent,
                fontSize = 16.sp,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            
            plan.steps.forEach { step ->
                val stepColor = when (step.status) {
                    "done" -> Color(0xFF4CAF50)
                    "error" -> Color(0xFFFF5252)
                    "cancelled" -> Color(0xFF9E9E9E)
                    "in_progress" -> Color(0xFFFF9800)
                    else -> Color.LightGray
                }
                
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = step.description,
                        color = Color.White,
                        fontSize = 14.sp,
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        text = step.status,
                        color = stepColor,
                        fontSize = 12.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                    )
                }
            }
        }
    }
}


