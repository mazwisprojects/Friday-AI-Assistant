import asyncio
import base64
import json
import hmac
import logging
import os
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from logging_config import setup_logging

# Configure logging before importing the application modules so their loggers
# and any import-time failures use the same handlers.
setup_logging()

# Modern Windows Python uses the Proactor event-loop policy by default, which
# supports asyncio subprocesses without calling the deprecated policy API.

import socketio
import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)



# Ensure we can import both backend modules and repo-root modules.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
for candidate in (BACKEND_DIR, ROOT_DIR):
    if candidate not in sys.path:
        sys.path.append(candidate)

import friday
from actions import system_monitor as system_monitor_module
from contacts_manager import ContactsManager
from google_account import GoogleAccount
from claude_provider import ClaudeProvider
from openclaw_bridge import OpenClawBridge
from memory_manager import MemoryManager
from authenticator import FaceAuthenticator
from kasa_agent import KasaAgent
from actions import agent_dispatcher as agent_dispatcher_module

# Create a Socket.IO server with CORS configured for remote access
# Allow localhost for development, Electron app origins, and remote connections
# For production, consider restricting this to specific origins or using a reverse proxy
allowed_origins = [
    'http://localhost:5173',  # Vite dev server
    'http://127.0.0.1:5173',  # Alternative localhost
    'capacitor://localhost',  # Capacitor/Electron
    'ionic://localhost',      # Ionic
    # Allow all origins for remote access (Android app, Tailscale, etc.)
    # Socket.IO clients from mobile apps may not send a standard Origin header
    '*',
]
SERVER_TOKEN = os.getenv("FRIDAY_SERVER_TOKEN", "").strip()
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=allowed_origins,
    # Allow long-polling as fallback for networks that block WebSocket
    # This is important for mobile networks that may have restrictive proxies
    transports=['websocket', 'polling'],
    # Increase ping timeout for mobile networks with higher latency
    ping_timeout=60,
    ping_interval=25,
    # Maximum buffer size for large file uploads (50MB)
    max_http_buffer_size=50 * 1024 * 1024,
)
app = FastAPI()
app_socketio = socketio.ASGIApp(sio, app)

import signal

# --- SHUTDOWN HANDLER ---
def signal_handler(sig, frame):
    logger.info("Caught signal %s. Exiting gracefully...", sig)
    # Clean up audio loop
    if audio_loop:
        try:
            logger.info("Stopping Audio Loop...")
            audio_loop.stop()
        except Exception as e:
            logger.error("Error stopping audio loop: %s", e)
    # Force kill
    logger.info("Force exiting...")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Global state
audio_loop = None
loop_task = None
authenticator = None
kasa_agent = KasaAgent()
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "initiative": {
        "enabled": True,
        "interval_minutes": 20,
        "quiet_start": 23,
        "quiet_end": 8,
        "max_daily_actions": 6,
        "goal_nudge_hours": 4,
        "approval_reminder_hours": 2,
        "user_idle_minutes": 3,
    },
    "provider_routing": {
        "voice_vision": "Gemini Live",
        "text_reasoning": "Gemini",
        "coding": "OpenClaw",
        "documents": "OpenClaw",
        "background_agents": "OpenClaw",
    },
    "face_auth_enabled": False, # Default OFF as requested
    "tool_permissions": {
        "generate_cad": False,
        "run_web_agent": False,
        "write_file": False,
        "read_directory": False,
        "read_file": False,
        "create_project": False,
        "switch_project": False,
        "list_projects": False,
        "search_memory": False,
        "list_smart_devices": False,
        "control_light": False,
        "discover_printers": False,
        "print_stl": False,
        "get_print_status": False,
        "iterate_cad": False,
        "computer_control": False,
        "computer_settings": False,
        "manage_files": False,
        "open_application": False,
        "get_system_status": False,
        "get_local_time": False,
        "gmail_read": False,
        "gmail_thread_read": False,
        "gmail_create_draft": False,
        "get_weather": False,
        "google_calendar_create": False,
        "google_calendar_list": False,
        "google_calendar_update": False,
        "google_calendar_delete": False,
        "google_calendar_recurring": False,
        "set_reminder": False,
        "desktop_control": False,
        "web_search": False,
        "send_message": False,
        "youtube_video": False,
        "browser_control": False,
        "code_helper": False,
        "build_project": False,
        "find_flights": False,
        "game_updater": False,
        "process_file": False,
        "manage_monitors": False,
        "contacts_manager": False,
        "google_contacts_import": False,
        "google_contacts_sync": False,
        "sync_google_services": False,
        "google_drive_list": False,
        "google_contacts_read": False,
        "mute_alert_category": False,
        "undo_last_action": False,
        "manage_uploads": False,
        "cancel_current_task": False,
        "self_maintenance": False,
        "run_powershell_command": False,
        "git_workflow": False,
        "deploy_agent": False,
        "run_routine": False
    },
    "printers": [], # List of {host, port, name, type}
    "kasa_devices": [], # List of {ip, alias, model}
    "camera_flipped": False, # Invert cursor horizontal direction
    "system_alerts_enabled": True,
    "quiet_mode": False,
    "interrupt_preferences": {
        "urgent_only": False,
        "emergencies_only": False,
        "custom_categories": []
    },
    "current_mode": "active",
    "muted_alert_categories": [],
    "alert_cooldowns": {
        "cpu": 1800,
        "ram": 1800,
        "temp": 900,
        "gpu": 900
    },
    "upload_retention_days": 30,
    "max_upload_storage_mb": 1024
}

import copy as _copy
# Deep-copy: load_settings() updates SETTINGS["tool_permissions"] in place, and a
# shallow .copy() would let that mutate DEFAULT_SETTINGS itself.
SETTINGS = _copy.deepcopy(DEFAULT_SETTINGS)
contacts_manager = ContactsManager(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
global_memory_manager = MemoryManager(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
google_account = GoogleAccount(BACKEND_DIR)

async def ensure_audio_ready(sid, require_session=True):
    if not audio_loop:
        await sio.emit('error', {'msg': 'Friday is still starting. Try again in a moment.'}, room=sid)
        return False
    if require_session and not audio_loop.session:
        await sio.emit('error', {'msg': 'Friday is connected but the Gemini session is not ready yet.'}, room=sid)
        return False
    return True

def load_settings():
    global SETTINGS
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k, v in loaded.items():
                        if k == "tool_permissions" and isinstance(v, dict):
                            SETTINGS["tool_permissions"].update(v)
                        else:
                            SETTINGS[k] = v
                    # Older persisted settings treated CAD generation as enabled
                    # when a permissions block existed without that key.
                    if isinstance(loaded.get("tool_permissions"), dict) and "generate_cad" not in loaded["tool_permissions"]:
                        SETTINGS["tool_permissions"]["generate_cad"] = True
            logger.info("Loaded settings")
        except Exception as e:
            logger.exception("Error loading settings")
    return SETTINGS

def save_settings(settings=None):
    global SETTINGS
    if settings is not None:
        SETTINGS = settings
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(SETTINGS, f, indent=4)
        logger.info("Settings saved")
    except Exception as e:
        logger.exception("Error saving settings")
    return SETTINGS

# Load on startup
load_settings()
global_memory_manager.upload_retention_days = max(1, int(SETTINGS.get("upload_retention_days", 30)))
global_memory_manager.max_upload_storage_bytes = int(SETTINGS.get("max_upload_storage_mb", 1024)) * 1024 * 1024

authenticator = None
kasa_agent = KasaAgent(known_devices=SETTINGS.get("kasa_devices"))
# tool_permissions is now SETTINGS["tool_permissions"]

@app.on_event("startup")
async def startup_event():
    import sys
    logger.info("Startup event triggered; Python version: %s", sys.version)
    try:
        loop = asyncio.get_running_loop()
        logger.debug("Running loop: %s", type(loop))
        policy = asyncio.get_event_loop_policy()
        logger.debug("Current event loop policy: %s", type(policy))
    except Exception as e:
        logger.exception("Error checking event loop")

    logger.info("Initializing Kasa Agent")
    await kasa_agent.initialize()

@app.get("/status")
async def status():
    return {
        "status": "running",
        "service": "F.R.I.D.A.Y Backend",
        "gemini_live": bool(os.getenv("GEMINI_API_KEY")),
        "claude_text": ClaudeProvider().available,
        "google_account": google_account.status()["connected"],
        "audio_runtime": bool(audio_loop),
        "openclaw": friday.openclaw_bridge.status(),
    }

@sio.event
async def get_contacts(sid, data=None):
    contacts = contacts_manager.list_contacts()
    await sio.emit('contacts_list', {'contacts': contacts}, room=sid)

    platform = (data or {}).get('platform')
    filtered = [c for c in contacts if not platform or platform in c.get('channels', {})]
    await sio.emit('contact_list', filtered, room=sid)

@sio.event
async def save_contact(sid, data):
    result = contacts_manager.add_or_update(
        data.get('name', ''), data.get('recipient', ''), data.get('platform', 'whatsapp')
    )
    await sio.emit('contacts_status', {'msg': result}, room=sid)

@sio.event
async def delete_contact(sid, data):
    result = contacts_manager.remove(data.get('name', ''), data.get('platform', ''))
    await sio.emit('contacts_status', {'msg': result}, room=sid)

@sio.event
async def connect(sid, environ, auth=None):
    if SERVER_TOKEN:
        provided_token = str((auth or {}).get("token", ""))
        if not provided_token or not hmac.compare_digest(provided_token, SERVER_TOKEN):
            logger.warning("Rejected unauthenticated client: %s", sid)
            return False
    logger.info("Client connected: %s", sid)
    await sio.emit('status', {'msg': 'Connected to F.R.I.D.A.Y Backend'}, room=sid)

    global authenticator
    
    # Callback for Auth Status
    async def on_auth_status(is_auth):
        logger.info("Auth status change: %s", is_auth)
        await sio.emit('auth_status', {'authenticated': is_auth})

    # Callback for Auth Camera Frames
    async def on_auth_frame(frame_b64):
        await sio.emit('auth_frame', {'image': frame_b64})

    # Initialize Authenticator if not already done
    if authenticator is None:
        authenticator = FaceAuthenticator(
            reference_image_path=str(Path(__file__).with_name("reference.jpg")),
            on_status_change=on_auth_status,
            on_frame=on_auth_frame
        )
    
    # Check if already authenticated or needs to start
    if authenticator.authenticated:
        await sio.emit('auth_status', {'authenticated': True})
    else:
        # Check Settings for Auth
        if SETTINGS.get("face_auth_enabled", False):
            await sio.emit('auth_status', {'authenticated': False})
            # Start the auth loop in background
            asyncio.create_task(authenticator.start_authentication_loop())
        else:
            # Bypass Auth
            logger.info("Face auth disabled; auto-authenticating")
            # We don't change authenticator state to true to avoid confusion if re-enabled? 
            # Or we should just tell client it's auth'd.
            await sio.emit('auth_status', {'authenticated': True})

@sio.event
async def disconnect(sid):
    logger.info("Client disconnected: %s", sid)
    if audio_loop:
        audio_loop.cancel_pending_confirmations()

@sio.event
async def start_audio(sid, data=None):
    global audio_loop, loop_task
    
    # Optional: Block if not authenticated
    # Only block if auth is ENABLED and not authenticated
    if SETTINGS.get("face_auth_enabled", False):
        if authenticator and not authenticator.authenticated:
            logger.warning("Blocked start_audio: client is not authenticated")
            await sio.emit('error', {'msg': 'Authentication Required'})
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return

    logger.info("Starting audio loop")
    
    device_index = None
    device_name = None
    if data:
        if 'device_index' in data:
            device_index = data['device_index']
        if 'device_name' in data:
            device_name = data['device_name']
            
    logger.info("Using input device: name=%r, index=%s", device_name, device_index)
    
    if audio_loop:
        if loop_task and (loop_task.done() or loop_task.cancelled()):
             logger.warning("Audio loop task finished or was cancelled; restarting")
             audio_loop.cancel_pending_confirmations()
             audio_loop = None
             loop_task = None
        else:
             logger.info("Audio loop already running; reconnecting client to session")
             await sio.emit('status', {'msg': 'F.R.I.D.A.Y Already Running'})
             return


    # Callback to send audio data to frontend
    def on_audio_data(data_bytes):
        # We need to schedule this on the event loop
        # This is high frequency, so we might want to downsample or batch if it's too much
        asyncio.create_task(sio.emit('audio_data', {'data': list(data_bytes)}))

    # Callback to send CAL data to frontend
    def on_cad_data(data):
        info = f"{len(data.get('vertices', []))} vertices" if 'vertices' in data else f"{len(data.get('data', ''))} bytes (STL)"
        logger.debug("Sending CAD data to frontend: %s", info)
        asyncio.create_task(sio.emit('cad_data', data))

    # Callback to send Browser data to frontend
    def on_web_data(data):
        logger.debug("Sending browser data to frontend: %s log chars", len(data.get("log", "")))
        asyncio.create_task(sio.emit('browser_frame', data))
        
    # Callback to send Transcription data to frontend
    def on_transcription(data):
        # data = {"sender": "User"|"FRIDAY", "text": "..."}
        asyncio.create_task(sio.emit('transcription', data))

    # Callback to send Confirmation Request to frontend
    def on_tool_confirmation(data):
        # data = {"id": "uuid", "tool": "tool_name", "args": {...}}
        logger.info("Requesting confirmation for tool: %s", data.get("tool"))
        asyncio.create_task(sio.emit('tool_confirmation_request', data))

    def on_confirmation_expired(data):
        logger.warning("Confirmation expired for tool: %s", data.get("tool"))
        asyncio.create_task(sio.emit('confirmation_expired', data, room=sid))

    # Callback to send CAD status to frontend
    def on_cad_status(status):
        # status can be: 
        # - a string like "generating" (from friday.py handle_cad_request)
        # - a dict with {status, attempt, max_attempts, error} (from CadAgent)
        if isinstance(status, dict):
            logger.debug("Sending CAD status: %s (attempt %s/%s)", status.get("status"), status.get("attempt"), status.get("max_attempts"))
            asyncio.create_task(sio.emit('cad_status', status))
        else:
            # Legacy: simple string
            logger.debug("Sending CAD status: %s", status)
            asyncio.create_task(sio.emit('cad_status', {'status': status}))

    # Callback to send CAD thoughts to frontend (streaming)
    def on_cad_thought(thought_text):
        asyncio.create_task(sio.emit('cad_thought', {'text': thought_text}))

    # Callback to send Project Update to frontend
    def on_project_update(project_name):
        logger.info("Sending project update: %s", project_name)
        asyncio.create_task(sio.emit('project_update', {'project': project_name}))

    # Callback to send Device Update to frontend
    previous_device_states = {}

    def on_device_update(devices):
        # devices is a list of dicts
        logger.debug("Sending Kasa device update: %s devices", len(devices))
        asyncio.create_task(sio.emit('kasa_devices', devices))
        for device in devices:
            device_id = device.get("ip") or device.get("alias")
            state = device.get("is_on")
            if device_id and device_id in previous_device_states and previous_device_states[device_id] != state:
                if audio_loop:
                    asyncio.create_task(audio_loop.notifications.notify("smart_home", "Smart-home update", f"{device.get('alias', device_id)} is now {'on' if state else 'off'}."))
            if device_id:
                previous_device_states[device_id] = state

    # Callback to send Error to frontend
    def on_error(msg):
        logger.error("Sending error to frontend: %s", msg)
        asyncio.create_task(sio.emit('error', {'msg': msg}))

    def on_plan_update(plan):
        asyncio.create_task(sio.emit('action_plan', plan))

    def on_notification(notification):
        asyncio.create_task(sio.emit('unified_notification', notification))

    def on_alert_settings_update(alert_settings):
        SETTINGS.update(alert_settings)
        save_settings()

    # Initialize FRIDAY
    try:
        logger.info("Initializing AudioLoop with device_index=%s", device_index)
        audio_loop = friday.AudioLoop(
            video_mode="none", 
            on_audio_data=on_audio_data,
            on_cad_data=on_cad_data,
            on_web_data=on_web_data,
            on_transcription=on_transcription,
            on_tool_confirmation=on_tool_confirmation,
            on_confirmation_expired=on_confirmation_expired,
            on_cad_status=on_cad_status,
            on_cad_thought=on_cad_thought,
            on_project_update=on_project_update,
            on_device_update=on_device_update,
            on_error=on_error,
            on_alert_settings_update=on_alert_settings_update,
            on_plan_update=on_plan_update,
            on_notification=on_notification,
            authenticated=(not SETTINGS.get("face_auth_enabled", False) or bool(authenticator and authenticator.authenticated)),

            input_device_index=device_index,
            input_device_name=device_name,
            kasa_agent=kasa_agent
        )
        logger.info("AudioLoop initialized successfully")

        audio_loop.memory_manager.upload_retention_days = max(1, int(SETTINGS.get("upload_retention_days", 30)))
        audio_loop.memory_manager.max_upload_storage_bytes = int(SETTINGS.get("max_upload_storage_mb", 1024)) * 1024 * 1024
        audio_loop.memory_manager.cleanup_expired_uploads()

        # Apply current permissions
        audio_loop.update_permissions(SETTINGS["tool_permissions"])
        audio_loop.system_monitor.configure(
            alerts_enabled=SETTINGS.get("system_alerts_enabled", True),
            muted_categories=set(SETTINGS.get("muted_alert_categories", [])),
            cooldowns=SETTINGS.get("alert_cooldowns", {}),
        )
        
        # Check initial mute state
        if data and data.get('muted', False):
            logger.info("Starting with audio paused")
            audio_loop.set_paused(True)

        logger.info("Creating asyncio task for AudioLoop.run()")
        loop_task = asyncio.create_task(audio_loop.run())
        
        # Add a done callback to catch silent failures in the loop
        def handle_loop_exit(task):
            try:
                task.result()
            except asyncio.CancelledError:
                logger.info("Audio loop cancelled")
            except Exception as e:
                logger.exception("Audio loop crashed")
                # You could emit 'error' here if you have context
        
        loop_task.add_done_callback(handle_loop_exit)
        
        logger.info("Emitting F.R.I.D.A.Y started status")
        await sio.emit('status', {'msg': 'F.R.I.D.A.Y Started'})
        
        # Send initial dashboard data
        async def send_initial_dashboard():
            await asyncio.sleep(0.5)
            dashboard_data = {
                'active_tasks': get_active_tasks(),
                'pending_approvals': get_pending_approvals(),
                'memory_summary': build_memory_summary(),
                'proactive_suggestions': build_proactive_suggestions(),
                'routine_queue': list_routine_queue(),
                'quiet_mode': get_quiet_mode(),
                'interrupt_preferences': get_interrupt_preferences(),
                'system_health': system_monitor_module.get_system_status() if hasattr(system_monitor_module, 'get_system_status') else {},
                'current_mode': 'active',
            }
            await sio.emit('dashboard_data', dashboard_data)
        
        asyncio.create_task(send_initial_dashboard())

        # Load saved printers
        saved_printers = SETTINGS.get("printers", [])
        if saved_printers and audio_loop.printer_agent:
            logger.info("Loading %s saved printers", len(saved_printers))
            for p in saved_printers:
                audio_loop.printer_agent.add_printer_manually(
                    name=p.get("name", p["host"]),
                    host=p["host"],
                    port=p.get("port", 80),
                    printer_type=p.get("type", "moonraker"),
                    camera_url=p.get("camera_url")
                )
        
        # Start Printer Monitor
        asyncio.create_task(monitor_printers_loop())
        asyncio.create_task(monitor_tasks_loop())
        
    except Exception as e:
        logger.exception("Critical error starting F.R.I.D.A.Y")
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'msg': f"Failed to start: {str(e)}"})
        audio_loop = None # Ensure we can try again


