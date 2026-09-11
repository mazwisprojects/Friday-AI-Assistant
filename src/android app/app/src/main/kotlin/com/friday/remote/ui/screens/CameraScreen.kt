package com.friday.remote.ui.screens

import android.util.Base64
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageProxy
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Camera
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.FrontHand
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.LockOpen
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.friday.remote.network.FridaySocketManager
import com.friday.remote.ui.theme.FridayAccent
import com.friday.remote.ui.theme.FridayGrey
import org.json.JSONObject
import java.nio.ByteBuffer
import java.util.concurrent.Executor

@Composable
fun CameraScreen(socketManager: FridaySocketManager) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraProviderFuture = remember { androidx.camera.lifecycle.ProcessCameraProvider.getInstance(context) }
    val imageCapture = remember { ImageCapture.Builder().build() }
    
    var isBiometricAuthEnabled by remember { mutableStateOf(false) }
    var isHandTrackingEnabled by remember { mutableStateOf(false) }
    var isAuthenticated by remember { mutableStateOf(false) }
    var handTrackingStatus by remember { mutableStateOf("Hand tracking disabled") }
    var useFrontCamera by remember { mutableStateOf(false) }

    // Biometric Authentication
    val biometricManager = BiometricManager.from(context)
    val canAuthenticate = biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
    
    val biometricPrompt = remember {
        if (context is FragmentActivity) {
            val executor = ContextCompat.getMainExecutor(context)
            BiometricPrompt(context, executor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    isAuthenticated = true
                    socketManager.sendUserInput("User authenticated via biometrics")
                }
                
                override fun onAuthenticationFailed() {
                    isAuthenticated = false
                }
                
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    isAuthenticated = false
                }
            })
        } else null
    }

    val promptInfo = BiometricPrompt.PromptInfo.Builder()
        .setTitle("Biometric Authentication")
        .setSubtitle("Authenticate to access Friday")
        .setNegativeButtonText("Cancel")
        .build()

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { ctx ->
                val previewView = PreviewView(ctx)
                val executor = ContextCompat.getMainExecutor(ctx)
                cameraProviderFuture.addListener({
                    val cameraProvider = cameraProviderFuture.get()
                    val preview = androidx.camera.core.Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }

                    try {
                        cameraProvider.unbindAll()
                        val cameraSelector = if (useFrontCamera) {
                            CameraSelector.DEFAULT_FRONT_CAMERA
                        } else {
                            CameraSelector.DEFAULT_BACK_CAMERA
                        }
                        cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            cameraSelector,
                            preview,
                            imageCapture
                        )
                    } catch (e: Exception) {
                        e.printStackTrace()
                    }
                }, executor)
                previewView
            },
            modifier = Modifier.fillMaxSize()
        )

        // Top Controls
        Column(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color.Black.copy(alpha = 0.5f), RoundedCornerShape(12.dp))
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                // Biometric Auth Toggle
                if (canAuthenticate == BiometricManager.BIOMETRIC_SUCCESS) {
                    FilterChip(
                        selected = isBiometricAuthEnabled,
                        onClick = {
                            isBiometricAuthEnabled = !isBiometricAuthEnabled
                            if (isBiometricAuthEnabled && biometricPrompt != null) {
                                biometricPrompt.authenticate(promptInfo)
                            }
                        },
                        label = { 
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = if (isAuthenticated) Icons.Default.LockOpen else Icons.Default.Lock,
                                    contentDescription = "Biometric",
                                    modifier = Modifier.size(16.dp),
                                    tint = if (isAuthenticated) Color(0xFF4CAF50) else Color.White
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Biometric")
                            }
                        },
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Face,
                                contentDescription = "Face",
                                modifier = Modifier.size(16.dp)
                            )
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = FridayAccent,
                            selectedLabelColor = Color.Black
                        )
                    )
                }

                // Hand Tracking Toggle
                FilterChip(
                    selected = isHandTrackingEnabled,
                    onClick = {
                        isHandTrackingEnabled = !isHandTrackingEnabled
                        handTrackingStatus = if (isHandTrackingEnabled) {
                            "Hand tracking active - gesture recognition enabled"
                        } else {
                            "Hand tracking disabled"
                        }
                        socketManager.sendUserInput("Hand tracking ${if (isHandTrackingEnabled) "enabled" else "disabled"}")
                    },
                    label = { 
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.FrontHand,
                                contentDescription = "Hand",
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Hand Track")
                        }
                    },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = FridayAccent,
                        selectedLabelColor = Color.Black
                    )
                )
            }

            // Status Messages
            if (isBiometricAuthEnabled && !isAuthenticated) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF2A1A1A))
                ) {
                    Text(
                        text = "Authentication required for full access",
                        color = Color(0xFFFF9800),
                        fontSize = 12.sp,
                        modifier = Modifier.padding(8.dp)
                    )
                }
            }

            if (isHandTrackingEnabled) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    colors = CardDefaults.cardColors(containerColor = FridayGrey)
                ) {
                    Text(
                        text = handTrackingStatus,
                        color = FridayAccent,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(8.dp)
                    )
                }
            }
        }

        // Bottom Controls
        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(32.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Camera Switch
            Button(
                onClick = {
                    useFrontCamera = !useFrontCamera
                },
                colors = ButtonDefaults.buttonColors(containerColor = FridayGrey)
            ) {
                Icon(Icons.Default.Camera, contentDescription = "Switch Camera")
            }

            // Capture Button
            Button(
                onClick = {
                    if (!isBiometricAuthEnabled || isAuthenticated) {
                        captureAndUpload(imageCapture, socketManager, ContextCompat.getMainExecutor(context))
                    } else {
                        // Request authentication before capture
                        biometricPrompt?.authenticate(promptInfo)
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = FridayAccent),
                modifier = Modifier.size(80.dp)
            ) {
                Icon(Icons.Default.Camera, contentDescription = "Capture", tint = Color.Black)
            }
        }
    }
}

private fun captureAndUpload(
    imageCapture: ImageCapture,
    socketManager: FridaySocketManager,
    executor: java.util.concurrent.Executor
) {
    imageCapture.takePicture(executor, object : ImageCapture.OnImageCapturedCallback() {
        override fun onCaptureSuccess(image: ImageProxy) {
            val buffer = image.planes[0].buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            val base64Image = Base64.encodeToString(bytes, Base64.NO_WRAP)
            
            val data = JSONObject().apply {
                put("filename", "phone_capture_${System.currentTimeMillis()}.jpg")
                put("data", base64Image)
                put("mime_type", "image/jpeg")
                put("action", "Look at this photo and respond.")
            }
            socketManager.emit("upload_file_for_awareness", data)
            image.close()
        }
    })
}
