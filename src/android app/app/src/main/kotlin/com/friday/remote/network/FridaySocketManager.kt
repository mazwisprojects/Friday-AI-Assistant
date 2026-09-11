package com.friday.remote.network

import android.content.Context
import com.friday.remote.security.SecurityManager
import dagger.hilt.android.qualifiers.ApplicationContext
import io.socket.client.IO
import io.socket.client.Socket
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject

import java.net.URISyntaxException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Socket.IO client aligned with the real F.R.I.D.A.Y server contract (backend/server.py).
 *
 * RECONNECTION STRATEGY:
 * - Exponential backoff: starts at 1s, doubles each attempt, max 30s
 * - Infinite reconnection attempts (reconnectionAttempts = Int.MAX_VALUE)
 * - Dual transport: WebSocket primary, HTTP polling fallback for restrictive mobile networks
 * - On reconnect: re-requests all data (system monitor, tasks, autonomy, reminders, kasa, printers, Google, weather)
 * - Offline-first outbox: events sent while disconnected are queued and replayed on reconnect
 *
 * EMIT (app -> server):  user_input {text}, get_system_monitor {},
 *   approval_response {approval_id, approved}, start_audio {}, stop_audio {},
 *   upload_file_for_awareness {filename, data, mime_type, action},
 *   get_task_cards {}, task_action {task_id, action},
 *   get_autonomy_status {}, approve_autonomy_proposal {proposal_id},
 *   resolve_security_finding {finding_path, finding_value},
 *   get_reminders {}, add_reminder {text, remind_at}, delete_reminder {id},
 *   get_kasa_devices {}, get_printers {}, get_google_account_status {},
 *   get_weather {}, connect_google_account {}, disconnect_google_account {},
 *   discover_kasa {}, control_light {device_id, action, brightness}
 * RECEIVE (server -> app): status {msg}, transcription {sender, text},
 *   tool_confirmation_request {id, tool, args}, confirmation_expired {id, tool},
 *   approval_response_ack, dashboard_system_update / system_monitor_data,
 *   audio_data {data: [bytes]}, file_processing_result, file_download,
 *   task_cards [...], task_action_response {task_id, action, success},
 *   autonomy_status {phases, proposals, security_findings, ...},
 *   autonomy_approval_result {ok}, reminders_list [...],
 *   unified_notification {category, title, message},
 *   weather_data {location, temperature, ...}, kasa_devices [...],
 *   printer_list [...], google_account_status {connected, ...},
 *   system_alert {id, title, message, severity, timestamp},
 *   cad_data {id, name, ...}, cad_status {status, progress, ...}
 */