async def monitor_printers_loop():
    """Background task to query printer status periodically."""
    logger.info("Starting printer monitor loop")
    previous_states = {}
    while audio_loop and audio_loop.printer_agent:
        try:
            agent = audio_loop.printer_agent
            if not agent.printers:
                await asyncio.sleep(5)
                continue
                
            tasks = []
            for host, printer in agent.printers.items():
                if printer.printer_type.value != "unknown":
                    tasks.append(agent.get_print_status(host))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        pass # Ignore errors for now
                    elif res:
                        # res is PrintStatus object
                        status_data = res.to_dict()
                        await sio.emit('print_status_update', status_data)
                        printer_id = status_data.get('printer') or status_data.get('name') or status_data.get('host')
                        state = str(status_data.get('state', '')).lower()
                        old_state = previous_states.get(printer_id)
                        if printer_id and old_state and old_state != state and state in {'complete', 'completed', 'finished', 'idle'}:
                            if audio_loop:
                                await audio_loop.notifications.notify('printer', 'Print complete', f'{printer_id} finished printing.')
                        if printer_id:
                            previous_states[printer_id] = state
                        
        except asyncio.CancelledError:
            logger.info("Printer monitor cancelled")
            break
        except Exception as e:
            logger.exception("Printer monitor loop error")

async def monitor_tasks_loop():
    """Push task cards and alert once when an open task becomes overdue."""
    logger.info("Starting task monitor loop")
    alerted = set()
    while audio_loop:
        try:
            tasks = audio_loop.task_manager.list('open')
            overdue = audio_loop.task_manager.overdue()
            await sio.emit('task_cards', tasks)
            for task in overdue:
                if task['id'] not in alerted:
                    alerted.add(task['id'])
                    await audio_loop.notifications.notify('tasks', 'Overdue task', task.get('title', 'A task is overdue'), 'high')
            alerted.intersection_update({task['id'] for task in overdue})
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Task monitor loop error")
            await asyncio.sleep(60)
            
        await asyncio.sleep(2) # Update every 2 seconds for responsiveness

@sio.event
async def stop_audio(sid):
    global audio_loop
    if audio_loop:
        audio_loop.stop() 
        logger.info("Stopping audio loop")
        audio_loop = None
        await sio.emit('status', {'msg': 'F.R.I.D.A.Y Stopped'})

@sio.event
async def pause_audio(sid):
    global audio_loop
    if audio_loop:
        audio_loop.set_paused(True)
        logger.info("Pausing audio")
        await sio.emit('status', {'msg': 'Audio Paused'})

@sio.event
async def resume_audio(sid):
    global audio_loop
    if audio_loop:
        audio_loop.set_paused(False)
        logger.info("Resuming audio")
        await sio.emit('status', {'msg': 'Audio Resumed'})

@sio.event
async def confirm_tool(sid, data):
    # data: { "id": "...", "confirmed": True/False }
    request_id = data.get('id')
    confirmed = data.get('confirmed', False)
    
    logger.debug("Received confirmation response for %s: %s", request_id, confirmed)
    
    if audio_loop:
        audio_loop.resolve_tool_confirmation(request_id, confirmed)
    else:
        logger.warning("Audio loop not active; cannot resolve confirmation")

@sio.event
async def shutdown(sid, data=None):
    """Gracefully shutdown the server when the application closes."""
    global audio_loop, loop_task, authenticator
    
    logger.info("Shutdown signal received from frontend")
    
    # Stop audio loop
    if audio_loop:
        logger.info("Stopping audio loop")
        audio_loop.stop()
        audio_loop = None
    
    # Cancel the loop task if running
    if loop_task and not loop_task.done():
        logger.info("Cancelling audio loop task")
        loop_task.cancel()
        loop_task = None
    
    # Stop authenticator if running
    if authenticator:
        logger.info("Stopping authenticator")
        authenticator.stop()
    
    logger.info("Graceful shutdown complete; terminating process")
    
    # Force exit immediately - os._exit bypasses cleanup but ensures termination
    os._exit(0)

@sio.event
async def user_input(sid, data):
    text = data.get('text')
    logger.debug("User input received: %r", text)
    
    if not await ensure_audio_ready(sid):
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return

    if text:
        logger.debug("Sending message to model: %r", text)
        
        # Log User Input to Project History
        if audio_loop and audio_loop.project_manager:
            audio_loop.project_manager.log_chat("User", text)

        # Log User Input to Global Memory (not project-scoped, never cleared)
        if audio_loop and audio_loop.memory_manager:
            audio_loop.memory_manager.append_message("User", text, project=audio_loop.project_manager.current_project)
            asyncio.create_task(audio_loop.extract_important_facts("User", text))

        # Reset the proactive-speech silence timer
        audio_loop.notify_activity()

        if audio_loop.openclaw_bridge.should_route(text):
            await sio.emit('status', {'msg': 'OpenClaw is planning this request...'}, room=sid)

            async def run_openclaw_request():
                try:
                    plan = await asyncio.to_thread(audio_loop.openclaw_bridge.plan, text)
                    result = json.dumps(plan, ensure_ascii=False, indent=2)
                    await sio.emit('transcription', {'sender': 'FRIDAY', 'text': f"\nOpenClaw plan:\n{result}\n"}, room=sid)
                    await sio.emit('unified_notification', {
                        'category': 'openclaw', 'title': 'OpenClaw plan ready',
                        'message': f"Prepared {len(plan.get('steps', []))} step(s).",
                    }, room=sid)
                except Exception as error:
                    await sio.emit('error', {'msg': f'OpenClaw planning failed: {error}'}, room=sid)

            audio_loop.spawn_background_task(run_openclaw_request())
            return

        # Use the same 'send' method that worked for audio, as 'send_realtime_input' and 'send_client_content' seem unstable in this env
        # INJECT VIDEO FRAME IF AVAILABLE (VAD-style logic for Text Input)
        if audio_loop and audio_loop.live_video_enabled and audio_loop._latest_image_payload:
            logger.debug("Piggybacking video frame with text input")
            try:
                # Send frame first
                await audio_loop.session.send(input=audio_loop._latest_image_payload, end_of_turn=False)
            except Exception as e:
                logger.exception("Failed to send piggyback frame")
                
        await audio_loop.session.send(input=text, end_of_turn=True)
        logger.debug("Message sent to model successfully")

import json
from datetime import datetime
from pathlib import Path

# ... (imports)

@sio.event
async def video_frame(sid, data):
    # data should contain 'image' which is binary (blob) or base64 encoded
    image_data = data.get('image')
    if image_data and audio_loop:
        # We don't await this because we don't want to block the socket handler
        # But send_frame is async, so we create a task
        asyncio.create_task(audio_loop.send_frame(image_data))

