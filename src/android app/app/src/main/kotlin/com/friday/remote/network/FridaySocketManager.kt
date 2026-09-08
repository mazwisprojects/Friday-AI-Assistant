package com.friday.remote.network

import android.content.Context
import com.friday.remote.security.SecurityManager
import io.socket.client.IO
import io.socket.client.Socket
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sleep
import org.json.JSONObject
import java.net.URISyntaxException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Socket.IO client aligned with the real F.R.I.D.A.Y server contract (backend/server.py).
 *
 * EMIT (app -> server):  user_input {text}, get_system_monitor {},
 *   approval_response {approval_id, approved}, start_audio {}, stop_audio {},
 *   upload_file_for_awareness {filename, data, mime_type, action}
 * RECEIVE (server -> app): status {msg}, transcription {sender, text},
 *   tool_confirmation_request {id, tool, args}, confirmation_expired {id, tool},
 *   approval_response_ack, dashboard_system_update / system_monitor_data,
 *   audio_data {data: [bytes]}, file_processing_result, file_download
 */
@Singleton
class FridaySocketManager @Inject constructor(
    private val securityManager: SecurityManager,
    private val context: Context
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

    fun connect() {
        if (socket?.connected() == true) return
        _connectionState.value = ConnectionState.CONNECTING
        try {
            val opts = IO.Options().apply {
                forceNew = true
                reconnection = true
            }
            socket = IO.socket(securityManager.getServerUrl(), opts)

            socket?.on(Socket.EVENT_CONNECT) {
                _connectionState.value = ConnectionState.CONNECTED
                flushOutbox()
                requestSystemMonitor()
                startMonitor()
            }
            socket?.on(Socket.EVENT_DISCONNECT) {
                _connectionState.value = ConnectionState.DISCONNECTED
                monitorJob?.cancel()
            }
            socket?.on(Socket.EVENT_CONNECT_ERROR) {
                _connectionState.value = ConnectionState.ERROR
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

            socket?.connect()
        } catch (e: URISyntaxException) {
            _connectionState.value = ConnectionState.ERROR
        } catch (e: Exception) {
            _connectionState.value = ConnectionState.ERROR
        }
    }

    fun disconnect() {
        monitorJob?.cancel()
        socket?.disconnect()
        _connectionState.value = ConnectionState.DISCONNECTED
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

    // ----- server -> app event handlers -----

    private fun onStatus(args: Array<Any?>) {
        if (args.isEmpty) return
        val data = args[0] as JSONObject
        val msg = data.optString("msg", data.optString("text", "System"))
        if (msg.isNotEmpty()) addMessage(msg, false, true)
    }

    private fun onTranscription(args: Array<Any?>) {
        if (args.isEmpty) return
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
        if (args.isEmpty) return
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
        if (args.isEmpty) return
        val data = args[0] as JSONObject
        val id = data.optString("id", "")
        if (_pendingApproval.value?.id == id) _pendingApproval.value = null
        val tool = data.optString("tool", "tool")
        addMessage("Confirmation expired for \"$tool\". The action was not executed.", false, true)
    }

    private fun onApprovalAck(args: Array<Any?>) {
        if (args.isEmpty) return
        val data = args[0] as JSONObject
        addMessage(if (data.optBoolean("approved", false)) "Approved." else "Denied.", false, true)
    }

    private fun onSystemMetrics(args: Array<Any?>) {
        if (args.isEmpty) return
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
        if (args.isEmpty) return
        try {
            val arr = (args[0] as JSONObject).getJSONArray("data")
            val bytes = ArrayList<Int>(arr.length())
            for (i in 0 until arr.length()) bytes.add(arr.optInt(i, 0))
            audioSink?.onAudioData(bytes)
        } catch (e: Exception) { /* ignore malformed frame */ }
    }

    private fun onFileProcessingResult(args: Array<Any?>) {
        if (args.isEmpty) return
        val data = args[0] as JSONObject
        val error = data.optString("error", "")
        val ok = data.optBoolean("ok", error.isEmpty())
        addMessage(if (ok) "File received by Friday." else "File upload failed: $error", false, true)
    }

    private fun onFileDownload(args: Array<Any?>) {
        if (args.isEmpty) return
        val data = args[0] as JSONObject
        val name = data.optString("name", data.optString("filename", "file"))
        addMessage("File received from Friday: $name", false, true)
        // TODO: decode base64 payload to context.filesDir once the server payload shape is pinned.
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
                    sleep(2000L)
                } catch (e: Exception) {
                    sleep(2000L)
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
