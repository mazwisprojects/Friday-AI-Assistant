# Socket.IO Event Contract — Server ↔ Android App

## Status Legend
- ✅ **Working** — Server emits real data, Android app handles it
- ⚠️ **Partial** — Server emits but with limitations
- ❌ **Stub/Missing** — Server returns hardcoded/empty data or doesn't emit at all

---

## Server → Android (Events the server emits, app receives)

| Event | Server Status | Android Handler | Notes |
|-------|--------------|-----------------|-------|
| `status` | ✅ Real | `onStatus()` | Connection status messages |
| `transcription` | ✅ Real | `onTranscription()` | Voice transcription from Gemini |
| `tool_confirmation_request` | ✅ Real | `onToolConfirmation()` | Confirmation prompt for dangerous actions |
| `confirmation_expired` | ✅ Real | `onConfirmationExpired()` | Confirmation timeout |
| `approval_response_ack` | ✅ Real | `onApprovalAck()` | Approval response acknowledged |
| `dashboard_system_update` | ✅ Real | `onSystemMetrics()` | System metrics (CPU, RAM, GPU, etc.) |
| `system_monitor_data` | ✅ Real | `onSystemMetrics()` | Same as above, alternate event name |
| `audio_data` | ✅ Real | `onAudioData()` | Audio playback data |
| `file_processing_result` | ✅ Real | `onFileProcessingResult()` | File upload processing result |
| `file_download` | ✅ Real | `onFileDownload()` | File download from server |
| `task_cards` | ✅ Real | `onTaskCards()` | Task/project cards |
| `task_action_response` | ✅ Real | `onTaskActionResponse()` | Task action result |
| `autonomy_status` | ✅ Real | `onAutonomyStatus()` | Autonomy pipeline status |
| `autonomy_approval_result` | ✅ Real | `onAutonomyApprovalResult()` | Autonomy proposal approval result |
| `reminders_list` | ✅ Real | `onRemindersList()` | Reminders list |
| `unified_notification` | ✅ Real | `onUnifiedNotification()` | System notifications |
| `action_plan` | ✅ Real | `onActionPlan()` | Action plan steps |
| `settings` | ✅ Real | `onSettings()` | Settings data |
| `weather_data` | ✅ Real | `onWeatherData()` | Weather information |
| `google_account_status` | ✅ Real | `onGoogleAccountStatus()` | Google account connection status |
| `kasa_devices` | ✅ Real | `onKasaDevices()` | Kasa smart devices list |
| `printer_list` | ✅ Real | `onPrinters()` | 3D printers list |
| `system_alert` | ✅ Real | `onSystemAlert()` | System alerts |
| `cad_data` | ✅ Real | `onCADData()` | CAD model data |
| `cad_status` | ✅ Real | `onCADStatus()` | CAD generation status |

---

## Android → Server (Events the app emits, server receives)

| Event | Android Emits | Server Handler | Notes |
|-------|--------------|----------------|-------|
| `user_input` | ✅ | `on_user_input` | User text input |
| `get_system_monitor` | ✅ | `get_system_monitor` | Request system metrics |
| `approval_response` | ✅ | `on_approval_response` | Approval response |
| `start_audio` | ✅ | `on_start_audio` | Start audio session |
| `stop_audio` | ✅ | `on_stop_audio` | Stop audio session |
| `upload_file_for_awareness` | ✅ | `on_upload_file` | Upload file for AI awareness |
| `get_task_cards` | ✅ | `get_task_cards` | Request task cards |
| `task_action` | ✅ | `on_task_action` | Task action (complete, defer, etc.) |
| `get_autonomy_status` | ✅ | `get_autonomy_status` | Request autonomy status |
| `approve_autonomy_proposal` | ✅ | `on_approve_autonomy_proposal` | Approve autonomy proposal |
| `resolve_security_finding` | ✅ | `on_resolve_security_finding` | Resolve security finding |
| `get_reminders` | ✅ | `get_reminders` | Request reminders |
| `add_reminder` | ✅ | `on_add_reminder` | Add new reminder |
| `delete_reminder` | ✅ | `on_delete_reminder` | Delete reminder |
| `get_kasa_devices` | ✅ | `get_kasa_devices` | Request Kasa devices |
| `get_printers` | ✅ | `get_printers` | Request printers |
| `get_google_account_status` | ✅ | `get_google_account_status` | Request Google account status |
| `get_weather` | ✅ | `get_weather` | Request weather data |
| `connect_google_account` | ✅ | `on_connect_google_account` | Connect Google account |
| `disconnect_google_account` | ✅ | `on_disconnect_google_account` | Disconnect Google account |
| `discover_kasa` | ✅ | `on_discover_kasa` | Discover Kasa devices |
| `control_light` | ✅ | `on_control_light` | Control Kasa light |

---

## Additional Server Events (Not handled by Android)

These events are emitted by the server but not currently listened to by the Android app:

| Event | Description |
|-------|-------------|
| `auth_status` | Authentication status |
| `auth_frame` | Camera frame for face auth |
| `contacts_list` | Google contacts list |
| `contact_list` | Filtered contacts list |
| `contacts_status` | Contact operation status |
| `provider_routing` | AI provider routing config |
| `openclaw_status` | OpenClaw bridge status |
| `openclaw_capabilities` | OpenClaw tool capabilities |
| `text_provider_status` | Text provider status |
| `agent_console` | Agent console data |
| `agent_console_action_result` | Agent console action result |
| `slicing_progress` | 3D print slicing progress |
| `slicer_profiles` | Slicer profiles |
| `print_result` | 3D print result |
| `kasa_update` | Kasa device state update |
| `error` | Error messages |

---

## Summary

✅ **All critical events are working!** The server emits real data for all events the Android app listens to. There are no stubs or fake data for the events the app actually handles.

The events listed in "Additional Server Events" are typically emitted to specific clients (like the web dashboard) and are not needed for the Android app's core functionality.