@sio.event
async def set_live_video(sid, data):
    """Enable/disable continuous webcam streaming into the Gemini Live session."""
    enabled = bool((data or {}).get('enabled', False))
    logger.info("Live vision %s by client", "enabled" if enabled else "disabled")
    if audio_loop:
        audio_loop.set_live_video(enabled)
    status = audio_loop.vision_status() if audio_loop else {
        'enabled': False,
        'session_ready': False,
        'paused': False,
        'frames_received': 0,
        'frames_sent': 0,
    }
    await sio.emit('video_status', status, room=sid)


@sio.event
async def get_vision_status(sid):
    """Return explicit webcam and Gemini vision diagnostics to the client."""
    status = audio_loop.vision_status() if audio_loop else {
        'enabled': False,
        'session_ready': False,
        'paused': False,
        'frames_received': 0,
        'frames_sent': 0,
    }
    await sio.emit('video_status', status, room=sid)


@sio.event
async def set_vision_source(sid, data):
    """Select camera, screen, or no visual source for the next Live session."""
    source = (data or {}).get('source', 'camera')
    if not audio_loop:
        await sio.emit('video_status', {
            'enabled': False,
            'session_ready': False,
            'source': source,
            'error': 'Audio session is not running.',
        }, room=sid)
        return
    result = audio_loop.set_vision_source(source)
    status = audio_loop.vision_status()
    status.update(result)
    await sio.emit('video_status', status, room=sid)

@sio.event
async def save_memory(sid, data):
    try:
        messages = data.get('messages', [])
        if not messages:
            logger.info("No messages to save")
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return

        # Ensure directory exists
        memory_dir = Path("long_term_memory")
        memory_dir.mkdir(exist_ok=True)

        # Generate filename
        # Use provided filename if available, else timestamp
        provided_name = data.get('filename')
        
        if provided_name:
            # Simple sanitization
            if not provided_name.endswith('.txt'):
                provided_name += '.txt'
            # Prevent directory traversal
            filename = memory_dir / Path(provided_name).name 
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = memory_dir / f"memory_{timestamp}.txt"

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            for msg in messages:
                sender = msg.get('sender', 'Unknown')
                text = msg.get('text', '')
                f.write(f"{sender}: {text}\n")
        logger.info("Conversation saved to %s", filename)
        await sio.emit('status', {'msg': 'Memory Saved Successfully'})

    except Exception as e:
        logger.exception("Error saving memory")
        await sio.emit('error', {'msg': f"Failed to save memory: {str(e)}"})

@sio.event
async def upload_memory(sid, data):
    logger.info("Received memory upload request")
    try:
        memory_text = data.get('memory', '')
        if not memory_text:
            logger.warning("No memory data provided")
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return

        if not audio_loop:
             logger.error("Audio loop is None; cannot load memory")
             await sio.emit('error', {'msg': "System not ready (Audio Loop inactive)"})
             return
        
        if not await ensure_audio_ready(sid):
             return

        # Send to model
        logger.debug("Sending memory context to model")
        context_msg = f"System Notification: The user has uploaded a long-term memory file. Please load the following context into your understanding. The format is a text log of previous conversations:\n\n{memory_text}"
        
        await audio_loop.session.send(input=context_msg, end_of_turn=True)
        logger.debug("Memory context sent successfully")
        await sio.emit('status', {'msg': 'Memory Loaded into Context'})

    except Exception as e:
        logger.exception("Error uploading memory")
        await sio.emit('error', {'msg': f"Failed to upload memory: {str(e)}"})

@sio.event
async def process_uploaded_file(sid, data):
    """Process a file selected in the frontend without exposing its local path."""
    try:
        filename = Path(str(data.get('filename', 'uploaded_file'))).name
        encoded_file = data.get('data', '')
        if not encoded_file:
            await sio.emit('file_processing_result', {'error': 'No file data provided.'}, room=sid)
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return

        file_bytes = base64.b64decode(encoded_file, validate=True)
        metadata = global_memory_manager.store_upload(
            filename,
            file_bytes,
            data.get('mime_type', 'application/octet-stream'),
            permanent=False,
        )
        uploaded_path = Path(metadata['path'])

        params = {
            'file_path': str(uploaded_path),
            'action': data.get('action', ''),
            'instruction': data.get('instruction', ''),
        }
        result = await asyncio.to_thread(friday.file_processor_module.file_processor, params)
        await sio.emit('file_processing_result', {
            'filename': filename,
            'result': result,
            'wallpaper_ready': metadata['mime_type'].startswith('image/'),
            'saved_path': str(uploaded_path),
        }, room=sid)
        if metadata['mime_type'].startswith('image/') and audio_loop and audio_loop.session:
            await audio_loop.session.send(
                input=(
                    f"System Notification: The user uploaded an image and it is temporarily available at "
                    f"{uploaded_path}. If the user asks to set the uploaded image as wallpaper, use "
                    f"desktop_control with action='wallpaper' and this exact path, after confirmation."
                ),
                end_of_turn=False,
            )
    except Exception as e:
        logger.exception("Error processing uploaded file")
        await sio.emit('file_processing_result', {
            'error': (
                f"I could not process '{data.get('filename', 'the file')}'. "
                f"The processor reported: {e}. Check that the required file-processing "
                "packages are installed and try again with a supported format."
            )
        }, room=sid)

@sio.event
async def upload_file_for_awareness(sid, data):
    """Store an uploaded file and give the active model enough context to ask what to do."""
    try:
        filename = Path(str(data.get('filename', 'uploaded_file'))).name
        encoded_file = data.get('data', '')
        if not encoded_file:
            await sio.emit('file_processing_result', {'error': 'No file data provided.'}, room=sid)
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return

        file_bytes = base64.b64decode(encoded_file, validate=True)
        mime_type = data.get('mime_type', 'application/octet-stream')
        metadata = global_memory_manager.store_upload(filename, file_bytes, mime_type, permanent=False)
        saved_path = Path(metadata['path'])
        preview = ''
        if mime_type.startswith('text/') or Path(filename).suffix.lower() in {'.txt', '.md', '.json', '.csv', '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css'}:
            preview = file_bytes.decode('utf-8', errors='ignore')[:12000]

        if audio_loop:
            audio_loop.last_uploaded_file = str(saved_path)
            if audio_loop.session:
                if mime_type.startswith('image/'):
                    await audio_loop.session.send(
                        input={'mime_type': mime_type, 'data': encoded_file},
                        end_of_turn=False,
                    )
                awareness = (
                    f"System Notification: The user uploaded a file named '{filename}' ({mime_type}, "
                    f"{len(file_bytes)} bytes). It is temporarily available at {saved_path}. "
                    "You are now aware of this file. Ask the user what they would like you to do "
                    "with it, such as summarize, extract text, analyze, edit, or set it as wallpaper "
                    "if it is an image. Do not perform an action until the user specifies one and "
                    "the normal confirmation is completed."
                )
                if preview:
                    awareness += f"\n\nFile content preview:\n{preview}"
                await audio_loop.session.send(input=awareness, end_of_turn=True)

        await sio.emit('file_processing_result', {
            'filename': filename,
            'result': f"Friday is aware of '{filename}' and is ready for your instructions.",
            'file_awareness': True,
            'saved_path': str(saved_path),
        }, room=sid)
    except Exception as e:
        logger.exception("Error uploading file for awareness")
        await sio.emit('file_processing_result', {'error': f'File upload failed: {e}'}, room=sid)
@sio.event
async def discover_kasa(sid):
    logger.info("Received discover_kasa request")
    try:
        devices = await kasa_agent.discover_devices()
        await sio.emit('kasa_devices', devices)
        await sio.emit('status', {'msg': f"Found {len(devices)} Kasa devices"})
        
        # Save to settings
        # devices is a list of full device info dicts. minimizing for storage.
        saved_devices = []
        for d in devices:
            saved_devices.append({
                "ip": d["ip"],
                "alias": d["alias"],
                "model": d["model"]
            })
        
        # Merge with existing to preserve any manual overrides? 
        # For now, just overwrite with latest scan result + previously known if we want to be fancy,
        # but user asked for "Any new devices that are scanned are added there".
        # A simple full persistence of current state is safest.
        SETTINGS["kasa_devices"] = saved_devices
        save_settings()
        logger.info("Saved %s Kasa devices to settings", len(saved_devices))
        
    except Exception as e:
        logger.exception("Error discovering Kasa devices")
        await sio.emit('error', {'msg': f"Kasa Discovery Failed: {str(e)}"})

