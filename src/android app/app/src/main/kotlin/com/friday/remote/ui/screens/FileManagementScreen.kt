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
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.VideoFile
import androidx.compose.material.icons.filled.AudioFile
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey
import java.io.InputStream

@Composable
fun FileManagementScreen(socketManager: FridaySocketManager) {
    val context = LocalContext.current
    var selectedFileUri by remember { mutableStateOf<Uri?>(null) }
    var uploadStatus by remember { mutableStateOf<String?>(null) }
    var uploadedFiles by remember { mutableStateOf<List<UploadedFile>>(emptyList()) }
    var showUploadDialog by remember { mutableStateOf(false) }

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        selectedFileUri = uri
        if (uri != null) {
            showUploadDialog = true
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "File Management",
            style = MaterialTheme.typography.titleLarge,
            color = Color.White,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        // Upload Section
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp),
            colors = CardDefaults.cardColors(containerColor = FridayGrey),
            shape = RoundedCornerShape(12.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Upload Files to Friday",
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                Text(
                    text = "Friday will process uploaded files for analysis, OCR, or other operations",
                    color = Color.LightGray,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(bottom = 16.dp)
                )
                Button(
                    onClick = { filePickerLauncher.launch("*/*") },
                    colors = ButtonDefaults.buttonColors(containerColor = FridayAccent),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(
                        imageVector = Icons.Default.CloudUpload,
                        contentDescription = "Upload",
                        tint = Color.Black,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text("Select File to Upload", color = Color.Black)
                }
            }
        }

        // Upload Status
        uploadStatus?.let { status ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (status.startsWith("Success")) Color(0xFF2A4A2A) else Color(0xFF4A2A2A)
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text(
                    text = status,
                    color = Color.White,
                    fontSize = 14.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }

        // Uploaded Files Section
        Text(
            text = "Recently Uploaded",
            color = Color.White,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 12.dp)
        )

        if (uploadedFiles.isEmpty()) {
            Text(
                text = "No files uploaded yet",
                color = Color.LightGray,
                fontSize = 14.sp,
                modifier = Modifier.padding(top = 24.dp)
            )
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(uploadedFiles) { file ->
                    UploadedFileCard(file, onDelete = {
                        uploadedFiles = uploadedFiles.filter { it.id != file.id }
                    })
                }
            }
        }
    }

    // Upload Confirmation Dialog
    if (showUploadDialog && selectedFileUri != null) {
        UploadFileDialog(
            fileUri = selectedFileUri!!,
            context = context,
            onDismiss = { showUploadDialog = false },
            onUpload = { fileName, fileData, mimeType ->
                socketManager.uploadFile(fileName, fileData, mimeType, "process")
                uploadedFiles = uploadedFiles + UploadedFile(
                    id = System.currentTimeMillis().toString(),
                    name = fileName,
                    mimeType = mimeType,
                    uploadedAt = System.currentTimeMillis()
                )
                uploadStatus = "Success: File '$fileName' uploaded to Friday for processing"
                selectedFileUri = null
                showUploadDialog = false
            },
            onError = { error ->
                uploadStatus = "Error: $error"
                selectedFileUri = null
                showUploadDialog = false
            }
        )
    }
}

@Composable
fun UploadFileDialog(
    fileUri: Uri,
    context: Context,
    onDismiss: () -> Unit,
    onUpload: (String, ByteArray, String) -> Unit,
    onError: (String) -> Unit
) {
    var fileName by remember { mutableStateOf("") }
    var isUploading by remember { mutableStateOf(false) }

    LaunchedEffect(fileUri) {
        fileName = getFileName(context, fileUri)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Upload File", color = Color.White) },
        text = {
            Column {
                Text(
                    text = "File: $fileName",
                    color = Color.White,
                    fontSize = 14.sp,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                Text(
                    text = "Friday will process this file for analysis, OCR, or other operations.",
                    color = Color.LightGray,
                    fontSize = 13.sp
                )
                if (isUploading) {
                    Spacer(modifier = Modifier.height(16.dp))
                    LinearProgressIndicator(
                        color = FridayAccent,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    isUploading = true
                    try {
                        val fileData = readFileBytes(context, fileUri)
                        val mimeType = context.contentResolver.getType(fileUri) ?: "application/octet-stream"
                        onUpload(fileName, fileData, mimeType)
                    } catch (e: Exception) {
                        onError(e.message ?: "Failed to read file")
                    }
                },
                enabled = !isUploading,
                colors = ButtonDefaults.buttonColors(containerColor = FridayAccent)
            ) {
                Text(if (isUploading) "Uploading..." else "Upload", color = Color.Black)
            }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                enabled = !isUploading
            ) {
                Text("Cancel", color = Color.LightGray)
            }
        }
    )
}

@Composable
fun UploadedFileCard(file: UploadedFile, onDelete: () -> Unit) {
    val icon = when {
        file.mimeType?.startsWith("image/") == true -> Icons.Default.Image
        file.mimeType?.startsWith("video/") == true -> Icons.Default.VideoFile
        file.mimeType?.startsWith("audio/") == true -> Icons.Default.AudioFile
        else -> Icons.Default.Description
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = FridayGrey),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = "File type",
                    tint = FridayAccent,
                    modifier = Modifier.padding(end = 12.dp)
                )
                Column {
                    Text(
                        text = file.name,
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = formatTimestamp(file.uploadedAt),
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                }
            }
            IconButton(onClick = onDelete) {
                Icon(
                    imageVector = Icons.Default.Delete,
                    contentDescription = "Delete",
                    tint = Color(0xFFFF5252)
                )
            }
        }
    }
}

data class UploadedFile(
    val id: String,
    val name: String,
    val mimeType: String?,
    val uploadedAt: Long
)



fun formatTimestamp(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    val seconds = diff / 1000
    val minutes = seconds / 60
    val hours = minutes / 60
    val days = hours / 24

    return when {
        days > 0 -> "${days}d ago"
        hours > 0 -> "${hours}h ago"
        minutes > 0 -> "${minutes}m ago"
        else -> "Just now"
    }
}