package com.friday.remote.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.friday.remote.network.FridaySocketManager
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.atomic.AtomicBoolean

@Composable
fun PairingScreen(socketManager: FridaySocketManager) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val pairedDevice by socketManager.pairedDevice.collectAsState()
    val pairingError by socketManager.pairingError.collectAsState()
    val connectionState by socketManager.connectionState.collectAsState()
    var cameraGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var scanning by remember { mutableStateOf(false) }
    var scanMessage by remember { mutableStateOf("Scan the QR shown by Friday on the desktop.") }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        cameraGranted = granted
        scanning = granted
    }

    LaunchedEffect(Unit) {
        if (!cameraGranted) permissionLauncher.launch(Manifest.permission.CAMERA)
        else scanning = true
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Default.QrCodeScanner, contentDescription = null, tint = Color(0xFF67E8F9))
        Spacer(Modifier.height(12.dp))
        Text("Connect to Friday", style = MaterialTheme.typography.headlineMedium, color = Color.White)
        Spacer(Modifier.height(8.dp))
        Text(scanMessage, color = Color(0xFFB0B0B0))
        if (connectionState != FridaySocketManager.ConnectionState.CONNECTED) {
            Text("Friday link: ${connectionState.name.lowercase()}", color = Color(0xFFFCD34D))
        }
        Spacer(Modifier.height(16.dp))

        if (scanning && cameraGranted) {
            QrCamera(
                lifecycleOwner = lifecycleOwner,
                onPayload = { payload ->
                    scanning = false
                    scanMessage = "Pairing with Friday..."
                    socketManager.consumeQrPayload(payload)
                },
            )
        } else if (!cameraGranted) {
            Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                Text("Allow camera")
            }
        }

        pairingError.takeIf { it.isNotBlank() }?.let { error ->
            Spacer(Modifier.height(12.dp))
            Text(error, color = Color(0xFFFCA5A5))
            Button(onClick = { scanning = true; scanMessage = "Scan the QR shown by Friday on the desktop." }) {
                Text("Try again")
            }
        }

        pairedDevice?.let { device ->
            Spacer(Modifier.height(20.dp))
            Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF12313A))) {
                Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF86EFAC))
                    Spacer(Modifier.padding(horizontal = 6.dp))
                    Column {
                        Text("Connected to Friday", color = Color.White)
                        Text("${device.name} // ${device.status}", color = Color(0xFFBAE6FD))
                    }
                }
            }
        }
    }
}

@Composable
private fun QrCamera(
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    onPayload: (String) -> Unit,
) {
    val context = LocalContext.current
    val consumed = remember { AtomicBoolean(false) }
    val scanner = remember {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        )
    }
    var cameraProvider: ProcessCameraProvider? = null

    DisposableEffect(Unit) {
        onDispose {
            cameraProvider?.unbindAll()
            scanner.close()
        }
    }

    AndroidView(
        modifier = Modifier.fillMaxWidth().height(280.dp),
        factory = { viewContext ->
            val previewView = PreviewView(viewContext)
            val providerFuture = ProcessCameraProvider.getInstance(viewContext)
            providerFuture.addListener({
                val provider = providerFuture.get()
                cameraProvider = provider
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                analysis.setAnalyzer(ContextCompat.getMainExecutor(viewContext)) { imageProxy ->
                    val image = imageProxy.image
                    if (image == null) {
                        imageProxy.close()
                        return@setAnalyzer
                    }
                    scanner.process(InputImage.fromMediaImage(image, imageProxy.imageInfo.rotationDegrees))
                        .addOnSuccessListener { codes ->
                            val payload = codes.firstOrNull()?.rawValue
                            if (payload != null && consumed.compareAndSet(false, true)) {
                                runCatching { onPayload(payload) }
                            }
                        }
                        .addOnCompleteListener { imageProxy.close() }
                }
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }, ContextCompat.getMainExecutor(context))
            previewView
        },
    )
}