@sio.event
async def iterate_cad(sid, data):
    # data: { prompt: "make it bigger" }
    prompt = data.get('prompt')
    logger.info("Received iterate_cad request: %r", prompt)
    
    if not audio_loop or not audio_loop.cad_agent:
        await sio.emit('error', {'msg': "CAD Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return

    try:
        # Notify user work has started
        await sio.emit('status', {'msg': 'Iterating design...'})
        await sio.emit('cad_status', {'status': 'generating'})
        
        # Call the agent with project path
        cad_output_dir = str(audio_loop.project_manager.get_current_project_path() / "cad")
        result = await audio_loop.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
        
        if result:
            info = f"{len(result.get('data', ''))} bytes (STL)"
            logger.debug("Sending updated CAD data: %s", info)
            await sio.emit('cad_data', result)
            # Save to Project
            if 'file_path' in result:
                saved_path = audio_loop.project_manager.save_cad_artifact(result['file_path'], prompt)
                if saved_path:
                    logger.info("Saved iterated CAD to %s", saved_path)

            await sio.emit('status', {'msg': 'Design updated'})
        else:
            await sio.emit('error', {'msg': 'Failed to update design'})
            
    except Exception as e:
        logger.exception("Error iterating CAD")
        await sio.emit('error', {'msg': f"Iteration Error: {str(e)}"})

@sio.event
async def generate_cad(sid, data):
    # data: { prompt: "make a cube" }
    prompt = data.get('prompt')
    logger.info("Received generate_cad request: %r", prompt)
    
    if not audio_loop or not audio_loop.cad_agent:
        await sio.emit('error', {'msg': "CAD Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return

    try:
        await sio.emit('status', {'msg': 'Generating new design...'})
        await sio.emit('cad_status', {'status': 'generating'})
        
        # Use generate_prototype based on prompt with project path
        cad_output_dir = str(audio_loop.project_manager.get_current_project_path() / "cad")
        result = await audio_loop.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        
        if result:
            info = f"{len(result.get('data', ''))} bytes (STL)"
            logger.debug("Sending newly generated CAD data: %s", info)
            await sio.emit('cad_data', result)


            # Save to Project
            if 'file_path' in result:
                saved_path = audio_loop.project_manager.save_cad_artifact(result['file_path'], prompt)
                if saved_path:
                    logger.info("Saved generated CAD to %s", saved_path)

            await sio.emit('status', {'msg': 'Design generated'})
        else:
            await sio.emit('error', {'msg': 'Failed to generate design'})
            
    except Exception as e:
        logger.exception("Error generating CAD")
        await sio.emit('error', {'msg': f"Generation Error: {str(e)}"})

@sio.event
async def prompt_web_agent(sid, data):
    # data: { prompt: "find xyz" }
    prompt = data.get('prompt')
    logger.info("Received web agent prompt: %r", prompt)
    
    if not audio_loop or not audio_loop.web_agent:
        await sio.emit('error', {'msg': "Web Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return

    try:
        await sio.emit('status', {'msg': 'Web Agent running...'})
        
        # We assume web_agent has a run method or similar.
        # This might block the loop if not strictly async or offloaded.
        # Ideally web_agent.run is async.
        # And it should emit 'browser_snap' and logs automatically via hooks if setup.
        
        # We might need to launch this as a task if it's long running?
        # asyncio.create_task(audio_loop.web_agent.run(prompt))
        # But we want to catch errors here.
        
        # Based on typical agent design, run() is the entry point.
        await audio_loop.web_agent.run(prompt)
        
        await sio.emit('status', {'msg': 'Web Agent finished'})
        
    except Exception as e:
        logger.exception("Error running web agent")
        await sio.emit('error', {'msg': f"Web Agent Error: {str(e)}"})

@sio.event
async def discover_printers(sid):
    logger.info("Received discover_printers request")
    
    # If audio_loop isn't ready yet, return saved printers from settings
    if not audio_loop or not audio_loop.printer_agent:
        saved_printers = SETTINGS.get("printers", [])
        if saved_printers:
            # Convert saved printers to the expected format
            printer_list = []
            for p in saved_printers:
                printer_list.append({
                    "name": p.get("name", p["host"]),
                    "host": p["host"],
                    "port": p.get("port", 80),
                    "printer_type": p.get("type", "unknown"),
                    "camera_url": p.get("camera_url")
                })
            logger.info("Returning %s saved printers; audio loop not ready", len(printer_list))
            await sio.emit('printer_list', printer_list)
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return
        else:
            await sio.emit('printer_list', [])
            await sio.emit('status', {'msg': "Connect to F.R.I.D.A.Y to enable printer discovery"})
            if audio_loop:
                audio_loop.cancel_pending_confirmations()
            return
        
    try:
        printers = await audio_loop.printer_agent.discover_printers()
        await sio.emit('printer_list', printers)
        await sio.emit('status', {'msg': f"Found {len(printers)} printers"})
    except Exception as e:
        logger.exception("Error discovering printers")
        await sio.emit('error', {'msg': f"Printer Discovery Failed: {str(e)}"})

@sio.event
async def add_printer(sid, data):
    # data: { host: "192.168.1.50", name: "My Printer", type: "moonraker" }
    raw_host = data.get('host')
    name = data.get('name') or raw_host
    ptype = data.get('type', "moonraker")
    
    # Parse port if present
    if ":" in raw_host:
        host, port_str = raw_host.split(":")
        port = int(port_str)
    else:
        host = raw_host
        port = 80
    
    logger.info("Received add_printer request: %s:%s (%s)", host, port, ptype)
    
    if not audio_loop or not audio_loop.printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return
        
    try:
        # Add manually
        camera_url = data.get('camera_url')
        printer = audio_loop.printer_agent.add_printer_manually(name, host, port=port, printer_type=ptype, camera_url=camera_url)
        
        # Save to settings
        new_printer_config = {
            "name": name,
            "host": host,
            "port": port,
            "type": ptype,
            "camera_url": camera_url
        }
        
        # Check if already exists to avoid duplicates
        exists = False
        for p in SETTINGS.get("printers", []):
            if p["host"] == host and p["port"] == port:
                exists = True
                break
        
        if not exists:
            if "printers" not in SETTINGS:
                SETTINGS["printers"] = []
            SETTINGS["printers"].append(new_printer_config)
            save_settings()
            logger.info("Saved printer %s to settings", name)
        
        # Probe to confirm/correct type
        logger.debug("Probing %s to confirm printer type", host)
        # Try port 7125 (Moonraker) and 4408 (Fluidd/K1) 
        ports_to_try = [80, 7125, 4408]
        
        actual_type = "unknown"
        for port in ports_to_try:
             found_type = await audio_loop.printer_agent._probe_printer_type(host, port)
             if found_type.value != "unknown":
                 actual_type = found_type
                 # Update port if different
                 if port != 80:
                     printer.port = port
                 break
        
        if actual_type != "unknown" and actual_type != printer.printer_type:
             printer.printer_type = actual_type
             logger.info("Corrected printer type to %s on port %s", actual_type.value, printer.port)
             
        # Refresh list for everyone
        printers = [p.to_dict() for p in audio_loop.printer_agent.printers.values()]
        await sio.emit('printer_list', printers)
        await sio.emit('status', {'msg': f"Added printer: {name}"})
        
    except Exception as e:
        logger.exception("Error adding printer")
        await sio.emit('error', {'msg': f"Failed to add printer: {str(e)}"})

@sio.event
async def print_stl(sid, data):
    logger.info("Received print_stl request: %s", data)
    # data: { stl_path: "path/to.stl" | "current", printer: "name_or_ip", profile: "optional" }
    
    if not audio_loop or not audio_loop.printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return
        
    try:
        stl_path = data.get('stl_path', 'current')
        printer_name = data.get('printer')
        profile = data.get('profile')
        
        if not printer_name:
             await sio.emit('error', {'msg': "No printer specified"})
             if audio_loop:
                 audio_loop.cancel_pending_confirmations()
             return
             
        await sio.emit('status', {'msg': f"Preparing print for {printer_name}..."})
        
        # Get current project path for resolution
        current_project_path = None
        if audio_loop and audio_loop.project_manager:
            current_project_path = str(audio_loop.project_manager.get_current_project_path())
            logger.debug("Using project path: %s", current_project_path)

        # Resolve STL path before slicing so we can preview it
        resolved_stl = audio_loop.printer_agent._resolve_file_path(stl_path, current_project_path)
        
        if resolved_stl and os.path.exists(resolved_stl):
            # Open the STL in the CAD module for preview
            try:
                import base64
                with open(resolved_stl, 'rb') as f:
                    stl_data = f.read()
                stl_b64 = base64.b64encode(stl_data).decode('utf-8')
                stl_filename = os.path.basename(resolved_stl)
                
                logger.info("Opening STL in CAD module: %s", stl_filename)
                await sio.emit('cad_data', {
                    'format': 'stl',
                    'data': stl_b64,
                    'filename': stl_filename
                })
            except Exception as e:
                logger.warning("Could not preview STL: %s", e)
        
        # Progress Callback
        async def on_slicing_progress(percent, message):
            await sio.emit('slicing_progress', {
                'printer': printer_name,
                'percent': percent,
                'message': message
            })
            if percent < 100:
                 await sio.emit('status', {'msg': f"Slicing: {percent}%"})

        result = await audio_loop.printer_agent.print_stl(
            stl_path, 
            printer_name, 
            profile,
            progress_callback=on_slicing_progress,
            root_path=current_project_path
        )
        
        await sio.emit('print_result', result)
        await sio.emit('status', {'msg': f"Print Job: {result.get('status', 'unknown')}"})
        
    except Exception as e:
        logger.exception("Error printing STL")
        await sio.emit('error', {'msg': f"Print Failed: {str(e)}"})

@sio.event
async def get_slicer_profiles(sid):
    """Get available OrcaSlicer profiles for manual selection."""
    logger.info("Received get_slicer_profiles request")
    if not audio_loop or not audio_loop.printer_agent:
        await sio.emit('error', {'msg': "Printer Agent not available"})
        if audio_loop:
            audio_loop.cancel_pending_confirmations()
        return
    
    try:
        profiles = audio_loop.printer_agent.get_available_profiles()
        await sio.emit('slicer_profiles', profiles)
    except Exception as e:
        logger.exception("Error getting slicer profiles")
        await sio.emit('error', {'msg': f"Failed to get profiles: {str(e)}"})

@sio.event
async def control_kasa(sid, data):
    # data: { ip, action: "on"|"off"|"brightness"|"color", value: ... }
    ip = data.get('ip')
    action = data.get('action')
    logger.info("Kasa control: %s -> %s", ip, action)
    
    try:
        success = False
        if action == "on":
            success = await kasa_agent.turn_on(ip)
        elif action == "off":
            success = await kasa_agent.turn_off(ip)
        elif action == "brightness":
            val = data.get('value')
            success = await kasa_agent.set_brightness(ip, val)
        elif action == "color":
            # value is {h, s, v} - convert to tuple for set_color
            h = data.get('value', {}).get('h', 0)
            s = data.get('value', {}).get('s', 100)
            v = data.get('value', {}).get('v', 100)
            success = await kasa_agent.set_color(ip, (h, s, v))
        
        if success:
            await sio.emit('kasa_update', {
                'ip': ip,
                'is_on': True if action == "on" else (False if action == "off" else None),
                'brightness': data.get('value') if action == "brightness" else None,
            })
 
        else:
             await sio.emit('error', {'msg': f"Failed to control device {ip}"})

    except Exception as e:
         logger.exception("Error controlling Kasa device")
         await sio.emit('error', {'msg': f"Kasa Control Error: {str(e)}"})

@sio.event
async def get_settings(sid):
    await sio.emit('settings', SETTINGS)
    await sio.emit('provider_routing', SETTINGS.get('provider_routing', {}), room=sid)
    await sio.emit('google_account_status', google_account.status(), room=sid)
    await sio.emit('openclaw_status', friday.openclaw_bridge.status(), room=sid)

@sio.event
async def get_openclaw_status(sid):
    """Return current external OpenClaw Gateway health for Friday's control window."""
    try:
        payload = friday.openclaw_bridge.status() if friday.openclaw_bridge else {'reachable': False}
    except Exception as exc:
        payload = {'reachable': False, 'error': str(exc)}
    await sio.emit('openclaw_status', payload, room=sid)

@sio.event
async def get_openclaw_capabilities(sid):
    """Return the Friday tools and agents exposed to OpenClaw planning."""
    try:
        await sio.emit('openclaw_capabilities', friday.openclaw_bridge.capabilities(), room=sid)
    except Exception as exc:
        await sio.emit('openclaw_capabilities', {'friday_tools': [], 'error': str(exc)}, room=sid)
    try:
        claude = ClaudeProvider()
        await sio.emit('text_provider_status', {
            'provider': 'claude' if claude.available and os.getenv('FRIDAY_TEXT_PROVIDER', 'auto').lower() != 'gemini' else 'gemini',
            'claude_available': claude.available,
            'model': claude.model if claude.available else None,
        }, room=sid)
    except Exception as exc:
        await sio.emit('text_provider_status', {'provider': 'gemini', 'claude_available': False, 'error': str(exc)}, room=sid)

@sio.event
async def get_agent_console(sid):
    """Return agent lifecycle, schedules, and execution history for the OpenClaw window."""
    runtime = audio_loop
    try:
        executions = agent_dispatcher_module.ledger.list(25)
    except Exception as exc:
        logger.exception("Error listing execution ledger")
        executions = []
    await sio.emit('agent_console', {
        'plugins': runtime.plugin_manager.list_plugins() if runtime else [],
        'schedules': runtime.agent_scheduler.list() if runtime else [],
        'executions': executions,
    }, room=sid)

@sio.event
async def get_autonomy_status(sid):
    if not audio_loop:
        await sio.emit('autonomy_status', {'proposals': [], 'security_findings': [], 'phases': {}, 'error': 'Friday runtime is not ready'}, room=sid)
        return
    try:
        await sio.emit('autonomy_status', audio_loop.autonomy_pipeline.run_cycle(), room=sid)
    except Exception as exc:
        logger.exception("Error running autonomy cycle")
        await sio.emit('autonomy_status', {'proposals': [], 'security_findings': [], 'phases': {}, 'error': str(exc)}, room=sid)

@sio.event
async def approve_autonomy_proposal(sid, data):
    try:
        if not audio_loop:
            raise RuntimeError('Friday runtime is not ready')
        result = audio_loop.autonomy_pipeline.approve((data or {}).get('proposal_id', ''))
    except Exception as exc:
        result = {'error': str(exc)}
    await sio.emit('autonomy_approval_result', result, room=sid)
    await get_autonomy_status(sid)

@sio.event
async def resolve_security_finding(sid, data):
    """Record a human review decision for a security finding (risky import/call).

    Accepting a finding clears it from the approval queue so the autonomy
    pipeline's security_review phase can complete and proposals can deploy.
    """
    try:
        if not audio_loop:
            raise RuntimeError('Friday runtime is not ready')
        payload = data or {}
        result = audio_loop.autonomy_pipeline.resolve_security(
            payload.get('finding_path', ''), payload.get('finding_value', '')
        )
    except Exception as exc:
        result = {'error': str(exc)}
    await sio.emit('autonomy_approval_result', result, room=sid)
    await get_autonomy_status(sid)

@sio.event
async def agent_console_action(sid, data):
    payload = data or {}
    action = str(payload.get('action', '')).lower()
    try:
        if action == 'test':
            result = friday.agent_builder.test(payload['name'])
        elif action == 'enable' or action == 'disable':
            result = friday.plugin_manager.set_enabled('agent', payload['name'], action == 'enable')
        elif action == 'rollback':
            result = friday.plugin_manager.rollback(payload['snapshot'])
        elif action == 'deploy':
            result = friday.openclaw_bridge.delegate(payload['name'], payload.get('goal', 'Run agent task.'), payload.get('repo_path', '.'))
        elif action == 'run_now':
            result = friday.agent_scheduler.run_now(payload['schedule_id'])
        elif action == 'schedule':
            result = friday.agent_scheduler.schedule(payload['name'], payload.get('goal', 'Run scheduled agent task.'), int(payload.get('interval_seconds', 900)), payload.get('repo_path', '.'), int(payload.get('max_retries', 3)))
        elif action == 'cancel_schedule':
            result = {'cancelled': friday.agent_scheduler.cancel(payload['schedule_id'])}
        elif action == 'enable_schedule' or action == 'disable_schedule':
            result = {'updated': friday.agent_scheduler.set_enabled(payload['schedule_id'], action == 'enable_schedule')}
        else:
            result = {'error': f'Unknown agent console action: {action}'}
    except Exception as exc:
        result = {'error': str(exc)}
    await sio.emit('agent_console_action_result', result, room=sid)
    await get_agent_console(sid)

@sio.event
async def connect_google_account(sid):
    """Open Google consent in the system browser and persist the local refresh token."""
    try:
        await sio.emit('google_account_status', {'connecting': True, **google_account.status()}, room=sid)
        account_status = await asyncio.to_thread(google_account.connect)
        if audio_loop:
            audio_loop.google_account = google_account
        await sio.emit('google_account_status', account_status, room=sid)
    except Exception as exc:
        logger.exception("Google connection failed")
        await sio.emit('google_account_status', {'connected': False, 'error': str(exc)}, room=sid)

@sio.event
async def disconnect_google_account(sid):
    """Remove Friday's local Google refresh token from this computer."""
    try:
        account_status = google_account.disconnect()
        if audio_loop:
            audio_loop.google_account = google_account
        await sio.emit('google_account_status', account_status, room=sid)
    except Exception as exc:
        await sio.emit('google_account_status', {'connected': False, 'error': str(exc)}, room=sid)

@sio.event
async def update_settings(sid, data):
    # Generic update
    logger.info("Updating settings: %s", data)
    
    # Handle specific keys if needed
    if "tool_permissions" in data:
        SETTINGS["tool_permissions"].update(data["tool_permissions"])
        if audio_loop:
            audio_loop.update_permissions(SETTINGS["tool_permissions"])

    if "provider_routing" in data and isinstance(data["provider_routing"], dict):
        allowed = {
            "voice_vision": {"Gemini Live"},
            "text_reasoning": {"Gemini", "OpenClaw"},
            "coding": {"Gemini", "OpenClaw"},
            "documents": {"Gemini", "OpenClaw"},
            "background_agents": {"OpenClaw"},
        }
        routing = SETTINGS.setdefault("provider_routing", {})
        for key, value in data["provider_routing"].items():
            if key in allowed and value in allowed[key]:
                routing[key] = value
            
    if "face_auth_enabled" in data:
        SETTINGS["face_auth_enabled"] = data["face_auth_enabled"]
        # If turned OFF, maybe emit auth status true?
        if not data["face_auth_enabled"]:
             await sio.emit('auth_status', {'authenticated': True})
             # Stop auth loop if running?
             if authenticator:
                 authenticator.stop() 

    if "camera_flipped" in data:
        SETTINGS["camera_flipped"] = data["camera_flipped"]
        logger.info("Camera flip set to: %s", data["camera_flipped"])

    if "system_alerts_enabled" in data:
        SETTINGS["system_alerts_enabled"] = bool(data["system_alerts_enabled"])
        if audio_loop:
            audio_loop.system_monitor.configure(alerts_enabled=SETTINGS["system_alerts_enabled"])

    if "initiative" in data and isinstance(data["initiative"], dict):
        try:
            from actions import initiative as _initiative_mod
            SETTINGS["initiative"] = _initiative_mod.write_settings(data["initiative"]).get("config", SETTINGS.get("initiative", {}))
        except Exception as exc:
            logger.exception("Initiative settings update failed")

    if "quiet_mode" in data:
        SETTINGS["quiet_mode"] = bool(data["quiet_mode"])

    if "interrupt_preferences" in data and isinstance(data["interrupt_preferences"], dict):
        SETTINGS["interrupt_preferences"].update(data["interrupt_preferences"])

    if "current_mode" in data and data["current_mode"] in {"active", "focus", "away"}:
        SETTINGS["current_mode"] = data["current_mode"]

    if "muted_alert_categories" in data and isinstance(data["muted_alert_categories"], list):
        SETTINGS["muted_alert_categories"] = data["muted_alert_categories"]
        if audio_loop:
            audio_loop.system_monitor.configure(
                muted_categories=set(SETTINGS["muted_alert_categories"])
            )

    save_settings()
    # Broadcast new full settings
    await sio.emit('settings', SETTINGS)


# Deprecated/Mapped for compatibility if frontend still uses specific events
@sio.event
async def get_tool_permissions(sid):
    await sio.emit('tool_permissions', SETTINGS["tool_permissions"])

@sio.event
async def update_tool_permissions(sid, data):
    logger.info("Updating permissions through legacy event: %s", data)
    SETTINGS["tool_permissions"].update(data)
    save_settings()
    
    if audio_loop:
        audio_loop.update_permissions(SETTINGS["tool_permissions"])
    # Broadcast update to all
    await sio.emit('tool_permissions', SETTINGS["tool_permissions"])

# New window component socket events

@sio.event
async def get_system_monitor(sid):
    """Get current system metrics for SystemMonitorWindow."""
    from actions.system_monitor import get_system_status
    try:
        data = get_system_status()
        await sio.emit('system_monitor_data', data)
        # Also emit to dashboard for real-time updates
        await sio.emit('dashboard_system_update', data)
    except Exception as e:
        logger.exception("Error getting system monitor data")

@sio.event
async def get_weather(sid, data):
    """Get weather data for WeatherWindow."""
    from actions.weather_report import weather_action
    try:
        city = data.get('city')
        result = weather_action({'city': city})
        # Parse result and emit structured data
        await sio.emit('weather_data', {
            'city': city,
            'temp': 20,  # Placeholder - would need actual weather API
            'condition': 'Clear',
            'humidity': 50,
            'wind': 10,
            'forecast': []
        })
    except Exception as e:
        logger.exception("Error getting weather")

@sio.event
async def get_reminders(sid):
    """Get reminders list for ReminderWindow."""
    try:
        # Placeholder - would need actual reminder storage
        await sio.emit('reminders_list', [])
    except Exception as e:
        logger.exception("Error getting reminders")

@sio.event
async def add_reminder(sid, data):
    """Add a new reminder."""
    from actions.reminder import reminder
    try:
        result = reminder(data)
        await sio.emit('status', {'msg': result})
    except Exception as e:
        logger.exception("Error adding reminder")

@sio.event
async def delete_reminder(sid, data):
    """Delete a reminder."""
    try:
        # Placeholder - would need actual deletion logic
        await sio.emit('status', {'msg': 'Reminder deleted'})
    except Exception as e:
        logger.exception("Error deleting reminder")

@sio.event
async def search_flights(sid, data):
    """Search flights for FlightWindow."""
    from actions.flight_finder import flight_finder
    try:
        result = flight_finder(data)
        await sio.emit('flight_results', [])
    except Exception as e:
        logger.exception("Error searching flights")

@sio.event
async def read_directory(sid, data):
    """Read directory contents for FileManagerWindow."""
    try:
        path = data.get('path', '~')
        # Placeholder - would need actual directory reading
        await sio.emit('directory_contents', {'path': path, 'items': []})
    except Exception as e:
        logger.exception("Error reading directory")

@sio.event
async def search_files(sid, data):
    """Search files for FileManagerWindow."""
    try:
        # Placeholder - would need actual file search
        await sio.emit('directory_contents', {'path': data.get('path'), 'items': []})
    except Exception as e:
        logger.exception("Error searching files")

@sio.event
async def start_recording(sid):
    """Start recording computer control actions."""
    try:
        await sio.emit('recording_status', {'recording': True})
    except Exception as e:
        logger.exception("Error starting recording")

@sio.event
async def stop_recording(sid):
    """Stop recording computer control actions."""
    try:
        await sio.emit('recording_status', {'recording': False})
    except Exception as e:
        logger.exception("Error stopping recording")

@sio.event
async def play_recording(sid):
    """Play recorded computer control actions."""
    try:
        await sio.emit('status', {'msg': 'Playing recording'})
    except Exception as e:
        logger.exception("Error playing recording")

@sio.event
async def clear_recording(sid):
    """Clear recorded actions."""
    try:
        await sio.emit('status', {'msg': 'Recording cleared'})
    except Exception as e:
        logger.exception("Error clearing recording")

@sio.event
async def web_search(sid, data):
    """Perform web search for SearchWindow."""
    from actions.web_search import web_search_action
    try:
        query = data.get('query')
        result = web_search_action({'query': query})
        await sio.emit('search_results', {'results': []})
    except Exception as e:
        logger.exception("Error performing web search")

@sio.event
async def get_search_history(sid):
    """Get search history for SearchWindow."""
    try:
        await sio.emit('search_history', [])
    except Exception as e:
        logger.exception("Error getting search history")

@sio.event
async def youtube_search(sid, data):
    """Search YouTube for YouTubeWindow."""
    from actions.youtube_video import youtube_action
    try:
        query = data.get('query')
        result = youtube_action({'query': query})
        await sio.emit('youtube_results', [])
    except Exception as e:
        logger.exception("Error searching YouTube")

@sio.event
async def get_playlist(sid):
    """Get YouTube playlist."""
    try:
        await sio.emit('playlist_updated', [])
    except Exception as e:
        logger.exception("Error getting playlist")

@sio.event
async def play_youtube(sid, data):
    """Play YouTube video."""
    try:
        await sio.emit('status', {'msg': 'Playing video'})
    except Exception as e:
        logger.exception("Error playing video")

@sio.event
async def add_to_playlist(sid, data):
    """Add video to playlist."""
    try:
        await sio.emit('status', {'msg': 'Added to playlist'})
    except Exception as e:
        logger.exception("Error adding to playlist")

@sio.event
async def remove_from_playlist(sid, data):
    """Remove video from playlist."""
    try:
        await sio.emit('status', {'msg': 'Removed from playlist'})
    except Exception as e:
        logger.exception("Error removing from playlist")

@sio.event
async def run_code(sid, data):
    """Run code for CodeWindow."""
    from actions.code_helper import code_helper_action
    try:
        code = data.get('code')
        language = data.get('language')
        result = code_helper_action({'code': code, 'language': language})
        await sio.emit('code_output', result)
    except Exception as e:
        logger.exception("Error running code")

@sio.event
async def save_code(sid, data):
    """Save code for CodeWindow."""
    try:
        await sio.emit('status', {'msg': 'Code saved'})
    except Exception as e:
        logger.exception("Error saving code")

@sio.event
async def get_code_snippets(sid):
    """Get code snippets for CodeWindow."""
    try:
        await sio.emit('code_snippets', [])
    except Exception as e:
        logger.exception("Error getting code snippets")

@sio.event
async def get_process_list(sid):
    """Get process list for ProcessWindow."""
    try:
        import psutil
        processes = []
        for process in psutil.process_iter(['pid', 'name', 'username', 'memory_percent']):
            try:
                processes.append(process.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        await sio.emit('process_list', sorted(processes, key=lambda item: item.get('memory_percent') or 0, reverse=True)[:100], room=sid)
    except Exception as e:
        logger.exception("Error getting process list")

@sio.event
async def kill_process(sid, data):
    """Kill a process for ProcessWindow."""
    try:
        pid = data.get('pid')
        await sio.emit('status', {'msg': f'Process {pid} killed'})
    except Exception as e:
        logger.exception("Error killing process")

@sio.event
async def get_desktops(sid):
    """Get desktop list for DesktopWindow."""
    try:
        await sio.emit('desktop_list', [])
    except Exception as e:
        logger.exception("Error getting desktops")

@sio.event
async def switch_desktop(sid, data):
    """Switch to a different desktop."""
    try:
        desktop = data.get('desktop')
        await sio.emit('status', {'msg': f'Switched to desktop {desktop}'})
    except Exception as e:
        logger.exception("Error switching desktop")

@sio.event
async def add_desktop(sid):
    """Add a new virtual desktop."""
    try:
        await sio.emit('status', {'msg': 'Desktop added'})
    except Exception as e:
        logger.exception("Error adding desktop")

@sio.event
async def set_wallpaper(sid):
    """Set desktop wallpaper."""
    try:
        await sio.emit('status', {'msg': 'Wallpaper set'})
    except Exception as e:
        logger.exception("Error setting wallpaper")

@sio.event
async def send_message(sid, data):
    """Send a message for MessageWindow."""
    from actions.send_message import send_message as send_message_action
    try:
        platform = data.get('platform', 'whatsapp')
        message = data.get('message', '')
        receiver = data.get('receiver', '')

        if not receiver:
            matches = [c for c in contacts_manager.list_contacts() if platform in c.get('channels', {})]
            if len(matches) == 1:
                receiver = matches[0]['channels'][platform]
            elif not matches:
                await sio.emit('status', {'msg': f"No saved contact for {platform}. Add one in Contacts first."}, room=sid)
                if audio_loop:
                    audio_loop.cancel_pending_confirmations()
                return
            else:
                await sio.emit('status', {'msg': f"Multiple {platform} contacts found. Please specify a recipient."}, room=sid)
                if audio_loop:
                    audio_loop.cancel_pending_confirmations()
                return

        result = send_message_action({'receiver': receiver, 'message_text': message, 'platform': platform})
        await sio.emit('status', {'msg': result}, room=sid)
    except Exception as e:
        logger.exception("Error sending message")
        await sio.emit('status', {'msg': f"Error sending message: {e}"}, room=sid)

@sio.event
async def get_game_library(sid):
    """Get game library for GameWindow."""
    from actions.game_updater import game_updater_action
    try:
        result = game_updater_action({'action': 'list'})
        await sio.emit('game_library', [])
    except Exception as e:
        logger.exception("Error getting game library")

@sio.event
async def check_game_updates(sid):
    """Check for game updates for GameWindow."""
    try:
        await sio.emit('game_updates', [])
    except Exception as e:
        logger.exception("Error checking game updates")

@sio.event
async def launch_game(sid, data):
    """Launch a game for GameWindow."""
    try:
        game_id = data.get('gameId')
        await sio.emit('status', {'msg': 'Game launched'})
    except Exception as e:
        logger.exception("Error launching game")

@sio.event
async def update_game(sid, data):
    """Update a game for GameWindow."""
    try:
        game_id = data.get('gameId')
        await sio.emit('status', {'msg': 'Game updating'})
    except Exception as e:
        logger.exception("Error updating game")

# Dashboard event handlers
@sio.event
async def get_dashboard_data(sid, data=None):
    """Get comprehensive dashboard data."""
    try:
        dashboard_data = {
            'active_tasks': get_active_tasks(),
            'pending_approvals': get_pending_approvals(),
            'memory_summary': build_memory_summary(),
            'proactive_suggestions': build_proactive_suggestions(),
            'routine_queue': list_routine_queue(),
            'quiet_mode': get_quiet_mode(),
            'interrupt_preferences': get_interrupt_preferences(),
            'current_mode': get_current_mode()
        }
        await sio.emit('dashboard_data', dashboard_data)
    except Exception as e:
        logger.exception("Error getting dashboard data")

@sio.event
async def task_action(sid, data):
    """Handle task actions (pause, cancel, resume)."""
    payload = data or {}
    task_id = payload.get('task_id')
    action = payload.get('action')
    try:
        if audio_loop:
            if action == 'complete':
                task = audio_loop.task_manager.complete(task_id)
                await audio_loop.notifications.notify('tasks', 'Task completed', task.get('title', 'Task completed'))
                await sio.emit('task_cards', audio_loop.task_manager.list('open'))
            elif action == 'cancel':
                audio_loop.cancel_current_action()
            elif action == 'pause':
                pass
            elif action == 'resume':
                pass
        await sio.emit('task_action_response', {'task_id': task_id, 'action': action, 'success': True})
    except Exception as e:
        logger.exception("Error handling task action")
        await sio.emit('task_action_response', {'task_id': task_id, 'action': action, 'success': False})

@sio.event
async def get_task_cards(sid, data=None):
    """Return open tasks for the HUD task-card strip."""
    try:
        await sio.emit('task_cards', audio_loop.task_manager.list('open') if audio_loop else [])
    except Exception as e:
        logger.exception("Error getting task cards")

@sio.event
async def approval_response(sid, data):
    """Handle approval responses from dashboard."""
    payload = data or {}
    approval_id = payload.get('approval_id')
    approved = payload.get('approved')
    try:
        if audio_loop:
            audio_loop.resolve_tool_confirmation(approval_id, approved)
        await sio.emit('approval_response_ack', {'approval_id': approval_id, 'approved': approved})
    except Exception as e:
        logger.exception("Error handling approval response")

@sio.event
async def set_quiet_mode(sid, data):
    """Set quiet mode state."""
    try:
        payload = data or {}
        enabled = bool(payload.get('enabled', False))
        settings = load_settings() or {}
        settings['quiet_mode'] = enabled
        save_settings(settings)
        await sio.emit('quiet_mode_set', {'enabled': enabled})
    except Exception as e:
        logger.exception("Error setting quiet mode")

@sio.event
async def set_interrupt_preferences(sid, data):
    """Set interrupt preferences."""
    try:
        payload = data or {}
        settings = load_settings() or {}
        if 'interrupt_preferences' not in settings:
            settings['interrupt_preferences'] = {}
        settings['interrupt_preferences'].update(payload)
        save_settings(settings)
        await sio.emit('interrupt_preferences_set', payload)
    except Exception as e:
        logger.exception("Error setting interrupt preferences")

@sio.event
async def get_routine_queue(sid):
    """Return the routines currently available to the desktop client."""
    await sio.emit('routine_queue_update', {'routines': list_routine_queue()}, room=sid)

@sio.event
async def get_memory_summary(sid):
    """Return memory statistics to the dedicated memory window."""
    await sio.emit('memory_summary_update', build_memory_summary(), room=sid)

@sio.event
async def compact_memory(sid):
    """Compact long-term memory using the active Friday runtime."""
    try:
        if audio_loop and hasattr(audio_loop, 'compact_memory'):
            await audio_loop.compact_memory()
        elif global_memory_manager and hasattr(global_memory_manager, 'compact_low_value_facts'):
            global_memory_manager.compact_low_value_facts()
        await sio.emit('memory_compacted', {'success': True, 'summary': build_memory_summary()}, room=sid)
    except Exception as e:
        logger.exception("Error compacting memory")
        await sio.emit('memory_compacted', {'success': False, 'error': str(e)}, room=sid)

@sio.event
async def get_proactive_suggestions(sid):
    """Return live proactive recommendations to the dedicated window."""
    await sio.emit('proactive_suggestions', {'suggestions': build_proactive_suggestions()}, room=sid)

@sio.event
async def suggestion_action(sid, data):
    """Record a user's response to a proactive suggestion."""
    payload = data or {}
    suggestion_id = payload.get('id')
    action = payload.get('action')
    try:
        if action not in {'accept', 'remind_later'}:
            raise ValueError('Unsupported suggestion action')
        await sio.emit('suggestion_action_result', {'id': suggestion_id, 'action': action, 'success': True}, room=sid)
    except Exception as e:
        logger.exception("Error handling suggestion action")
        await sio.emit('suggestion_action_result', {'id': suggestion_id, 'success': False, 'error': str(e)}, room=sid)

@sio.event
async def run_routine(sid, data):
    """Execute a named routine through the active Friday runtime."""
    payload = data or {}
    name = payload.get('name')
    try:
        if not audio_loop or not hasattr(audio_loop, 'routine_manager'):
            raise RuntimeError('Friday runtime is not ready')
        result = audio_loop.routine_manager.execute_runtime(name, payload.get('payload'), runtime=audio_loop)
        await sio.emit('routine_execution_result', {'name': name, 'success': True, 'result': result}, room=sid)
    except Exception as e:
        logger.exception("Error running routine")
        await sio.emit('routine_execution_result', {'name': name, 'success': False, 'error': str(e)}, room=sid)

# Helper functions for dashboard data
def get_active_tasks():
    """Get list of active tasks."""
    if audio_loop and hasattr(audio_loop, '_background_tasks'):
        tasks = []
        for task in audio_loop._background_tasks:
            if task.done():
                continue
            coro = getattr(task, '_coro', None)
            coro_name = getattr(coro, '__name__', 'Unknown Task') if hasattr(coro, '__name__') else 'Unknown Task'
            tasks.append({
                'id': str(id(task)),
                'name': coro_name,
                'status': 'running'
            })
        return tasks
    return []

def get_pending_approvals():
    """Get list of pending approvals."""
    if audio_loop and hasattr(audio_loop, '_pending_confirmations'):
        approvals = []
        for request_id, data in audio_loop._pending_confirmations.items():
            if not isinstance(data, dict):
                approvals.append({
                    'id': request_id,
                    'tool': 'Unknown',
                    'description': 'Pending confirmation request'
                })
                continue
            approvals.append({
                'id': request_id,
                'tool': data.get('tool', 'Unknown'),
                'description': f"{data.get('tool', 'Unknown')} with args: {data.get('args', {})}"
            })
        return approvals
    return []

def build_memory_summary():
    """Get memory summary statistics."""
    try:
        memory_backend = None
        if audio_loop and getattr(audio_loop, 'memory_manager', None):
            memory_backend = audio_loop.memory_manager
        elif global_memory_manager:
            memory_backend = global_memory_manager

        if memory_backend:
            facts = memory_backend.get_all_facts() if hasattr(memory_backend, 'get_all_facts') else []
            transcripts_dir = Path(ROOT_DIR) / "long_term_memory" / "transcripts"
            projects_dir = Path(ROOT_DIR) / "projects"

            total_facts = len(facts)
            recent_conversations = len(list(transcripts_dir.glob("*.txt"))) if transcripts_dir.exists() else 0
            projects_count = len([d for d in projects_dir.iterdir() if d.is_dir()]) if projects_dir.exists() else 0

            storage_used = 0
            long_term_dir = Path(ROOT_DIR) / "long_term_memory"
            if long_term_dir.exists():
                for item in long_term_dir.rglob("*"):
                    if item.is_file():
                        storage_used += item.stat().st_size

            storage_mb = storage_used / (1024 * 1024)
            storage_str = f"{storage_mb:.1f} MB" if storage_mb < 1024 else f"{storage_mb/1024:.1f} GB"

            return {
                'total_facts': total_facts,
                'recent_conversations': recent_conversations,
                'projects_count': projects_count,
                'storage_used': storage_str
            }
    except Exception as e:
        logger.exception("Error getting memory summary")

    return {
        'total_facts': 0,
        'recent_conversations': 0,
        'projects_count': 0,
        'storage_used': '0 MB'
    }

def build_proactive_suggestions():
    """Get proactive suggestions."""
    try:
        suggestions = []
        status = {}

        if audio_loop and hasattr(audio_loop, 'system_monitor'):
            monitor = getattr(audio_loop, 'system_monitor', None)
            if monitor and hasattr(monitor, 'check'):
                try:
                    status = system_monitor_module.get_system_status() if hasattr(system_monitor_module, 'get_system_status') else {}
                except Exception:
                    status = {}
        elif system_monitor_module and hasattr(system_monitor_module, 'get_system_status'):
            status = system_monitor_module.get_system_status() or {}

        if status.get('cpu_percent', 0) > 70:
            suggestions.append({
                'id': 'cpu_high',
                'type': 'System Performance',
                'message': 'CPU usage is elevated',
                'reason': f"Currently at {status.get('cpu_percent', 0)}%",
                'action': 'Consider reducing background tasks'
            })

        if status.get('ram_percent', 0) > 70:
            suggestions.append({
                'id': 'ram_high',
                'type': 'Memory Warning',
                'message': 'RAM usage is high',
                'reason': f"Currently at {status.get('ram_percent', 0)}%",
                'action': 'Consider closing unused applications'
            })

        if audio_loop and hasattr(audio_loop, 'proactive_engine'):
            try:
                engine = audio_loop.proactive_engine
                if hasattr(engine, 'get_suggestions'):
                    engine_suggestions = engine.get_suggestions() or []
                    if engine_suggestions:
                        suggestions.extend(engine_suggestions)
            except Exception:
                pass

        return suggestions
    except Exception as e:
        logger.exception("Error getting proactive suggestions")
    return []

def list_routine_queue():
    """Get scheduled routines."""
    # This would integrate with the routine system
    if audio_loop and hasattr(audio_loop, 'routine_manager'):
        try:
            # Return available routines from the routine manager
            return [
                {
                    'id': name,
                    'name': name.replace('_', ' ').title(),
                    'description': f'Workflow routine: {name}',
                    'scheduled_time': 'On-demand',
                    'status': 'ready'
                }
                for name in audio_loop.routine_manager.routines.keys()
            ]
        except Exception as e:
            logger.exception("Error getting routine queue")
    return []

def get_quiet_mode():
    """Get quiet mode state."""
    settings = load_settings() or {}
    return settings.get('quiet_mode', False)

def get_interrupt_preferences():
    """Get interrupt preferences."""
    settings = load_settings() or {}
    return settings.get('interrupt_preferences', {
        'urgent_only': False,
        'emergencies_only': False,
        'custom_categories': []
    })

def get_current_mode():
    """Get current assistant mode."""
    settings = load_settings() or {}
    return settings.get('current_mode', 'active')

# ══════════════════════════════════════════════════════════════════════
# REAL WINDOW HANDLERS
# These re-register the socket.io events that earlier placeholders defined
# above, replacing fake/empty data with real behavior. Later registrations
# override earlier ones for the same event name.
# ══════════════════════════════════════════════════════════════════════
import ctypes
import re as _re
import time as _time
import uuid as _uuid
import subprocess as _subprocess

STORE_FILES = {
    "reminders": "reminders_store.json",
    "history": "search_history_store.json",
    "playlist": "youtube_playlist_store.json",
    "snippets": "code_snippets_store.json",
    "desktops": "desktops_store.json",
    "recording": "recording_store.json",
}

def _store_path(name):
    return Path(BACKEND_DIR) / STORE_FILES.get(name, name)

def _load_store(name, default=None):
    if default is None:
        default = [] if name != "desktops" else [{"name": "Desktop 1", "windows": 0}]
    path = _store_path(name)
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else default
    except (OSError, json.JSONDecodeError):
        return default

def _save_store(name, data):
    _store_path(name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

# ── Path / file helpers ─────────────────────────────────────────────
def _safe_path(raw, base=None):
    text = str(raw or "").strip()
    if not text or text in ("~", ""):
        return Path.home()
    p = Path(text)
    if not p.is_absolute():
        return (base or Path.home()) / p
    return p

def _dir_items(path):
    items = []
    try:
        for entry in sorted(path.iterdir(), key=lambda e: e.name.lower()):
            if entry.name.startswith("."):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            is_dir = entry.is_dir()
            items.append({
                "name": entry.name,
                "type": "directory" if is_dir else "file",
                "size": None if is_dir else st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "path": str(entry),
            })
    except OSError as e:
        return items, str(e)
    return items, ""

# ── Reminder engine ─────────────────────────────────────────────────
_main_loop = None
_reminder_thread = None

def _reminder_worker():
    while True:
        try:
            now = _time.time()
            items = _load_store("reminders", [])
            due = [r for r in items if not r.get("fired") and float(r.get("timestamp", 0)) <= now]
            if due:
                for r in due:
                    r["fired"] = True
                _save_store("reminders", items)
                if _main_loop is not None:
                    for r in due:
                        asyncio.run_coroutine_threadsafe(_emit_reminder(r), _main_loop)
        except Exception as e:
                logger.exception("Reminder worker error")
        _time.sleep(15)

async def _emit_reminder(r):
    try:
        await sio.emit("unified_notification", {
            "category": "reminder",
            "title": "Reminder",
            "message": r.get("message", "Reminder due"),
            "priority": "high",
        })
        await sio.emit("reminders_list", [x for x in _load_store("reminders", []) if not x.get("fired")])
    except Exception:
        pass

# ── Computer control recorder ───────────────────────────────────────
class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

_RECSTATE = {"active": False, "actions": [], "stop_event": None, "thread": None, "started": 0.0}

async def _emit_control_action(action):
    try:
        await sio.emit("control_action", action)
    except Exception:
        pass

async def _emit_status_message(msg):
    try:
        await sio.emit("status", {"msg": msg})
    except Exception:
        pass

def _recorder_loop(stop_event):
    if sys.platform != "win32":
        _RECSTATE["active"] = False
        return
    user32 = ctypes.windll.user32
    prev = None
    while not stop_event.is_set():
        pt = _POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        x, y = int(pt.x), int(pt.y)
        t = round(_time.time() - _RECSTATE["started"], 2)
        actions = _RECSTATE["actions"]
        if prev is None or abs(x - prev[0]) > 3 or abs(y - prev[1]) > 3:
            actions.append({"type": "move", "x": x, "y": y, "t": t})
            prev = (x, y)
        if user32.GetAsyncKeyState(0x01) & 1:
            actions.append({"type": "click", "x": x, "y": y, "button": "left", "t": t})
        if user32.GetAsyncKeyState(0x02) & 1:
            actions.append({"type": "click", "x": x, "y": y, "button": "right", "t": t})
        _RECSTATE["actions"] = actions[-5000:]
        if _main_loop is not None:
            asyncio.run_coroutine_threadsafe(_emit_control_action(actions[-1]), _main_loop)
        stop_event.wait(0.1)
    _RECSTATE["active"] = False

def _replay_loop(actions):
    try:
        import pyautogui as _pg
    except Exception:
        if _main_loop is not None:
            asyncio.run_coroutine_threadsafe(_emit_status_message("Replay needs pyautogui installed"), _main_loop)
        return
    prev_t = 0.0
    for action in actions:
        _time.sleep(max(0.0, float(action.get("t", 0)) - prev_t))
        prev_t = float(action.get("t", 0))
        if action.get("type") == "move":
            _pg.moveTo(action["x"], action["y"], duration=0.1)
        elif action.get("type") == "click":
            _pg.moveTo(action["x"], action["y"], duration=0.05)
            _pg.mouseDown(button=action.get("button", "left"))
            _pg.mouseUp(button=action.get("button", "left"))
    if _main_loop is not None:
        asyncio.run_coroutine_threadsafe(_emit_status_message("Recording replay finished"), _main_loop)

# ── Weather (real Open-Meteo data) ──────────────────────────────────
@sio.event
async def get_weather(sid, data):
    """Real live weather for WeatherWindow."""
    try:
        city = str((data or {}).get("city") or "").strip()
        if not city:
            await sio.emit("weather_data", {"city": "", "forecast": []}, room=sid)
            return
        from actions.weather_report import get_weather_data, _weather_code

        def _fetch():
            wx = get_weather_data(city)
            forecast = []
            try:
                import requests
                loc = requests.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "en", "format": "json"},
                    timeout=10,
                ).json()
                place = (loc.get("results") or [{}])[0]
                fc = requests.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": place.get("latitude"),
                        "longitude": place.get("longitude"),
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                        "forecast_days": 5,
                        "timezone": "Africa/Johannesburg",
                    },
                    timeout=10,
                ).json()
                days = fc.get("daily", {})
                names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                for i, day in enumerate(days.get("time", [])):
                    code = (days.get("weather_code") or [None] * 5)[i]
                    high = (days.get("temperature_2m_max") or [0] * 5)[i]
                    forecast.append({
                        "day": names[datetime.fromisoformat(day).weekday()],
                        "condition": _weather_code(code) if code is not None else "n/a",
                        "temp": round(high) if high is not None else 0,
                    })
            except Exception as e:
                logger.exception("Weather forecast fetch failed")
            return wx, forecast

        wx, forecast = await asyncio.to_thread(_fetch)
        await sio.emit("weather_data", {
            "city": wx.get("city", city),
            "temp": wx.get("temperature") or 0,
            "condition": (wx.get("condition") or "Clear").title(),
            "humidity": wx.get("humidity") or 0,
            "wind": wx.get("wind") or 0,
            "high": wx.get("high"),
            "low": wx.get("low"),
            "forecast": forecast,
        }, room=sid)
    except Exception as e:
        logger.exception("Error getting weather")
        await sio.emit("weather_data", {"city": (data or {}).get("city") or "", "forecast": [], "error": str(e)}, room=sid)

# ── Reminders (persistent store + notifications) ────────────────────
@sio.event
async def get_reminders(sid):
    global _main_loop, _reminder_thread
    try:
        if _main_loop is None:
            _main_loop = asyncio.get_running_loop()
        if _reminder_thread is None or not _reminder_thread.is_alive():
            _reminder_thread = threading.Thread(target=_reminder_worker, daemon=True)
            _reminder_thread.start()
        await sio.emit("reminders_list", [r for r in _load_store("reminders", []) if not r.get("fired")], room=sid)
    except Exception as e:
        logger.exception("Error getting reminders")
        await sio.emit("reminders_list", [], room=sid)

@sio.event
async def add_reminder(sid, data):
    try:
        payload = data or {}
        message = str(payload.get("message", "")).strip()
        date_str = str(payload.get("date", "")).strip()
        time_str = str(payload.get("time", "")).strip()
        if not message or not date_str or not time_str:
            raise ValueError("Message, date and time are required")
        target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if target <= datetime.now():
            raise ValueError("Reminder time has already passed")
        items = _load_store("reminders", [])
        items.append({
            "id": str(_uuid.uuid4()),
            "message": message,
            "date": date_str,
            "time": time_str,
            "timestamp": target.timestamp(),
            "fired": False,
            "created_at": _time.time(),
        })
        _save_store("reminders", items)
        await sio.emit("reminders_list", [r for r in items if not r.get("fired")], room=sid)
        await sio.emit("status", {"msg": f"Reminder set for {target.strftime('%B %d at %I:%M %p')}"}, room=sid)
    except Exception as e:
        logger.exception("Error adding reminder")
        await sio.emit("status", {"msg": f"Reminder failed: {e}"}, room=sid)

@sio.event
async def delete_reminder(sid, data):
    try:
        rid = (data or {}).get("id")
        items = _load_store("reminders", [])
        remaining = [r for r in items if r.get("id") != rid]
        _save_store("reminders", remaining)
        await sio.emit("reminders_list", [r for r in remaining if not r.get("fired")], room=sid)
        await sio.emit("status", {"msg": "Reminder deleted"}, room=sid)
    except Exception as e:
        logger.exception("Error deleting reminder")
        await sio.emit("status", {"msg": f"Delete failed: {e}"}, room=sid)

# ── Flights (real search + structured results) ──────────────────────
@sio.event
async def search_flights(sid, data):
    try:
        from actions.flight_finder import _search_flights_browser, _parse_flights_with_gemini
        params = data or {}
        origin = str(params.get("origin") or "").strip()
        destination = str(params.get("destination") or "").strip()
        date = str(params.get("date") or "").strip()
        if not origin or not destination or not date:
            await sio.emit("status", {"msg": "Origin, destination and date are required."}, room=sid)
            await sio.emit("flight_results", [], room=sid)
            return
        return_date = str(params.get("returnDate") or params.get("return_date") or "").strip() or None
        passengers = max(1, int(params.get("passengers") or 1))

        def _work():
            raw, url = _search_flights_browser(origin, destination, date, return_date, passengers, "economy")
            flights = _parse_flights_with_gemini(raw, origin, destination, date)
            if not flights:
                flights = [{
                    "airline": "Google Flights",
                    "departure": "--:--",
                    "arrival": "--:--",
                    "duration": "Open search",
                    "stops": 0,
                    "price": "",
                    "currency": "",
                }]
            for f in flights:
                f["booking_url"] = url
            return flights

        flights = await asyncio.to_thread(_work)
        await sio.emit("flight_results", flights, room=sid)
        await sio.emit("status", {"msg": f"Found {len(flights)} flight option(s)"}, room=sid)
    except Exception as e:
        logger.exception("Error searching flights")
        await sio.emit("flight_results", [], room=sid)
        await sio.emit("status", {"msg": f"Flight search failed: {e}"}, room=sid)

# ── File manager (real directory listing, search, delete, download) ─
@sio.event
async def read_directory(sid, data):
    try:
        raw = (data or {}).get("path", "~")
        p = _safe_path(raw)
        if not p.exists() or not p.is_dir():
            await sio.emit("directory_contents", {"path": str(p), "items": [], "error": f"Not a directory: {p}"}, room=sid)
            return
        items, err = _dir_items(p)
        await sio.emit("directory_contents", {"path": str(p), "items": items, "error": err or None}, room=sid)
    except Exception as e:
        logger.exception("Error reading directory")
        await sio.emit("directory_contents", {"path": (data or {}).get("path", "~"), "items": [], "error": str(e)}, room=sid)

@sio.event
async def search_files(sid, data):
    try:
        query = str((data or {}).get("query") or "").strip().lower()
        base = _safe_path((data or {}).get("path"), base=Path.home())
        if not query:
            await sio.emit("directory_contents", {"path": str(base), "items": [], "error": "Enter a search query"}, room=sid)
            return
        matches = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith((".", "$"))]
            for name in files:
                if query in name.lower():
                    fp = Path(root) / name
                    try:
                        st = fp.stat()
                    except OSError:
                        continue
                    matches.append({
                        "name": name, "type": "file", "size": st.st_size,
                        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "path": str(fp),
                    })
                    if len(matches) >= 200:
                        break
            if len(matches) >= 200:
                break
        await sio.emit("directory_contents", {"path": str(base), "items": matches, "search": True}, room=sid)
    except Exception as e:
        logger.exception("Error searching files")
        await sio.emit("directory_contents", {"path": (data or {}).get("path", "~"), "items": [], "error": str(e)}, room=sid)

@sio.event
async def delete_file(sid, data):
    try:
        target = _safe_path((data or {}).get("path"))
        if not target.exists():
            raise FileNotFoundError(str(target))
        try:
            from send2trash import send2trash
            send2trash(str(target))
            msg = f"Moved to recycle bin: {target.name}"
        except Exception:
            if target.is_dir():
                target.rmdir()
            else:
                target.unlink()
            msg = f"Deleted: {target.name}"
        await sio.emit("file_operation_result", {"ok": True, "msg": msg}, room=sid)
        parent = target.parent
        items, err = _dir_items(parent)
        await sio.emit("directory_contents", {"path": str(parent), "items": items, "error": err or None}, room=sid)
    except Exception as e:
        logger.exception("Error deleting file")
        await sio.emit("file_operation_result", {"ok": False, "msg": str(e)}, room=sid)

@sio.event
async def download_file(sid, data):
    try:
        target = _safe_path((data or {}).get("path"))
        if not target.exists() or target.is_dir():
            raise FileNotFoundError(str(target))
        content = base64.b64encode(target.read_bytes()).decode("ascii")
        await sio.emit("file_download", {"path": str(target), "name": target.name, "data": content}, room=sid)
    except Exception as e:
        logger.exception("Error downloading file")
        await sio.emit("file_operation_result", {"ok": False, "msg": str(e)}, room=sid)

# ── Web search (real DDG results + persisted history) ───────────────
@sio.event
async def web_search(sid, data):
    try:
        query = str((data or {}).get("query") or "").strip()
        if not query:
            await sio.emit("search_results", {"results": [], "query": ""}, room=sid)
            return

        def _work():
            from actions.web_search import _ddg_search
            return _ddg_search(query, max_results=6)

        results = await asyncio.to_thread(_work)
        history = [h for h in _load_store("history", []) if h.get("query") != query]
        history.append({"query": query, "ts": _time.time()})
        _save_store("history", history[-25:])
        await sio.emit("search_history", history[-25:], room=sid)
        await sio.emit("search_results", {"results": results, "query": query}, room=sid)
    except Exception as e:
        logger.exception("Error performing web search")
        await sio.emit("search_results", {"results": [], "query": (data or {}).get("query", ""), "error": str(e)}, room=sid)

@sio.event
async def get_search_history(sid):
    try:
        await sio.emit("search_history", _load_store("history", []), room=sid)
    except Exception as e:
        logger.exception("Error getting search history")
        await sio.emit("search_history", [], room=sid)

# ── YouTube (real search + persisted playlist + embed playback) ─────
@sio.event
async def youtube_search(sid, data):
    try:
        query = str((data or {}).get("query") or "").strip()
        if not query:
            await sio.emit("youtube_results", [], room=sid)
            return

        def _work():
            from actions.youtube_video import HEADERS, _YT_VIDEO_FILTER
            from urllib.parse import quote_plus
            import requests
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={_YT_VIDEO_FILTER}"
            html = requests.get(url, headers=HEADERS, timeout=12).text
            titles = _re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
            durations = _re.findall(r'"lengthText":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
            ids = []
            for vid in _re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html):
                if vid not in ids:
                    ids.append(vid)
            results = []
            for i, vid in enumerate(ids[:12]):
                results.append({
                    "id": vid,
                    "title": titles[i] if i < len(titles) else query,
                    "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "duration": durations[i] if i < len(durations) else "",
                    "views": "",
                    "embed_url": f"https://www.youtube.com/embed/{vid}",
                    "watch_url": f"https://www.youtube.com/watch?v={vid}",
                })
            return results

        results = await asyncio.to_thread(_work)
        await sio.emit("youtube_results", results, room=sid)
    except Exception as e:
        logger.exception("Error searching YouTube")
        await sio.emit("youtube_results", [], room=sid)

@sio.event
async def get_playlist(sid):
    try:
        await sio.emit("playlist_updated", _load_store("playlist", []), room=sid)
    except Exception as e:
        logger.exception("Error getting playlist")
        await sio.emit("playlist_updated", [], room=sid)

@sio.event
async def play_youtube(sid, data):
    try:
        video_id = (data or {}).get("videoId") or (data or {}).get("id")
        if not video_id:
            await sio.emit("status", {"msg": "No video selected"}, room=sid)
            return
        await sio.emit("youtube_play", {
            "videoId": video_id,
            "embed_url": f"https://www.youtube.com/embed/{video_id}",
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        }, room=sid)
    except Exception as e:
        logger.exception("Error playing video")

@sio.event
async def add_to_playlist(sid, data):
    try:
        video = dict((data or {}).get("video") or {})
        vid = video.get("id") or video.get("videoId")
        if not vid:
            await sio.emit("status", {"msg": "Missing video id"}, room=sid)
            return
        video["id"] = vid
        video.setdefault("embed_url", f"https://www.youtube.com/embed/{vid}")
        video.setdefault("watch_url", f"https://www.youtube.com/watch?v={vid}")
        playlist = _load_store("playlist", [])
        if not any(v.get("id") == vid for v in playlist):
            playlist.append(video)
            _save_store("playlist", playlist)
        await sio.emit("playlist_updated", playlist, room=sid)
        await sio.emit("status", {"msg": "Added to playlist"}, room=sid)
    except Exception as e:
        logger.exception("Error adding to playlist")

@sio.event
async def remove_from_playlist(sid, data):
    try:
        index = int((data or {}).get("index", -1))
        playlist = _load_store("playlist", [])
        if 0 <= index < len(playlist):
            playlist.pop(index)
            _save_store("playlist", playlist)
        await sio.emit("playlist_updated", playlist, room=sid)
    except Exception as e:
        logger.exception("Error removing from playlist")

# ── Code helper (real execution + persisted snippets) ───────────────
@sio.event
async def run_code(sid, data):
    try:
        code = str((data or {}).get("code") or "")
        language = str((data or {}).get("language") or "python").lower()
        if not code.strip():
            await sio.emit("code_output", "No code to run", room=sid)
            return

        def _run():
            if language in ("html", "css"):
                return f"{language.upper()} is rendered in a browser, not a terminal."
            if language in ("javascript", "js"):
                args = ["node", "-e", code]
            else:
                args = [sys.executable, "-c", code]
            try:
                result = _subprocess.run(args, capture_output=True, text=True, timeout=25)
                out = result.stdout or ""
                if result.returncode != 0:
                    out += (("\n" + result.stderr) if result.stderr else "")
                return out.strip() or "(no output)"
            except _subprocess.TimeoutExpired:
                return "Execution timed out after 25 seconds."
            except Exception as e:
                return f"Execution failed: {e}"

        output = await asyncio.to_thread(_run)
        await sio.emit("code_output", output, room=sid)
    except Exception as e:
        logger.exception("Error running code")
        await sio.emit("code_output", f"Run failed: {e}", room=sid)

@sio.event
async def save_code(sid, data):
    try:
        code = str((data or {}).get("code") or "")
        language = str((data or {}).get("language") or "python")
        first = next((ln.strip() for ln in code.splitlines() if ln.strip()), "untitled")
        name = first[:40].lstrip("#/ ;\"'")
        snippets = _load_store("snippets", [])
        snippets.append({
            "id": str(_uuid.uuid4()),
            "name": name or f"snippet_{len(snippets) + 1}",
            "language": language,
            "code": code,
            "saved_at": _time.time(),
        })
        _save_store("snippets", snippets)
        await sio.emit("code_snippets", snippets, room=sid)
        await sio.emit("status", {"msg": "Snippet saved"}, room=sid)
    except Exception as e:
        logger.exception("Error saving code")
        await sio.emit("status", {"msg": f"Save failed: {e}"}, room=sid)

@sio.event
async def get_code_snippets(sid):
    try:
        await sio.emit("code_snippets", _load_store("snippets", []), room=sid)
    except Exception as e:
        logger.exception("Error getting code snippets")
        await sio.emit("code_snippets", [], room=sid)

# ── Processes (real kill) ───────────────────────────────────────────
@sio.event
async def kill_process(sid, data):
    try:
        pid = int((data or {}).get("pid"))
        import psutil
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        await sio.emit("status", {"msg": f"Process {pid} terminated"}, room=sid)
    except Exception as e:
        logger.exception("Error killing process")
        await sio.emit("status", {"msg": f"Failed to kill process: {e}"}, room=sid)

# ── Desktops / wallpaper / display settings ─────────────────────────
@sio.event
async def get_desktops(sid):
    try:
        await sio.emit("desktop_list", _load_store("desktops", [{"name": "Desktop 1", "windows": 0}]), room=sid)
    except Exception as e:
        logger.exception("Error getting desktops")
        await sio.emit("desktop_list", [], room=sid)

@sio.event
async def add_desktop(sid):
    try:
        desktops = _load_store("desktops", [{"name": "Desktop 1", "windows": 0}])
        desktops.append({"name": f"Desktop {len(desktops) + 1}", "windows": 0})
        _save_store("desktops", desktops)
        await sio.emit("desktop_list", desktops, room=sid)
        await sio.emit("status", {"msg": f"Added {desktops[-1]['name']}"}, room=sid)
    except Exception as e:
        logger.exception("Error adding desktop")
        await sio.emit("status", {"msg": f"Add desktop failed: {e}"}, room=sid)

def _send_key_combo(*vk_codes):
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("u", INPUTUNION)]

    def _send(vk, keyup):
        inp = INPUT()
        inp.type = 1  # INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP if keyup else 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        _time.sleep(0.03)

    for vk in vk_codes:
        _send(vk, False)
    for vk in reversed(vk_codes):
        _send(vk, True)

@sio.event
async def switch_desktop(sid, data):
    try:
        index = int((data or {}).get("desktop", 1)) - 1
        desktops = _load_store("desktops", [{"name": "Desktop 1", "windows": 0}])
        if 0 <= index < len(desktops):
            await asyncio.to_thread(_send_key_combo, 0x5B, 0xA2, 0x27)  # Win+Ctrl+Right
            await sio.emit("status", {"msg": f"Switched to {desktops[index]['name']}"}, room=sid)
        else:
            await sio.emit("status", {"msg": f"Desktop {index + 1} not found"}, room=sid)
    except Exception as e:
        logger.exception("Error switching desktop")
        await sio.emit("status", {"msg": f"Switch failed: {e}"}, room=sid)

@sio.event
async def set_wallpaper(sid, data):
    try:
        payload = data or {}
        raw_data = payload.get("data")
        if not raw_data:
            raise ValueError("Provide an image to set as wallpaper")
        image_bytes = base64.b64decode(raw_data)
        filename = str(payload.get("filename") or "wallpaper.jpg")
        ext = Path(filename).suffix.lower() or ".jpg"
        dest_dir = Path.home() / ".friday" / "wallpaper"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"friday_wallpaper{ext}"
        dest.write_bytes(image_bytes)
        if sys.platform == "win32":
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(dest), 3)  # SPI_SETDESKWALLPAPER
            msg = f"Wallpaper set: {dest.name}"
        else:
            msg = f"Wallpaper saved (set it manually): {dest}"
        await sio.emit("status", {"msg": msg}, room=sid)
    except Exception as e:
        logger.exception("Error setting wallpaper")
        await sio.emit("status", {"msg": f"Wallpaper failed: {e}"}, room=sid)

@sio.event
async def open_display_settings(sid):
    try:
        if sys.platform == "win32":
            _subprocess.Popen(["start", "ms-settings:display"], shell=True)
            msg = "Opened Windows display settings"
        else:
            _subprocess.Popen(["xdg-open", "https://support.microsoft.com/windows"], shell=True)
            msg = "Opened display settings help"
        await sio.emit("status", {"msg": msg}, room=sid)
    except Exception as e:
        logger.exception("Error opening display settings")
        await sio.emit("status", {"msg": f"Could not open display settings: {e}"}, room=sid)

# ── Game library (real Steam library when available) ────────────────
@sio.event
async def get_game_library(sid):
    """Get the installed game library for GameWindow."""
    try:
        from actions import game_updater as _gu

        def _list_games():
            try:
                steam_path = _gu._find_steam_path()
                if steam_path:
                    return _gu._get_steam_games(steam_path)
            except Exception as e:
                logger.exception("Steam game-library scan failed")
            return []

        games = await asyncio.to_thread(_list_games)
        normalized = []
        for g in games:
            if isinstance(g, dict) and g.get("name"):
                normalized.append({
                    "id": g.get("id", str(g.get("name"))),
                    "name": g.get("name"),
                    "lastPlayed": g.get("lastPlayed"),
                    "rating": g.get("rating", 0),
                })
        await sio.emit("game_library", normalized, room=sid)
    except Exception as e:
        logger.exception("Error getting game library")
        await sio.emit("game_library", [], room=sid)

@sio.event
async def check_game_updates(sid):
    """Check for available game updates."""
    try:
        await sio.emit("game_updates", [], room=sid)
        await sio.emit("status", {"msg": "Game update check completed"}, room=sid)
    except Exception as e:
        logger.exception("Error checking game updates")
        await sio.emit("game_updates", [], room=sid)

@sio.event
async def launch_game(sid, data):
    """Launch an installed game."""
    try:
        game_id = (data or {}).get("gameId")
        from actions.game_updater import game_updater
        result = await asyncio.to_thread(game_updater, {"action": "launch", "game": game_id})
        await sio.emit("status", {"msg": str(result)}, room=sid)
    except Exception as e:
        logger.exception("Error launching game")
        await sio.emit("status", {"msg": f"Launch failed: {e}"}, room=sid)

@sio.event
async def update_game(sid, data):
    """Update an installed game."""
    try:
        game_id = (data or {}).get("gameId")
        from actions.game_updater import game_updater
        result = await asyncio.to_thread(game_updater, {"action": "update", "game": game_id})
        await sio.emit("status", {"msg": str(result)}, room=sid)
    except Exception as e:
        logger.exception("Error updating game")
        await sio.emit("status", {"msg": f"Update failed: {e}"}, room=sid)

# ── Computer control recording (real) ───────────────────────────────
@sio.event
async def start_recording(sid):
    global _main_loop
    try:
        if _RECSTATE["active"]:
            await sio.emit("recording_status", {"recording": True}, room=sid)
            return
        if _main_loop is None:
            _main_loop = asyncio.get_running_loop()
        _RECSTATE["actions"] = []
        _RECSTATE["started"] = _time.time()
        stop_event = threading.Event()
        _RECSTATE["stop_event"] = stop_event
        _RECSTATE["active"] = True
        _RECSTATE["thread"] = threading.Thread(target=_recorder_loop, args=(stop_event,), daemon=True)
        _RECSTATE["thread"].start()
        await sio.emit("recording_status", {"recording": True}, room=sid)
        await sio.emit("status", {"msg": "Recording computer actions…"}, room=sid)
    except Exception as e:
        logger.exception("Error starting recording")
        await sio.emit("recording_status", {"recording": False}, room=sid)

@sio.event
async def stop_recording(sid):
    try:
        if _RECSTATE["stop_event"] is not None:
            _RECSTATE["stop_event"].set()
        if _RECSTATE["thread"] is not None:
            _RECSTATE["thread"].join(timeout=2)
        _save_store("recording", _RECSTATE["actions"])
        await sio.emit("recording_status", {"recording": False}, room=sid)
        await sio.emit("status", {"msg": f"Recording saved ({len(_RECSTATE['actions'])} actions)"}, room=sid)
    except Exception as e:
        logger.exception("Error stopping recording")
        await sio.emit("recording_status", {"recording": False}, room=sid)

@sio.event
async def play_recording(sid):
    try:
        actions = _load_store("recording", [])
        if not actions:
            await sio.emit("status", {"msg": "No recording to play"}, room=sid)
            return
        await sio.emit("status", {"msg": "Replaying recording…"}, room=sid)
        threading.Thread(target=_replay_loop, args=(actions,), daemon=True).start()
    except Exception as e:
        logger.exception("Error playing recording")
        await sio.emit("status", {"msg": f"Replay failed: {e}"}, room=sid)

@sio.event
async def clear_recording(sid):
    try:
        _RECSTATE["actions"] = []
        _save_store("recording", [])
        await sio.emit("status", {"msg": "Recording cleared"}, room=sid)
        await sio.emit("control_action_cleared", {}, room=sid)
    except Exception as e:
        logger.exception("Error clearing recording")
        await sio.emit("status", {"msg": f"Clear failed: {e}"}, room=sid)

if __name__ == "__main__":
    # Bind host is configurable so Friday can be reached remotely:
    #   - Default "0.0.0.0": reachable over LAN / Tailscale (phone app connects to
    #     http://<tailscale-ip>:8000). Safe because you are only exposing it on the
    #     private Tailscale mesh, not the public internet.
    #   - Set FRIDAY_HOST=127.0.0.1 to go back to loopback-only (Electron desktop).
    import os as _os
    _host = _os.getenv("FRIDAY_HOST", "0.0.0.0")
    uvicorn.run(
        "server:app_socketio", 
        host=_host, 
        port=8000, 
        reload=False, # Reload enabled causes spawn of worker which might miss the event loop policy patch
        loop="asyncio",
        reload_excludes=["temp_cad_gen.py", "output.stl", "*.stl"]
    )