@Singleton
class FridaySocketManager @Inject constructor(
    private val securityManager: SecurityManager,
    @ApplicationContext private val context: Context
) {
    enum class ConnectionState { CONNECTED, DISCONNECTED, CONNECTING, ERROR }

    data class FridayMessage(
        val text: String,
        val isFromUser: Boolean,
        val isSystem: Boolean = false,
        val timestamp: Long = System.currentTimeMillis()
    ) {
        fun withAppended(extra: String): FridayMessage =
            FridayMessage(text + extra, isFromUser, isSystem, timestamp)
    }

    data class SystemMetrics(
        val cpuPercent: Double,
        val ramPercent: Double,
        val gpuPercent: Double?,
        val ramUsedGb: Double,
        val ramTotalGb: Double,
        val processCount: Int,
        val cpuTempC: Double?,
        val uptime: String
    )

    data class ApprovalRequest(val id: String, val title: String, val message: String)

    data class FridayTask(
        val id: String,
        val title: String,
        val due: String,
        val priority: String,
        val project: String,
        val status: String
    )

    data class AutonomyStatus(
        val phases: Map<String, String>,
        val proposals: List<AutonomyProposal>,
        val securityFindings: List<SecurityFinding>,
        val error: String
    )

    data class AutonomyProposal(
        val id: String,
        val name: String,
        val kind: String,
        val reason: String,
        val priority: String,
        val status: String
    )

    data class SecurityFinding(
        val path: String,
        val value: String
    )

    data class FridayReminder(
        val id: String,
        val text: String,
        val at: String
    )

    data class ActionPlan(
        val id: String,
        val steps: List<ActionStep>
    )

    data class ActionStep(
        val description: String,
        val status: String
    )

    data class FridaySettings(
        val faceAuthEnabled: Boolean = false,
        val systemAlertsEnabled: Boolean = true,
        val quietMode: Boolean = false,
        val urgentOnly: Boolean = false,
        val emergenciesOnly: Boolean = false,
        val currentMode: String = "active",
        val voiceVisionProvider: String = "Gemini Live",
        val textReasoningProvider: String = "Gemini",
        val codingProvider: String = "OpenClaw",
        val toolPermissions: Map<String, Boolean> = emptyMap()
    )

    data class WeatherData(
        val location: String,
        val temperature: Int,
        val feelsLike: Int,
        val condition: String,
        val humidity: Int,
        val windSpeed: Int,
        val cloudiness: Int,
        val high: Int,
        val low: Int,
        val unit: String = "C"
    )

    data class GoogleServices(
        val connected: Boolean,
        val gmailEnabled: Boolean,
        val calendarEnabled: Boolean,
        val contactsEnabled: Boolean,
        val driveEnabled: Boolean
    )

    data class KasaDevice(
        val id: String,
        val name: String,
        val type: String,
        val isOn: Boolean,
        val brightness: Int
    )

    data class Printer(
        val id: String,
        val name: String,
        val type: String,
        val status: String,
        val nozzleTemp: Int,
        val targetNozzleTemp: Int,
        val bedTemp: Int,
        val targetBedTemp: Int,
        val currentJob: PrintJob?
    )

    data class PrintJob(
        val name: String,
        val progress: Int,
        val timeRemaining: String
    )

    data class SystemAlert(
        val id: String,
        val title: String,
        val message: String,
        val severity: String,
        val timestamp: Long
    )

    data class CADData(
        val id: String,
        val name: String,
        val description: String,
        val format: String,
        val vertices: Int,
        val faces: Int
    )

    data class CADStatus(
        val status: String,
        val progress: Int,
        val currentStep: String
    )

    interface AudioSink { fun onAudioData(bytes: List<Int>) }


    private data class QueuedEvent(val event: String, val data: JSONObject)

    private var socket: Socket? = null
    private var monitorJob: Job? = null
    private var audioSink: AudioSink? = null
    private val _outbox = ArrayList<QueuedEvent>()

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState

    private val _messages = MutableStateFlow<List<FridayMessage>>(emptyList())
    val messages: StateFlow<List<FridayMessage>> = _messages

    private val _systemMetrics = MutableStateFlow<SystemMetrics?>(null)
    val systemMetrics: StateFlow<SystemMetrics?> = _systemMetrics

    private val _pendingApproval = MutableStateFlow<ApprovalRequest?>(null)
    val pendingApproval: StateFlow<ApprovalRequest?> = _pendingApproval

    private val _sessionActive = MutableStateFlow(false)
    val sessionActive: StateFlow<Boolean> = _sessionActive

    private val _tasks = MutableStateFlow<List<FridayTask>>(emptyList())
    val tasks: StateFlow<List<FridayTask>> = _tasks

    private val _autonomyStatus = MutableStateFlow<AutonomyStatus?>(null)
    val autonomyStatus: StateFlow<AutonomyStatus?> = _autonomyStatus

    private val _reminders = MutableStateFlow<List<FridayReminder>>(emptyList())
    val reminders: StateFlow<List<FridayReminder>> = _reminders

    private val _actionPlan = MutableStateFlow<ActionPlan?>(null)
    val actionPlan: StateFlow<ActionPlan?> = _actionPlan

    private val _settings = MutableStateFlow<FridaySettings?>(null)
    val settings: StateFlow<FridaySettings?> = _settings

    private val _weatherData = MutableStateFlow<WeatherData?>(null)
    val weatherData: StateFlow<WeatherData?> = _weatherData

    private val _googleServices = MutableStateFlow<GoogleServices?>(null)
    val googleServices: StateFlow<GoogleServices?> = _googleServices

    private val _kasaDevices = MutableStateFlow<List<KasaDevice>>(emptyList())
    val kasaDevices: StateFlow<List<KasaDevice>> = _kasaDevices

    private val _printers = MutableStateFlow<List<Printer>>(emptyList())
    val printers: StateFlow<List<Printer>> = _printers

    private val _systemAlerts = MutableStateFlow<List<SystemAlert>>(emptyList())
    val systemAlerts: StateFlow<List<SystemAlert>> = _systemAlerts

    private val _cadData = MutableStateFlow<CADData?>(null)
    val cadData: StateFlow<CADData?> = _cadData

    private val _cadStatus = MutableStateFlow<CADStatus?>(null)
    val cadStatus: StateFlow<CADStatus?> = _cadStatus

    fun connect() {
        android.util.Log.i("FridaySocket", "=== CONNECT() CALLED ===")
        
        if (socket?.connected() == true) {
            android.util.Log.w("FridaySocket", "Already connected, skipping")
            return
        }
        
        _connectionState.value = ConnectionState.CONNECTING
        
        try {
            val serverUrl = securityManager.getServerUrl()
            android.util.Log.i("FridaySocket", "========================================")
            android.util.Log.i("FridaySocket", "SERVER URL: $serverUrl")
            android.util.Log.i("FridaySocket", "TLS: ${securityManager.isTlsEnabled()}")
            android.util.Log.i("FridaySocket", "TOKEN: ${if (securityManager.getToken().isNotEmpty()) "[SET]" else "[EMPTY]"}")
            android.util.Log.i("FridaySocket", "========================================")
            
            val opts = IO.Options().apply {
                forceNew = true
                reconnection = true
                reconnectionDelay = 1000
                reconnectionDelayMax = 30000
                reconnectionAttempts = Int.MAX_VALUE
                timeout = 20000
                transports = arrayOf("websocket", "polling")
            }
            
            android.util.Log.d("FridaySocket", "Creating IO.socket...")
            socket = IO.socket(serverUrl, opts)
            android.util.Log.d("FridaySocket", "Socket created: ${socket != null}")

            socket?.on(Socket.EVENT_CONNECT) {
                android.util.Log.i("FridaySocket", "🎉 EVENT_CONNECT - Connected!")
                _connectionState.value = ConnectionState.CONNECTED
                flushOutbox()
                requestSystemMonitor()
                requestTaskCards()
                requestAutonomyStatus()
                requestReminders()
                requestKasaDevices()
                requestPrinters()
                requestGoogleAccountStatus()
                startMonitor()
            }
            
            socket?.on(Socket.EVENT_DISCONNECT) { args ->
                android.util.Log.w("FridaySocket", "⚠️ EVENT_DISCONNECT: ${args?.contentToString()}")
                _connectionState.value = ConnectionState.DISCONNECTED
                monitorJob?.cancel()
            }
            
            socket?.on(Socket.EVENT_CONNECT_ERROR) { args ->
                android.util.Log.e("FridaySocket", "❌ EVENT_CONNECT_ERROR")
                android.util.Log.e("FridaySocket", "Args: ${args?.contentToString()}")
                android.util.Log.e("FridaySocket", "Error type: ${args?.firstOrNull()?.javaClass?.simpleName}")
                if (args?.firstOrNull() is Exception) {
                    val ex = args?.firstOrNull() as Exception
                    android.util.Log.e("FridaySocket", "Message: ${ex.message}")
                    android.util.Log.e("FridaySocket", "Cause: ${ex.cause?.message}")
                }
                _connectionState.value = ConnectionState.ERROR
            }
            
            socket?.on("reconnect_attempt") { args ->
                android.util.Log.d("FridaySocket", "🔄 Reconnect attempt #${args?.firstOrNull()}")
                _connectionState.value = ConnectionState.CONNECTING
            }
            
            socket?.on("reconnect") { args ->
                android.util.Log.i("FridaySocket", "🎉 RECONNECT after ${args?.firstOrNull()} attempts")
                _connectionState.value = ConnectionState.CONNECTED
                flushOutbox()
                requestSystemMonitor()
                requestTaskCards()
                requestAutonomyStatus()
                requestReminders()
                requestKasaDevices()
                requestPrinters()
                requestGoogleAccountStatus()
                startMonitor()
            }
            
            socket?.on("reconnect_error") { args ->
                android.util.Log.e("FridaySocket", "❌ Reconnect error: ${args?.contentToString()}")
            }
            
            socket?.on("reconnect_failed") {
                android.util.Log.e("FridaySocket", "❌ RECONNECT FAILED")
            }

            // --- F.R.I.D.A.Y server contract ---
            socket?.on("status") { args -> onStatus(args) }
            socket?.on("transcription") { args -> onTranscription(args) }
            socket?.on("tool_confirmation_request") { args -> onToolConfirmation(args) }
            socket?.on("confirmation_expired") { args -> onConfirmationExpired(args) }
            socket?.on("approval_response_ack") { args -> onApprovalAck(args) }
            socket?.on("dashboard_system_update") { args -> onSystemMetrics(args) }
            socket?.on("system_monitor_data") { args -> onSystemMetrics(args) }
            socket?.on("audio_data") { args -> onAudioData(args) }
            socket?.on("file_processing_result") { args -> onFileProcessingResult(args) }
            socket?.on("file_download") { args -> onFileDownload(args) }
            socket?.on("task_cards") { args -> onTaskCards(args) }
            socket?.on("task_action_response") { args -> onTaskActionResponse(args) }
            socket?.on("autonomy_status") { args -> onAutonomyStatus(args) }
            socket?.on("autonomy_approval_result") { args -> onAutonomyApprovalResult(args) }
            socket?.on("reminders_list") { args -> onRemindersList(args) }
            socket?.on("unified_notification") { args -> onUnifiedNotification(args) }
            socket?.on("action_plan") { args -> onActionPlan(args) }
            socket?.on("settings") { args -> onSettings(args) }
            socket?.on("weather_data") { args -> onWeatherData(args) }
            socket?.on("google_account_status") { args -> onGoogleAccountStatus(args) }
            socket?.on("kasa_devices") { args -> onKasaDevices(args) }
            socket?.on("printer_list") { args -> onPrinters(args) }
            socket?.on("system_alert") { args -> onSystemAlert(args) }
            socket?.on("cad_data") { args -> onCADData(args) }
            socket?.on("cad_status") { args -> onCADStatus(args) }

            socket?.connect()
            android.util.Log.i("FridaySocket", "🚀 socket.connect() called (async)")
            
        } catch (e: URISyntaxException) {
            android.util.Log.e("FridaySocket", "❌ URISyntaxException - Invalid URL!")
            android.util.Log.e("FridaySocket", "URL: ${securityManager.getServerUrl()}")
            android.util.Log.e("FridaySocket", "Message: ${e.message}")
            e.printStackTrace()
            _connectionState.value = ConnectionState.ERROR
        } catch (e: IllegalArgumentException) {
            android.util.Log.e("FridaySocket", "❌ IllegalArgumentException!")
            android.util.Log.e("FridaySocket", "Message: ${e.message}")
            e.printStackTrace()
            _connectionState.value = ConnectionState.ERROR
        } catch (e: Exception) {
            android.util.Log.e("FridaySocket", "❌ EXCEPTION in connect()!")
            android.util.Log.e("FridaySocket", "Type: ${e.javaClass.simpleName}")
            android.util.Log.e("FridaySocket", "Message: ${e.message}")
            android.util.Log.e("FridaySocket", "Cause: ${e.cause?.message}")
            e.printStackTrace()
            _connectionState.value = ConnectionState.ERROR
        }
        android.util.Log.i("FridaySocket", "=== connect() finished ===")
    }

    fun disconnect() {
        monitorJob?.cancel()
        socket?.disconnect()
        _connectionState.value = ConnectionState.DISCONNECTED
    }

    /**
     * Disconnect and reconnect — used when server URL changes in Settings.
     * This creates a fresh Socket.IO connection to the new server.
     */
    fun reconnect() {
        disconnect()
        // Small delay to allow socket cleanup before reconnecting
        CoroutineScope(Dispatchers.IO).launch {
            delay(500)
            connect()
        }
    }

    /**
     * Request fresh data from server after reconnection.
     * Call this when the app comes back to foreground to ensure all data is current.
     */
    fun refreshAll() {
        if (_connectionState.value != ConnectionState.CONNECTED) return
        requestSystemMonitor()
        requestTaskCards()
        requestAutonomyStatus()
        requestReminders()
        requestKasaDevices()
        requestPrinters()
        requestGoogleAccountStatus()
        requestWeather()
    }

    /** Offline-first: queue while disconnected, replay on reconnect. */
    fun emit(event: String, data: JSONObject) {
        if (socket?.connected() == true) {
            rawEmit(event, data)
        } else {
            synchronized(_outbox) { _outbox.add(QueuedEvent(event, data)) }
        }
    }

    fun sendUserInput(text: String) {
        addMessage(text, true, false)
        emit("user_input", JSONObject().put("text", text))
    }

    fun respondToApproval(id: String, approved: Boolean) {
        emit("approval_response", JSONObject().apply {
            put("approval_id", id)
            put("approved", approved)
        })
        _pendingApproval.value = null
    }

    // Tier 1: task, autonomy, reminder emit methods
    fun requestTaskCards() {
        emit("get_task_cards", JSONObject())
    }

    fun performTaskAction(taskId: String, action: String) {
        emit("task_action", JSONObject().apply {
            put("task_id", taskId)
            put("action", action)
        })
    }

    fun requestAutonomyStatus() {
        emit("get_autonomy_status", JSONObject())
    }

    fun approveAutonomyProposal(proposalId: String) {
        emit("approve_autonomy_proposal", JSONObject().apply {
            put("proposal_id", proposalId)
        })
    }

    fun resolveSecurityFinding(findingPath: String, findingValue: String) {
        emit("resolve_security_finding", JSONObject().apply {
            put("finding_path", findingPath)
            put("finding_value", findingValue)
        })
    }

    fun requestReminders() {
        emit("get_reminders", JSONObject())
    }

    fun addReminder(text: String, remindAt: String) {
        emit("add_reminder", JSONObject().apply {
            put("text", text)
            put("remind_at", remindAt)
        })
    }

    fun deleteReminder(id: String) {
        emit("delete_reminder", JSONObject().apply {
            put("id", id)
        })
    }

    fun uploadFile(fileName: String, fileData: ByteArray, mimeType: String, action: String = "process") {
        val base64Data = android.util.Base64.encodeToString(fileData, android.util.Base64.NO_WRAP)
        emit("upload_file_for_awareness", JSONObject().apply {
            put("filename", fileName)
            put("data", base64Data)
            put("mime_type", mimeType)
            put("action", action)
        })
    }

    fun toggleAudioSession() {
        if (_sessionActive.value) stopAudioSession() else startAudioSession()
    }

    fun startAudioSession() {
        emit("start_audio", JSONObject())
        _sessionActive.value = true
        addMessage("Friday is listening (home server mic).", false, true)
    }

    fun stopAudioSession() {
        emit("stop_audio", JSONObject())
        _sessionActive.value = false
        addMessage("Friday session stopped.", false, true)
    }

    fun setAudioSink(sink: AudioSink) { audioSink = sink }

    fun requestSettings() {
        emit("get_settings", JSONObject())
    }

    fun updateSettings(settings: Map<String, Any>) {
        emit("update_settings", JSONObject(settings))
    }

    // Weather and Google Services
    fun requestWeather() {
        emit("get_weather", JSONObject())
    }

    fun requestKasaDevices() {
        emit("get_kasa_devices", JSONObject())
    }

    fun requestPrinters() {
        emit("get_printers", JSONObject())
    }

    fun requestGoogleAccountStatus() {
        emit("get_google_account_status", JSONObject())
    }

    fun connectGoogleAccount() {
        emit("connect_google_account", JSONObject())
    }

    fun disconnectGoogleAccount() {
        emit("disconnect_google_account", JSONObject())
    }

    // Kasa and Printers
    fun discoverKasaDevices() {
        emit("discover_kasa", JSONObject())
    }

    fun controlKasaDevice(deviceId: String, action: String, value: Int = 0) {
        emit("control_light", JSONObject().apply {
            put("device_id", deviceId)
            put("action", action)
            if (value > 0) put("brightness", value)
        })
    }

    fun discoverPrinters() {
        emit("discover_printers", JSONObject())
    }

    // Alerts
    fun clearAlerts() {
        _systemAlerts.value = emptyList()
    }

    // CAD operations
    fun downloadCAD(cadId: String) {
        emit("download_cad", JSONObject().apply {
            put("cad_id", cadId)
        })
    }

    fun iterateCAD(cadId: String) {
        emit("iterate_cad", JSONObject().apply {
            put("cad_id", cadId)
        })
    }

    // ----- server -> app event handlers -----

    private fun onStatus(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val msg = data.optString("msg", data.optString("text", "System"))
        if (msg.isNotEmpty()) addMessage(msg, false, true)
    }

    private fun onTranscription(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val text = data.optString("text", "")
        if (text.isEmpty()) return
        val sender = data.optString("sender", "FRIDAY")
        if (sender == "User") return // user lines are echoed locally on send
        val current = _messages.value
        if (current.isNotEmpty()) {
            val last = current.last()
            if (!last.isFromUser && !last.isSystem) {
                val list = current.toMutableList()
                list[list.size - 1] = last.withAppended(text)
                _messages.value = list
                return
            }
        }
        addMessage(text, false, false)
    }

    private fun onToolConfirmation(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val id = data.optString("id", "")
        if (id.isEmpty()) return
        val tool = data.optString("tool", "tool")
        var extra = ""
        try {
            val argObj = data.opt("args") as? JSONObject
            if (argObj != null) extra = "\n\n" + argObj.toString()
        } catch (e: Exception) { }
        _pendingApproval.value = ApprovalRequest(
            id = id,
            title = "Friday needs your approval",
            message = "Run tool \"$tool\"?$extra"
        )
    }

    private fun onConfirmationExpired(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val id = data.optString("id", "")
        if (_pendingApproval.value?.id == id) _pendingApproval.value = null
        val tool = data.optString("tool", "tool")
        addMessage("Confirmation expired for \"$tool\". The action was not executed.", false, true)
    }

    private fun onApprovalAck(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        addMessage(if (data.optBoolean("approved", false)) "Approved." else "Denied.", false, true)
    }

    private fun onSystemMetrics(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        _systemMetrics.value = SystemMetrics(
            cpuPercent = data.optDouble("cpu_percent", 0.0),
            ramPercent = data.optDouble("ram_percent", 0.0),
            gpuPercent = if (data.has("gpu_percent") && !data.isNull("gpu_percent")) data.getDouble("gpu_percent") else null,
            ramUsedGb = data.optDouble("ram_used_gb", 0.0),
            ramTotalGb = data.optDouble("ram_total_gb", 0.0),
            processCount = data.optInt("process_count", 0),
            cpuTempC = if (data.has("cpu_temp_c") && !data.isNull("cpu_temp_c")) data.getDouble("cpu_temp_c") else null,
            uptime = data.optString("uptime", "—")
        )
    }

    private fun onAudioData(args: Array<Any?>) {
        if (args.isEmpty()) return
        try {
            val arr = (args[0] as JSONObject).getJSONArray("data")
            val bytes = ArrayList<Int>(arr.length())
            for (i in 0 until arr.length()) bytes.add(arr.optInt(i, 0))
            audioSink?.onAudioData(bytes)
        } catch (e: Exception) { /* ignore malformed frame */ }
    }

    private fun onFileProcessingResult(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val error = data.optString("error", "")
        val ok = data.optBoolean("ok", error.isEmpty())
        addMessage(if (ok) "File received by Friday." else "File upload failed: $error", false, true)
    }

    private fun onFileDownload(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val name = data.optString("name", data.optString("filename", "file"))
        val payload = data.optString("data", data.optString("payload", ""))
        val mime = data.optString("mime_type", "application/octet-stream")
        if (payload.isNotEmpty()) {
            try {
                val bytes = android.util.Base64.decode(payload, android.util.Base64.DEFAULT)
                val file = java.io.File(context.filesDir, name)
                file.writeBytes(bytes)
                addMessage("Saved file from Friday: ${file.name} (${mime})", false, true)
            } catch (e: Exception) {
                addMessage("File received but failed to save: ${e.message}", false, true)
            }
        } else {
            addMessage("File received from Friday: $name", false, true)
        }
    }

    // ----- Tier 1 handler methods -----

    private fun onTaskCards(args: Array<Any?>) {
        if (args.isEmpty()) return
        try {
            // Server emits task_cards directly as a JSONArray
            val arr = args[0] as JSONArray
            val list = ArrayList<FridayTask>(arr.length())
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                list.add(FridayTask(
                    id = obj.optString("id", ""),
                    title = obj.optString("title", ""),
                    due = obj.optString("due", ""),
                    priority = obj.optString("priority", "normal"),
                    project = obj.optString("project", ""),
                    status = obj.optString("status", "open")
                ))
            }
            _tasks.value = list
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onTaskActionResponse(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val taskId = data.optString("task_id", "")
        val action = data.optString("action", "")
        val success = data.optBoolean("success", false)
        val msg = if (success) "Task \"$taskId\" $action successful." else "Task \"$taskId\" $action failed."
        addMessage(msg, false, true)
        requestTaskCards()
    }

    private fun onAutonomyStatus(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            val phases = mutableMapOf<String, String>()
            val phasesObj = data.optJSONObject("phases")
            if (phasesObj != null) {
                val keys = phasesObj.keys()
                while (keys.hasNext()) {
                    val key = keys.next() as String
                    phases[key] = phasesObj.getString(key)
                }
            }
            val proposals = parseProposals(data.optJSONArray("proposals"))
            val securityFindings = parseSecurityFindings(data.optJSONArray("security_findings"))
            val error = data.optString("error", "")
            _autonomyStatus.value = AutonomyStatus(
                phases = phases,
                proposals = proposals,
                securityFindings = securityFindings,
                error = error
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun parseProposals(arr: JSONArray?): List<AutonomyProposal> {

        if (arr == null) return emptyList()
        val list = ArrayList<AutonomyProposal>()
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            list.add(AutonomyProposal(
                id = obj.optString("id", ""),
                name = obj.optString("name", ""),
                kind = obj.optString("kind", ""),
                reason = obj.optString("reason", ""),
                priority = obj.optString("priority", "normal"),
                status = obj.optString("status", "pending_review")
            ))
        }
        return list
    }

    private fun parseSecurityFindings(arr: JSONArray?): List<SecurityFinding> {

        if (arr == null) return emptyList()
        val list = ArrayList<SecurityFinding>()
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            list.add(SecurityFinding(
                path = obj.optString("path", ""),
                value = obj.optString("value", "")
            ))
        }
        return list
    }

    private fun onAutonomyApprovalResult(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val ok = data.optBoolean("ok", !data.has("error"))
        val msg = if (ok) "Approval applied." else "Approval failed: ${data.optString("error", "unknown")}"
        addMessage(msg, false, true)
        requestAutonomyStatus()
    }

    private fun onRemindersList(args: Array<Any?>) {
        if (args.isEmpty()) return
        try {
            // Server emits reminders_list directly as a JSONArray
            val arr = args[0] as JSONArray
            val list = ArrayList<FridayReminder>(arr.length())
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                list.add(FridayReminder(
                    id = obj.optString("id", ""),
                    text = obj.optString("text", ""),
                    at = obj.optString("at", obj.optString("remind_at", ""))
                ))
            }
            _reminders.value = list
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onUnifiedNotification(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        val category = data.optString("category", "general")
        val title = data.optString("title", "")
        val message = data.optString("message", "")
        if (title.isNotEmpty() || message.isNotEmpty()) {
            addMessage("[${category}] ${if (title.isNotEmpty()) title else message}", false, true)
        }
    }

    private fun onActionPlan(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            val stepsArray = data.optJSONArray("steps")
            val steps = ArrayList<ActionStep>()
            if (stepsArray != null) {
                for (i in 0 until stepsArray.length()) {
                    val stepObj = stepsArray.getJSONObject(i)
                    steps.add(ActionStep(
                        description = stepObj.optString("description", ""),
                        status = stepObj.optString("status", "pending")
                    ))
                }
            }
            _actionPlan.value = ActionPlan(
                id = data.optString("id", ""),
                steps = steps
            )
            
            // Auto-hide if all steps are done/error/cancelled
            if (steps.all { it.status in listOf("done", "error", "cancelled") }) {
                kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
                    kotlinx.coroutines.delay(4000)
                    _actionPlan.value = null
                }
            }
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onSettings(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            val toolPermissions = mutableMapOf<String, Boolean>()
            val permissionsObj = data.optJSONObject("tool_permissions")
            if (permissionsObj != null) {
                val keys = permissionsObj.keys()
                while (keys.hasNext()) {
                    val key = keys.next() as String
                    toolPermissions[key] = permissionsObj.getBoolean(key)
                }
            }
            
            val interruptPrefs = data.optJSONObject("interrupt_preferences")
            
            _settings.value = FridaySettings(
                faceAuthEnabled = data.optBoolean("face_auth_enabled", false),
                systemAlertsEnabled = data.optBoolean("system_alerts_enabled", true),
                quietMode = data.optBoolean("quiet_mode", false),
                urgentOnly = interruptPrefs?.optBoolean("urgent_only", false) ?: false,
                emergenciesOnly = interruptPrefs?.optBoolean("emergencies_only", false) ?: false,
                currentMode = data.optString("current_mode", "active"),
                voiceVisionProvider = data.optString("voice_vision_provider", "Gemini Live"),
                textReasoningProvider = data.optString("text_reasoning_provider", "Gemini"),
                codingProvider = data.optString("coding_provider", "OpenClaw"),
                toolPermissions = toolPermissions
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onWeatherData(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            _weatherData.value = WeatherData(
                location = data.optString("location", "Unknown"),
                temperature = data.optInt("temperature", 0),
                feelsLike = data.optInt("feels_like", 0),
                condition = data.optString("condition", "Unknown"),
                humidity = data.optInt("humidity", 0),
                windSpeed = data.optInt("wind_speed", 0),
                cloudiness = data.optInt("cloudiness", 0),
                high = data.optInt("high", 0),
                low = data.optInt("low", 0),
                unit = data.optString("unit", "C")
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onGoogleAccountStatus(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            _googleServices.value = GoogleServices(
                connected = data.optBoolean("connected", false),
                gmailEnabled = data.optBoolean("gmail_enabled", false),
                calendarEnabled = data.optBoolean("calendar_enabled", false),
                contactsEnabled = data.optBoolean("contacts_enabled", false),
                driveEnabled = data.optBoolean("drive_enabled", false)
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onKasaDevices(args: Array<Any?>) {
        if (args.isEmpty()) return
        try {
            val arr = args[0] as JSONArray
            val list = ArrayList<KasaDevice>()
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                list.add(KasaDevice(
                    id = obj.optString("id", ""),
                    name = obj.optString("name", "Unknown"),
                    type = obj.optString("type", "device"),
                    isOn = obj.optBoolean("is_on", false),
                    brightness = obj.optInt("brightness", 100)
                ))
            }
            _kasaDevices.value = list
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onPrinters(args: Array<Any?>) {
        if (args.isEmpty()) return
        try {
            val arr = args[0] as JSONArray
            val list = ArrayList<Printer>()
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val jobObj = obj.optJSONObject("current_job")
                val job = if (jobObj != null) {
                    PrintJob(
                        name = jobObj.optString("name", ""),
                        progress = jobObj.optInt("progress", 0),
                        timeRemaining = jobObj.optString("time_remaining", "")
                    )
                } else null
                
                list.add(Printer(
                    id = obj.optString("id", ""),
                    name = obj.optString("name", "Unknown"),
                    type = obj.optString("type", "printer"),
                    status = obj.optString("status", "idle"),
                    nozzleTemp = obj.optInt("nozzle_temp", 0),
                    targetNozzleTemp = obj.optInt("target_nozzle_temp", 0),
                    bedTemp = obj.optInt("bed_temp", 0),
                    targetBedTemp = obj.optInt("target_bed_temp", 0),
                    currentJob = job
                ))
            }
            _printers.value = list
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onSystemAlert(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            val alert = SystemAlert(
                id = data.optString("id", System.currentTimeMillis().toString()),
                title = data.optString("title", "Alert"),
                message = data.optString("message", ""),
                severity = data.optString("severity", "info"),
                timestamp = System.currentTimeMillis()
            )
            _systemAlerts.value = _systemAlerts.value + alert
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onCADData(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            _cadData.value = CADData(
                id = data.optString("id", ""),
                name = data.optString("name", "Unknown"),
                description = data.optString("description", ""),
                format = data.optString("format", "STL"),
                vertices = data.optInt("vertices", 0),
                faces = data.optInt("faces", 0)
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    private fun onCADStatus(args: Array<Any?>) {
        if (args.isEmpty()) return
        val data = args[0] as JSONObject
        try {
            _cadStatus.value = CADStatus(
                status = data.optString("status", "idle"),
                progress = data.optInt("progress", 0),
                currentStep = data.optString("current_step", "")
            )
        } catch (e: Exception) { /* ignore malformed */ }
    }

    // ----- helpers -----

    private fun rawEmit(event: String, data: JSONObject) {
        try { socket?.emit(event, data) } catch (e: Exception) { }
    }

    private fun flushOutbox() {
        val pending = synchronized(_outbox) {
            val copy = _outbox.toMutableList()
            _outbox.clear()
            copy
        }
        for (queued in pending) rawEmit(queued.event, queued.data)
    }

    private fun requestSystemMonitor() {
        rawEmit("get_system_monitor", JSONObject())
    }

    private fun startMonitor() {
        monitorJob?.cancel()
        monitorJob = CoroutineScope(Dispatchers.IO).launch {
            while (_connectionState.value == ConnectionState.CONNECTED) {
                try {
                    requestSystemMonitor()
                    delay(2000L)
                } catch (e: Exception) {
                    delay(2000L)
                }
            }
        }
    }

    private fun addMessage(text: String, isFromUser: Boolean, isSystem: Boolean) {
        val current = _messages.value.toMutableList()
        current.add(FridayMessage(text, isFromUser, isSystem))
        _messages.value = current
    }
}
