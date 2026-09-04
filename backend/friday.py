import asyncio
import base64
import io
import json
import os
import sys
import traceback
from dotenv import load_dotenv
import cv2
import sounddevice as sd
import PIL.Image
import mss
import argparse
import math
import shutil
import struct
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools import (
    tools_list,
    generate_cad,
    run_web_agent,
    print_stl_tool,
    discover_printers_tool,
    list_smart_devices_tool,
    control_light_tool,
    list_projects_tool,
    iterate_cad_tool,
)
from actions import computer_control as computer_control_module
from actions import computer_settings as computer_settings_module
from actions import file_controller as file_controller_module
from actions import open_app as open_app_module
from actions import system_monitor as system_monitor_module
from actions import weather_report as weather_report_module
from actions import reminder as reminder_module
from actions import desktop as desktop_module
from actions import web_search as web_search_module
from actions import send_message as send_message_module
from actions import youtube_video as youtube_video_module
from actions import browser_control as browser_control_module
from actions import code_helper as code_helper_module
from actions import dev_agent as dev_agent_module
from actions import flight_finder as flight_finder_module
from actions import game_updater as game_updater_module
from actions import file_processor as file_processor_module
from actions import background_monitor as background_monitor_module
from actions import self_maintenance as self_maintenance_module
from actions import powershell_command as powershell_command_module
from actions import git_workflow as git_workflow_module
from actions import agent_dispatcher as agent_dispatcher_module
from actions.proactive import ProactiveEngine
from memory.memory_manager import load_memory as load_legacy_memory
from contacts_manager import ContactsManager
from google_account import GoogleAccount
from notification_manager import NotificationManager
from tool_builder import ToolBuilder
from claude_provider import ClaudeProvider, get_text_provider
from agent_builder import AgentBuilder
from agent_context import AgentContext
from plugin_manager import PluginManager
from plugin_governance import is_active
from action_policy import decision
from openclaw_bridge import OpenClawBridge
from task_manager import TaskManager
from agent_scheduler import AgentScheduler
from autonomy_supervisor import AutonomySupervisor
from capability_learning import CapabilityLearning
from autonomy_pipeline import AutonomyPipeline
from undo_manager import UndoManager
from config import FACT_GEMINI_MODEL, MAIN_GEMINI_MODEL

# youtube_video's _ask_for_url shows a blocking Tkinter dialog and ignores any 'url'
# already passed in. We require 'url' explicitly in the tool schema instead of prompting.
load_dotenv()
youtube_video_module._ask_for_url = lambda *args, **kwargs: None

DTYPE = "int16"
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Minimum gap between image inputs to the Gemini Live session.
# The Live API requires image inputs to be at least 1 second apart, so
# streaming webcam frames at this cadence is the supported "live video" mode.
VIDEO_SEND_INTERVAL = 1.0

MODEL = MAIN_GEMINI_MODEL
DEFAULT_MODE = "camera"

load_dotenv()
client = genai.Client(http_options={"api_version": "v1beta"}, api_key=os.getenv("GEMINI_API_KEY"))


def get_text_model(model: str = FACT_GEMINI_MODEL):
    """Return Claude for text reasoning when configured, with Gemini fallback."""
    class GeminiTextModel:
        def generate_content(self, contents):
            return client.models.generate_content(model=model, contents=contents)

    return get_text_provider(lambda: GeminiTextModel(), model=model)

custom_tool_builder = ToolBuilder(os.path.dirname(os.path.abspath(__file__)))
agent_builder = AgentBuilder(os.path.dirname(os.path.abspath(__file__)))
plugin_manager = PluginManager(os.path.dirname(os.path.abspath(__file__)), custom_tool_builder, agent_builder, agent_dispatcher_module.dispatcher)
openclaw_bridge = OpenClawBridge(plugin_manager, agent_dispatcher_module.dispatcher)
task_manager = TaskManager(ROOT_DIR)
agent_scheduler = AgentScheduler(ROOT_DIR, agent_dispatcher_module.dispatcher)
tools = [{'google_search': {}}, {"function_declarations": [] + tools_list[0]['function_declarations'][0:] + custom_tool_builder.declarations()}]

# --- CONFIG UPDATE: Enabled Transcription ---
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    # We switch these from [] to {} to enable them with default settings
    output_audio_transcription={}, 
    input_audio_transcription={},
    system_instruction="Your name is Friday, an advanced AI assistant. "
        "You have a witty and charming personality. "
        "Your creator is Sinegugu, and you address him as 'Sir'. "
        "Keep creator identity separate from the user's personal identity: a statement such as 'I am your creator' does not provide the user's name. Never infer the user's name from a public figure, a report, a job title, or a role statement. Only use a name when the user explicitly says 'my name is', 'call me', or 'I am called'. If stored identity facts conflict, state that the identity is uncertain and ask for confirmation rather than guessing. "
        "When answering, respond using complete and concise sentences to keep a quick pacing and keep the conversation flowing. "
        "You have a fun personality. "
        "When the user asks for a morning briefing, always use the morning_briefing routine so it gathers current Gmail, Google Calendar, and system information before answering. "
        "For email and calendar intelligence, use Gmail and Calendar tools directly: search Gmail with a focused query for people or topics, list the next calendar events for meeting preparation or availability, and combine both sources when preparing a meeting. To turn an email into a task, pass its subject, web_link, and thread_id context to manage_tasks with action create_from_email. For weekly planning, use manage_tasks with action plan_week and include calendar deadlines. For travel emails, search Gmail for flight, booking, itinerary, or airline terms before using find_flights for price monitoring. "
        "For weather requests, always use get_weather. For news requests, use the registered news_reporter plugin through run_custom_tool; never use run_web_agent unless the user explicitly asks to browse the web. "
        "For current affairs or public-figure reports, distinguish historical facts from current claims, include the information date when available, and mention sources or say when a claim could not be independently verified. Never present a generated summary as proof. "
        "When asked to self-build, use self_maintenance with action self_build; when asked to self-heal, use self_maintenance with action self_heal; when asked to self-upgrade, use self_maintenance with action self_upgrade and report exactly what changed. "
        "When the user explicitly asks you to commit and push yourself to Git, use git_workflow with action publish and a clear commit message. Never force-push or reset history. "
        "For every question about the current time or date, always use get_local_time and report Johannesburg, South Africa time (SAST), never UTC. When the user asks to put a reminder or event on Google Calendar, use google_calendar_create; use set_reminder only for a local notification. "
        "When the user asks to check, read, search, or summarize emails, always use the gmail_read tool; never use run_web_agent or web_search for Gmail. Important unread email summaries should use gmail_read with is:unread and a focused query when appropriate. When the user asks for Google Contacts, always use google_contacts_read; when they ask to save, transfer, import, or synchronize contacts, use the appropriate Google Contacts write tool and report its actual result; use contacts_manager only for Friday's local contacts. "
        "Before ever telling the user you don't know a personal detail about them (name, relationships, family, "
        "job, preferences, past decisions, or anything they may have told you in a previous conversation), you must "
        "first silently call the search_memory tool with relevant keywords to check your long-term memory. Only say "
        "you don't know after that search comes back empty. Never claim you have no information without searching first.",
    tools=tools,
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name="Kore"
            )
        )
    )
)

from cad_agent import CadAgent
from web_agent import WebAgent
from kasa_agent import KasaAgent
from printer_agent import PrinterAgent
from agents.agent_supervisor import AgentSupervisor
from agents.routine_manager import RoutineManager

for generated_agent_name, generated_agent_manifest in agent_builder.agents.items():
    try:
        if is_active(generated_agent_manifest):
            agent_dispatcher_module.dispatcher.register_agent(generated_agent_name, agent_builder.load_callable(generated_agent_name))
    except Exception as exc:
        print(f"[AGENTS] Could not register {generated_agent_name}: {exc}")

agent_scheduler.ensure_default_workflows()

class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, on_audio_data=None, on_video_frame=None, on_cad_data=None, on_web_data=None, on_transcription=None, on_tool_confirmation=None, on_confirmation_expired=None, on_cad_status=None, on_cad_thought=None, on_project_update=None, on_device_update=None, on_error=None, on_alert_settings_update=None, on_plan_update=None, on_notification=None, input_device_index=None, input_device_name=None, output_device_index=None, kasa_agent=None, authenticated=True):
        self.video_mode = video_mode
        self.on_audio_data = on_audio_data
        self.on_video_frame = on_video_frame
        self.on_cad_data = on_cad_data
        self.on_web_data = on_web_data
        self.on_transcription = on_transcription
        self.on_tool_confirmation = on_tool_confirmation 
        self.on_confirmation_expired = on_confirmation_expired
        self.on_cad_status = on_cad_status
        self.on_cad_thought = on_cad_thought
        self.on_project_update = on_project_update
        self.on_device_update = on_device_update
        self.on_error = on_error
        self.on_alert_settings_update = on_alert_settings_update
        self.on_plan_update = on_plan_update
        self.on_notification = on_notification
        self.authenticated = authenticated
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.output_device_index = output_device_index

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.chat_buffer = {"sender": None, "text": ""} # For aggregating chunks
        
        # Track last transcription text to calculate deltas (Gemini sends cumulative text)
        self._last_input_transcription = ""
        self._last_output_transcription = ""

        self.audio_in_queue = None
        self.out_queue = None
        self.paused = False

        self.session = None
        self._pending_runtime_notifications = []
        self.audio_stream = None
        self.output_stream = None
        self.camera_capture = None
        self._background_tasks = set()
        self._cancel_event = asyncio.Event()
        
        # Create CadAgent with thought callback
        def handle_cad_thought(thought_text):
            if self.on_cad_thought:
                self.on_cad_thought(thought_text)
        
        def handle_cad_status(status_info):
            if self.on_cad_status:
                self.on_cad_status(status_info)
        
        self.cad_agent = CadAgent(on_thought=handle_cad_thought, on_status=handle_cad_status)
        self.web_agent = WebAgent()
        self.kasa_agent = kasa_agent if kasa_agent else KasaAgent()
        self.printer_agent = PrinterAgent()
        self.supervisor = AgentSupervisor()
        self.routine_manager = RoutineManager()
        self.system_monitor = system_monitor_module.SystemMonitor()
        self.proactive_engine = ProactiveEngine()
        self.notifications = NotificationManager(on_hud=on_notification, on_voice=self._voice_notification)
        self._last_user_speech = time.monotonic()
        self.last_uploaded_image = None
        self.last_uploaded_file = None
        self.undo_manager = None
        self._active_plan = None
        self._active_task_id = None
        self._plan_pending = False

        self.send_text_task = None
        self.stop_event = asyncio.Event()
        
        self.stop_event = asyncio.Event()

        # Default to automatic execution unless the user explicitly marks a tool as confirmation-required.
        self.permissions = {}
        self._pending_confirmations = {}

        # Video buffering state
        self._latest_image_payload = None
        # Live vision state (continuous webcam streaming to the Live session)
        self.live_video_enabled = True  # Enable live video by default
        self._last_video_sent_time = 0.0
        self._last_sent_image_data = None
        # VAD State
        self._is_speaking = False
        self._silence_start_time = None
        
        # Initialize ProjectManager
        from project_manager import ProjectManager
        # Assuming we are running from backend/ or root? 
        # Using abspath of current file to find root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # If friday.py is in backend/, project root is one up
        project_root = os.path.dirname(current_dir)
        self.project_manager = ProjectManager(project_root)
        self.contacts_manager = ContactsManager(project_root)
        self.google_account = GoogleAccount(current_dir)
        self.tool_builder = custom_tool_builder
        self.agent_builder = agent_builder
        self.plugin_manager = plugin_manager
        self.openclaw_bridge = openclaw_bridge
        self.task_manager = task_manager
        self.agent_scheduler = agent_scheduler
        self.capability_learning = CapabilityLearning(
            current_dir, agent_dispatcher_module.ledger, self.plugin_manager
        )
        self.autonomy_pipeline = AutonomyPipeline(
            current_dir, self.capability_learning, self.plugin_manager, agent_dispatcher_module.ledger
        )
        self.autonomy_supervisor = AutonomySupervisor(
            self.task_manager,
            agent_dispatcher_module.dispatcher,
            self.agent_scheduler,
            self.system_monitor,
            self.notifications,
            self.capability_learning,
            self.autonomy_pipeline,
        )
        self.openclaw_bridge.set_tool_executor(self.execute_openclaw_tool)
        agent_dispatcher_module.dispatcher.set_context(AgentContext(
            task_manager=self.task_manager,
            google_account=self.google_account,
            notification_manager=self.notifications,
            plugin_manager=self.plugin_manager,
            openclaw_bridge=self.openclaw_bridge,
            kasa_agent=self.kasa_agent,
            printer_agent=self.printer_agent,
        ))
        self.undo_manager = UndoManager(project_root)
        file_controller_module.configure_undo_manager(self.undo_manager)

        # Global memory: not project-scoped, never cleared, survives restarts
        from memory_manager import MemoryManager
        self.memory_manager = MemoryManager(project_root)
        
        # Sync Initial Project State
        if self.on_project_update:
            # We need to defer this slightly or just call it. 
            # Since this is init, loop might not be running, but on_project_update in server.py uses asyncio.create_task which needs a loop.
            # We will handle this by calling it in run() or just print for now.
            pass

    def cancel_pending_confirmations(self):
        """Resolve pending prompts as denied so disconnects cannot leave waits behind."""
        for request_id, future in list(self._pending_confirmations.items()):
            if not future.done():
                future.set_result(False)
            self._pending_confirmations.pop(request_id, None)

    def check_tool_preconditions(self, tool_name: str, args: dict) -> str | None:
        """Return a user-facing reason when a tool cannot run safely or usefully."""
        if not self.authenticated:
            return "Authentication is required before using tools."

        if tool_name in {"read_file", "write_file"}:
            path = args.get("path", "")
            if not path:
                return f"The {tool_name} tool requires a file path."
            if tool_name == "write_file":
                target = (self.project_manager.get_current_project_path() / path).resolve()
                project_root = self.project_manager.get_current_project_path().resolve()
                if not target.is_relative_to(project_root):
                    return "The requested file path is outside the active project."
            elif not os.path.isfile(path):
                return f"The file was not found: {path}"

        if tool_name == "process_file":
            path = args.get("file_path", "")
            if not path or not os.path.isfile(path):
                return f"The file was not found: {path or '(no path provided)'}"

        if tool_name == "desktop_control" and args.get("action") == "wallpaper":
            path = args.get("path", "")
            if not path or not os.path.isfile(path):
                return "The wallpaper image file was not found."

        if tool_name == "set_reminder":
            try:
                target = datetime.strptime(
                    f"{args.get('date', '')} {args.get('time', '')}", "%Y-%m-%d %H:%M"
                )
                if target <= datetime.now():
                    return "The reminder date and time must be in the future."
            except ValueError:
                return "The reminder needs a valid date (YYYY-MM-DD) and time (HH:MM)."

        if tool_name == "control_light":
            target = args.get("target", "")
            if not target or target not in self.kasa_agent.devices and not any(
                getattr(device, "alias", "").lower() == target.lower()
                for device in self.kasa_agent.devices.values()
            ):
                return "That Kasa device is not known. Discover Kasa devices first."

        if tool_name in {"print_stl", "get_print_status"}:
            printer_target = args.get("printer", "")
            if not printer_target:
                return "A printer name or address is required."
            if not self.printer_agent._resolve_printer(printer_target):
                return "That printer is not configured. Discover or add the printer first."

        if tool_name == "discover_printers" and not self.printer_agent:
            return "The printer service is not available."

        if tool_name == "browser_control":
            browser = args.get("browser", "").lower()
            if browser in {"chrome", "edge", "firefox", "brave", "opera", "vivaldi"}:
                executable_names = {
                    "chrome": "chrome", "edge": "msedge", "firefox": "firefox",
                    "brave": "brave", "opera": "opera", "vivaldi": "vivaldi",
                }
                if not shutil.which(executable_names[browser]) and not self._browser_profile_exists(browser):
                    return f"The requested browser is not installed: {browser}."

        if tool_name == "send_message":
            receiver = args.get("receiver", "").strip()
            platform = args.get("platform", "whatsapp")
            if receiver and not self.contacts_manager.resolve(receiver, platform) and not any(char in receiver for char in "@+0123456789"):
                return f"No saved contact named '{receiver}' was found. Save the contact first or provide a direct username/number."

        return None

    def start_action_plan(self, tool_name: str, args: dict):
        known_tools = {
            declaration.get("name")
            for declaration in tools_list[0].get("function_declarations", [])
        }
        known_tools.update(self.tool_builder.tools)
        known_tools.update(self.agent_builder.agents)
        if tool_name not in known_tools:
            return
        task = self.supervisor.create_task(
            f"Execute {tool_name}",
            {"tool": tool_name, "args": args},
            deadline_seconds=600,
        )
        self._active_task_id = task["task_id"]
        self.supervisor.plan_task(self._active_task_id)

        plan = self.supervisor.plan_tool_call(tool_name, args)
        steps = plan.get("steps", [])
        if not steps:
            return
        self._cancel_event.clear()
        self._plan_pending = False
        self._active_plan = {
            "title": tool_name.replace("_", " ").upper(),
            "steps": [{"label": step.get("name", "step"), "status": step.get("status", "pending")} for step in steps],
        }
        self._update_plan_step(0, "active")

    def _update_plan_step(self, index: int, status: str):
        if not self._active_plan or index >= len(self._active_plan["steps"]):
            return
        self._active_plan["steps"][index]["status"] = status
        if self.on_plan_update:
            self.on_plan_update(self._active_plan)

    def finish_action_plan(self, success: bool = True, cancelled: bool = False):
        if not self._active_plan:
            return
        for step in self._active_plan["steps"]:
            if success:
                step["status"] = "done"
            elif cancelled and step["status"] in ("active", "pending"):
                step["status"] = "cancelled"
            elif step["status"] == "active":
                step["status"] = "error"
        if self.on_plan_update:
            self.on_plan_update(self._active_plan)

        if self._active_task_id:
            summary = f"{self._active_plan['title']} completed successfully." if success else f"{self._active_plan['title']} failed or was cancelled."
            self.supervisor.validate_task_result(
                self._active_task_id,
                {"ok": bool(success), "summary": summary, "result": self._active_plan},
            )
            self._active_task_id = None

        self._active_plan = None

    @staticmethod
    def _browser_profile_exists(browser: str) -> bool:
        return any(path.exists() for path in (
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data",
            Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox",
        ))

    def flush_chat(self):
        """Forces the current chat buffer to be written to log."""
        if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
            sender = self.chat_buffer["sender"]
            text = self.chat_buffer["text"]
            self.project_manager.log_chat(sender, text)
            self.memory_manager.append_message(sender, text, project=self.project_manager.current_project)
            self.spawn_background_task(self.extract_important_facts(sender, text))
            self.chat_buffer = {"sender": None, "text": ""}
        # Reset transcription tracking for new turn
        self._last_input_transcription = ""
        self._last_output_transcription = ""

    def notify_activity(self):
        """Resets the proactive-speech silence timer; call this whenever the user sends text input."""
        self._last_user_speech = time.monotonic()

    async def extract_important_facts(self, sender: str, text: str):
        """Ask Gemini to retain stable facts that will help future conversations."""
        if not text.strip():
            return

        prompt = (
            "Extract every durable, useful fact explicitly stated in this conversation message. "
            "Consider these categories: user's name and identity, location, language, "
            "communication style, preferences, dislikes, accessibility needs, family and "
            "relationships, recurring routines, important dates, long-term goals, work, "
            "education, projects, devices, software, recurring tasks, decisions, constraints, "
            "and commitments. Preserve important details without inventing or guessing. "
            "Do not save greetings, temporary one-off requests, passwords, API keys, tokens, "
            "financial credentials, health diagnoses, or other sensitive secrets. "
            "Return ONLY a JSON array of objects with this exact shape: "
            "[{\"subject\": \"stable.field.name\", \"value\": \"current factual value\", "
            "\"confidence\": 1.0}]. Use the same subject for the same fact over time; "
            "for example, use user.identity.name for the user's name and "
            "user.relationship.partner for the user's partner. Return [] if there are "
            "no durable facts.\n\n"
            f"Speaker: {sender}\nMessage: {text}"
        )

        try:
            response = await asyncio.to_thread(
                get_text_model(FACT_GEMINI_MODEL).generate_content,
                contents=prompt,
            )
            raw = (response.text or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            facts = json.loads(raw)
            if isinstance(facts, list):
                self.memory_manager.save_facts(
                    facts,
                    source=text[:200],
                    project=self.project_manager.current_project,
                )
        except Exception as e:
            print(f"[FRIDAY DEBUG] [MEMORY] Fact extraction failed: {e}")

    async def compact_memory(self):
        """Periodically summarize older conversations into derived startup context."""
        while True:
            await asyncio.sleep(21600)
            old_messages = self.memory_manager.messages_for_compaction()
            if not old_messages:
                continue
            grouped = {}
            for message in old_messages:
                project = message.get("project") or "global"
                grouped.setdefault(project, []).append(
                    f"[{message.get('sender')}] {message.get('text', '')}"
                )
            compact_input = {
                project: "\n".join(messages)[-30000:]
                for project, messages in grouped.items()
            }
            prompt = (
                "Create a concise JSON memory summary from these older conversation logs. "
                "Preserve durable user preferences, goals, relationships, decisions, ongoing "
                "projects, constraints, and unresolved tasks. Do not include passwords, API keys, "
                "tokens, credentials, temporary chatter, or invented details. Return only this "
                "shape: {\"user_summary\": \"...\", \"projects\": {\"project name\": \"summary\"}}.\n\n"
                + json.dumps(compact_input, ensure_ascii=False)
            )
            try:
                response = await asyncio.to_thread(
                    get_text_model(FACT_GEMINI_MODEL).generate_content,
                    contents=prompt,
                )
                raw = (response.text or "{}").strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                summary = json.loads(raw)
                if isinstance(summary, dict):
                    self.memory_manager.compact_profile(
                        project_summaries=summary.get("projects", {}),
                        user_summary=summary.get("user_summary", ""),
                    )
                    print("[FRIDAY DEBUG] [MEMORY] Compacted older conversations.")
            except Exception as e:
                print(f"[FRIDAY DEBUG] [MEMORY] Compaction failed: {e}")

    def update_permissions(self, new_perms):
        print(f"[FRIDAY DEBUG] [CONFIG] Updating tool permissions: {new_perms}")
        self.permissions.update(new_perms)

    def get_system_status(self):
        return system_monitor_module.get_system_status()

    def run_powershell_command(self, params):
        return powershell_command_module.run_powershell_command(params)

    def set_reminder(self, params):
        return reminder_module.reminder(params)

    def desktop_control(self, params):
        return desktop_module.desktop_control(params)

    def set_paused(self, paused):
        self.paused = paused

    async def _voice_notification(self, message, priority="normal"):
        await self.inject_runtime_event(message, priority)

    async def inject_runtime_event(self, message: str, priority: str = "normal"):
        """Deliver background events to Gemini Live, even when audio output is paused."""
        payload = f"System Notification ({priority}): {message}"
        if not self.session:
            self._pending_runtime_notifications.append(payload)
            print(f"[FRIDAY DEBUG] [RUNTIME EVENT] queued: {message}")
            return
        try:
            await self.session.send(input=payload, end_of_turn=True)
            print(f"[FRIDAY DEBUG] [RUNTIME EVENT] delivered: {message}")
        except Exception as error:
            self._pending_runtime_notifications.append(payload)
            print(f"[FRIDAY DEBUG] [RUNTIME EVENT] delivery failed: {error}")

    def stop(self):
        self.stop_event.set()
        self._cancel_event.set()
        self.cancel_pending_confirmations()

    def spawn_background_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def cancel_current_action(self) -> str:
        self._cancel_event.set()
        cancelled = 0
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                cancelled += 1
        if self._active_plan:
            self.finish_action_plan(success=False, cancelled=True)
        return f"Cancellation requested for {cancelled} background task(s)."

    def execute_openclaw_tool(self, tool_name: str, args: dict):
        """Execute OpenClaw-selected read-only/core tools through Friday's guards."""
        policy = decision(tool_name, args)
        if policy["tier"] in {"approval_required", "always_confirm"}:
            raise PermissionError(f"OpenClaw cannot execute approval-required tool automatically: {tool_name}. {policy['reason']}")
        if tool_name == "gmail_read":
            return self.google_account.read_emails(args.get("query", "is:unread"), args.get("limit", 10))
        if tool_name == "gmail_thread_read":
            return self.google_account.read_gmail_thread(args.get("thread_id", ""))
        if tool_name == "google_calendar_list":
            return self.google_account.list_calendar_events(args.get("query", ""), args.get("days", 7), args.get("limit", 25))
        if tool_name == "google_calendar_availability":
            return self.google_account.check_calendar_availability(args.get("date", ""), args.get("time", ""), args.get("duration_minutes", 60))
        if tool_name == "manage_tasks":
            return self.task_manager.manage(args.get("action", "list"), **args)
        if tool_name == "schedule_agent":
            action = args.get("action", "list")
            if action == "list":
                return self.agent_scheduler.list()
            if action == "run_now":
                return self.agent_scheduler.run_now(args["schedule_id"])
            if action in {"enable", "disable"}:
                return {"updated": self.agent_scheduler.set_enabled(args["schedule_id"], action == "enable")}
            return self.agent_scheduler.schedule(args["agent_type"], args.get("goal", "Run scheduled agent task."), int(args["interval_seconds"]), args.get("repo_path", "."), int(args.get("max_retries", 3)))
        if tool_name == "get_weather":
            return weather_report_module.get_weather_data(args.get("city", ""))
        if tool_name == "find_flights":
            return flight_finder_module.flight_finder(args)
        if tool_name == "get_system_status":
            return system_monitor_module.get_system_status()
        if tool_name in self.tool_builder.tools:
            return self.tool_builder.execute(tool_name, args)
        raise ValueError(f"OpenClaw tool is registered but not executable through the live boundary: {tool_name}")

    async def run_background_tool(self, tool_name: str, function, params: dict):
        """Run blocking action code off-loop and report its result after completion."""
        ledger_id = agent_dispatcher_module.ledger.start("tool", tool_name, arguments=params)
        try:
            params = {**params, "_cancel_event": self._cancel_event}
            result = await asyncio.to_thread(function, params)
            if self._cancel_event.is_set():
                return

            outcome = self.supervisor.record_execution(tool_name, result)
            if not outcome["ok"]:
                agent_dispatcher_module.ledger.finish(ledger_id, "failed", result)
                self.finish_action_plan(False)
                self_maintenance_module.record_tool_failure(tool_name, str(result))
                await self.notifications.notify("long_running_action", f"{tool_name} failed", f"{tool_name} reported a failed result.", "high")
                if self.session:
                    await self.session.send(
                        input=f"System Notification: {tool_name} reported a failed result. Outcome:\n{result}",
                        end_of_turn=True,
                    )
                return

            self.finish_action_plan(True)
            agent_dispatcher_module.ledger.finish(ledger_id, "done", result)
            await self.notifications.notify("long_running_action", f"{tool_name} complete", f"{tool_name} finished successfully.")
            if self.session:
                await self.session.send(
                    input=f"System Notification: {tool_name} completed. Result:\n{result}",
                    end_of_turn=True,
                )
        except asyncio.CancelledError:
            agent_dispatcher_module.ledger.finish(ledger_id, "cancelled")
            print(f"[FRIDAY DEBUG] [CANCELLED] {tool_name} task cancelled.")
            self.finish_action_plan(False, cancelled=True)
        except Exception as error:
            agent_dispatcher_module.ledger.finish(ledger_id, "failed", error=str(error))
            print(f"[FRIDAY DEBUG] [ERR] {tool_name} background task failed: {error}")
            self.finish_action_plan(False)
            self_maintenance_module.record_tool_failure(tool_name, str(error))
            await self.notifications.notify("long_running_action", f"{tool_name} failed", f"{tool_name} failed: {error}", "high")

    async def cleanup_resources(self):
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        for resource_name in ("audio_stream", "output_stream", "camera_capture"):
            resource = getattr(self, resource_name, None)
            if resource is None:
                continue
            try:
                method = resource.release if resource_name == "camera_capture" else resource.close
                await asyncio.to_thread(method)
            except Exception as error:
                print(f"[FRIDAY DEBUG] [CLEANUP] Failed to close {resource_name}: {error}")
            setattr(self, resource_name, None)

        self.session = None
        self.audio_in_queue = None
        self.out_queue = None
        # Forget any frame we already pushed to a (now dead) session so a
        # reconnect always starts with a clean video dedup state.
        self._last_sent_image_data = None
        
    def resolve_tool_confirmation(self, request_id, confirmed):
        print(f"[FRIDAY DEBUG] [RESOLVE] resolve_tool_confirmation called. ID: {request_id}, Confirmed: {confirmed}")
        if request_id in self._pending_confirmations:
            future = self._pending_confirmations[request_id]
            if not future.done():
                print(f"[FRIDAY DEBUG] [RESOLVE] Future found and pending. Setting result to: {confirmed}")
                future.set_result(confirmed)
            else:
                 print(f"[FRIDAY DEBUG] [WARN] Request {request_id} future already done. Result: {future.result()}")
        else:
            print(f"[FRIDAY DEBUG] [WARN] Confirmation Request {request_id} not found in pending dict. Keys: {list(self._pending_confirmations.keys())}")

    def clear_audio_queue(self):
        """Clears the queue of pending audio chunks to stop playback immediately."""
        try:
            count = 0
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
                count += 1
            if count > 0:
                print(f"[FRIDAY DEBUG] [AUDIO] Cleared {count} chunks from playback queue due to interruption.")
        except Exception as e:
            print(f"[FRIDAY DEBUG] [ERR] Failed to clear audio queue: {e}")

    async def send_frame(self, frame_data):
        # Update the latest frame payload
        if isinstance(frame_data, bytes):
            b64_data = base64.b64encode(frame_data).decode('utf-8')
        else:
            b64_data = frame_data 

        # Store as the designated "next frame to send"
        self._latest_image_payload = {"mime_type": "image/jpeg", "data": b64_data}
        # No event signal needed - listen_audio pulls it

    def set_live_video(self, enabled: bool):
        """Turn continuous webcam streaming to the Live session on or off."""
        self.live_video_enabled = bool(enabled)
        print(f"[FRIDAY DEBUG] [VIDEO] Live vision {'ENABLED' if self.live_video_enabled else 'DISABLED'}")
        if not self.live_video_enabled:
            # Forget what we already sent so a re-enable always starts fresh.
            self._last_sent_image_data = None

    def _should_send_video_frame(self, now: float) -> bool:
        """Decide whether the latest webcam frame should be forwarded now.

        Returns True only when the session is live, vision is enabled, a frame
        is available, that frame is genuinely new, and enough time has elapsed
        since the last send (Gemini Live allows at most ~1 image/second).
        """
        return (
            self.session is not None
            and self.live_video_enabled
            and not self.paused
            and self._latest_image_payload is not None
            and self._latest_image_payload.get("data") != self._last_sent_image_data
            and (now - self._last_video_sent_time) >= VIDEO_SEND_INTERVAL
        )

    async def _send_live_video(self):
        """Continuously forward the user's webcam to the Live session.

        The frontend already downscales and streams frames to the backend via
        ``send_frame``; this task picks up the newest one and pushes it into
        the Gemini Live session at the supported ~1 fps cadence, skipping
        frames that are byte-identical to the last one sent.
        """
        while True:
            if self.paused or not self.live_video_enabled or not self.session or self._latest_image_payload is None:
                await asyncio.sleep(0.2)
                continue

            if not self._should_send_video_frame(time.monotonic()):
                await asyncio.sleep(0.2)
                continue

            payload = self._latest_image_payload
            try:
                await self.session.send(input=payload, end_of_turn=False)
                self._last_sent_image_data = payload.get("data")
                self._last_video_sent_time = time.monotonic()
                print(f"[FRIDAY DEBUG] [VIDEO] Live frame sent to model ({len(payload.get('data', ''))} b64 chars).")
            except Exception as e:
                print(f"[FRIDAY DEBUG] [ERR] Failed to send live video frame: {e}")
                await asyncio.sleep(0.5)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg, end_of_turn=False)

    async def listen_audio(self):
        default_input = sd.default.device[0]

        # Resolve Input Device by Name if provided
        resolved_input_device_index = None
        
        if self.input_device_name:
            print(f"[FRIDAY] Attempting to find input device matching: '{self.input_device_name}'")
            count = len(sd.query_devices())
            best_match = None
            
            for i in range(count):
                try:
                    info = sd.query_devices(i)
                    if info['max_input_channels'] > 0:
                        name = info.get('name', '')
                        # Simple case-insensitive check
                        if self.input_device_name.lower() in name.lower() or name.lower() in self.input_device_name.lower():
                             print(f"   Candidate {i}: {name}")
                             # Prioritize exact match or very close match if possible, but first match is okay for now
                             resolved_input_device_index = i
                             best_match = name
                             break
                except Exception:
                    continue
            
            if resolved_input_device_index is not None:
                print(f"[FRIDAY] Resolved input device '{self.input_device_name}' to index {resolved_input_device_index} ({best_match})")
            else:
                print(f"[FRIDAY] Could not find device matching '{self.input_device_name}'. Checking index...")

        # Fallback to index if Name lookup failed or wasn't provided
        if resolved_input_device_index is None and self.input_device_index is not None:
             try:
                 resolved_input_device_index = int(self.input_device_index)
                 print(f"[FRIDAY] Requesting Input Device Index: {resolved_input_device_index}")
             except ValueError:
                 print(f"[FRIDAY] Invalid device index '{self.input_device_index}', reverting to default.")
                 resolved_input_device_index = None

        if resolved_input_device_index is None:
             print("[FRIDAY] Using Default Input Device")

        try:
            self.audio_stream = await asyncio.to_thread(
                sd.RawInputStream,
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                device=resolved_input_device_index if resolved_input_device_index is not None else default_input,
                blocksize=CHUNK_SIZE,
            )
            await asyncio.to_thread(self.audio_stream.start)
        except OSError as e:
            print(f"[FRIDAY] [ERR] Failed to open audio input stream: {e}")
            print("[FRIDAY] [WARN] Audio features will be disabled. Please check microphone permissions.")
            return

        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        # VAD Constants
        VAD_THRESHOLD = 800 # Adj based on mic sensitivity (800 is conservative for 16-bit)
        SILENCE_DURATION = 0.5 # Seconds of silence to consider "done speaking"
        
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue

            try:
                raw_data, _ = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE)
                data = bytes(raw_data)
                
                # 1. Send Audio
                if self.out_queue:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                
                # 2. VAD Logic for Video
                # rms = audioop.rms(data, 2)
                # Replacement for audioop.rms(data, 2)
                count = len(data) // 2
                if count > 0:
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s**2 for s in shorts)
                    rms = int(math.sqrt(sum_squares / count))
                else:
                    rms = 0
                
                if rms > VAD_THRESHOLD:
                    # Speech Detected
                    self._silence_start_time = None
                    
                    if not self._is_speaking:
                        # NEW Speech Utterance Started
                        self._is_speaking = True
                        self._last_user_speech = time.monotonic()
                        print(f"[FRIDAY DEBUG] [VAD] Speech Detected (RMS: {rms}). Sending Video Frame.")
                        
                        # Send ONE frame
                        if self._latest_image_payload and self.out_queue:
                            await self.out_queue.put(self._latest_image_payload)
                        else:
                            print(f"[FRIDAY DEBUG] [VAD] No video frame available to send.")
                            
                else:
                    # Silence
                    if self._is_speaking:
                        if self._silence_start_time is None:
                            self._silence_start_time = time.time()
                        
                        elif time.time() - self._silence_start_time > SILENCE_DURATION:
                            # Silence confirmed, reset state
                            print(f"[FRIDAY DEBUG] [VAD] Silence detected. Resetting speech state.")
                            self._is_speaking = False
                            self._silence_start_time = None

            except Exception as e:
                print(f"Error reading audio: {e}")
                await asyncio.sleep(0.1)

    async def handle_cad_request(self, prompt):
        print(f"[FRIDAY DEBUG] [CAD] Background Task Started: handle_cad_request('{prompt}')")
        if self._cancel_event.is_set():
            self.finish_action_plan(success=False, cancelled=True)
            return
        if self.on_cad_status:
            self.on_cad_status("generating")
            
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[FRIDAY DEBUG] [CAD] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User (Optional, or rely on update)
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[FRIDAY DEBUG] [ERR] Failed to notify auto-project: {e}")

        # Get project cad folder path
        cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
        
        # Call the secondary agent with project path
        cad_data = await self.cad_agent.generate_prototype(prompt, output_dir=cad_output_dir)
        if self._cancel_event.is_set():
            self.finish_action_plan(success=False, cancelled=True)
            return
        
        if cad_data:
            print(f"[FRIDAY DEBUG] [OK] CadAgent returned data successfully.")
            print(f"[FRIDAY DEBUG] [INFO] Data Check: {len(cad_data.get('vertices', []))} vertices, {len(cad_data.get('edges', []))} edges.")
            
            if self.on_cad_data:
                print(f"[FRIDAY DEBUG] [SEND] Dispatching data to frontend callback...")
                self.on_cad_data(cad_data)
                print(f"[FRIDAY DEBUG] [SENT] Dispatch complete.")
            
            # Save to Project
            if 'file_path' in cad_data:
                self.project_manager.save_cad_artifact(cad_data['file_path'], prompt)
            else:
                 # Fallback (legacy support)
                 self.project_manager.save_cad_artifact("output.stl", prompt)

            # Notify the model that the task is done - this triggers speech about completion
            completion_msg = "System Notification: CAD generation is complete! The 3D model is now displayed for the user. Let them know it's ready."
            try:
                await self.session.send(input=completion_msg, end_of_turn=True)
                print(f"[FRIDAY DEBUG] [NOTE] Sent completion notification to model.")
                self.finish_action_plan(True)
            except Exception as e:
                 print(f"[FRIDAY DEBUG] [ERR] Failed to send completion notification: {e}")

        else:
            print(f"[FRIDAY DEBUG] [ERR] CadAgent returned None.")
            # Optionally notify failure
            try:
                await self.session.send(input="System Notification: CAD generation failed.", end_of_turn=True)
            except Exception:
                pass
            self.finish_action_plan(False)



    async def handle_write_file(self, path, content):
        print(f"[FRIDAY DEBUG] [FS] Writing file: '{path}'")
        
        # Auto-create project if stuck in temp
        if self.project_manager.current_project == "temp":
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_project_name = f"Project_{timestamp}"
            print(f"[FRIDAY DEBUG] [FS] Auto-creating project: {new_project_name}")
            
            success, msg = self.project_manager.create_project(new_project_name)
            if success:
                self.project_manager.switch_project(new_project_name)
                # Notify User
                try:
                    await self.session.send(input=f"System Notification: Automatic Project Creation. Switched to new project '{new_project_name}'.", end_of_turn=False)
                    if self.on_project_update:
                         self.on_project_update(new_project_name)
                except Exception as e:
                    print(f"[FRIDAY DEBUG] [ERR] Failed to notify auto-project: {e}")
        
        # Force path to be relative to current project
        # If absolute path is provided, we try to strip it or just ignore it and use basename
        filename = os.path.basename(path)
        
        # If path contained subdirectories (e.g. "backend/server.py"), preserving that structure might be desired IF it's within the project.
        # But for safety, and per user request to "always create the file in the project", 
        # we will root it in the current project path.
        
        current_project_path = self.project_manager.get_current_project_path()
        final_path = current_project_path / filename # Simple flat structure for now, or allow relative?
        
        # If the user specifically wanted a subfolder, they might have provided "sub/file.txt".
        # Let's support relative paths if they don't start with /
        if not os.path.isabs(path):
             final_path = current_project_path / path
        
        print(f"[FRIDAY DEBUG] [FS] Resolved path: '{final_path}'")

        try:
            # Ensure parent exists
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            self.undo_manager.record_file_write(str(final_path))
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(content)
            result = f"File '{final_path.name}' written successfully to project '{self.project_manager.current_project}'."
        except Exception as e:
            result = f"Failed to write file '{path}': {str(e)}"

        print(f"[FRIDAY DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[FRIDAY DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_read_directory(self, path):
        print(f"[FRIDAY DEBUG] [FS] Reading directory: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"Directory '{path}' does not exist."
            else:
                items = os.listdir(path)
                result = f"Contents of '{path}': {', '.join(items)}"
        except Exception as e:
            result = f"Failed to read directory '{path}': {str(e)}"

        print(f"[FRIDAY DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[FRIDAY DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_read_file(self, path):
        print(f"[FRIDAY DEBUG] [FS] Reading file: '{path}'")
        try:
            if not os.path.exists(path):
                result = f"File '{path}' does not exist."
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                result = f"Content of '{path}':\n{content}"
        except Exception as e:
            result = f"Failed to read file '{path}': {str(e)}"

        print(f"[FRIDAY DEBUG] [FS] Result: {result}")
        try:
             await self.session.send(input=f"System Notification: {result}", end_of_turn=True)
        except Exception as e:
             print(f"[FRIDAY DEBUG] [ERR] Failed to send fs result: {e}")

    async def handle_web_agent_request(self, prompt):
        print(f"[FRIDAY DEBUG] [WEB] Web Agent Task: '{prompt}'")
        if self._cancel_event.is_set():
            self.finish_action_plan(success=False, cancelled=True)
            return
        
        async def update_frontend(image_b64, log_text):
            if self.on_web_data:
                 self.on_web_data({"image": image_b64, "log": log_text})
                 
        # Run the web agent and wait for it to return
        result = await self.web_agent.run_task(prompt, update_callback=update_frontend)
        if self._cancel_event.is_set():
            self.finish_action_plan(success=False, cancelled=True)
            return
        print(f"[FRIDAY DEBUG] [WEB] Web Agent Task Returned: {result}")
        
        # Send the final result back to the main model
        try:
            await self.session.send(input=f"System Notification: Web Agent has finished.\nResult: {result}", end_of_turn=True)
            self.finish_action_plan(True)
        except Exception as e:
            print(f"[FRIDAY DEBUG] [ERR] Failed to send web agent result to model: {e}")

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    # 1. Handle Audio Data
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        # NOTE: 'continue' removed here to allow processing transcription/tools in same packet

                    # 2. Handle Transcription (User & Model)
                    if response.server_content:
                        if response.server_content.input_transcription:
                            transcript = response.server_content.input_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_input_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_input_transcription):
                                        delta = transcript[len(self._last_input_transcription):]
                                    self._last_input_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # User is speaking, so interrupt model playback!
                                        self.clear_audio_queue()

                                        # Send to frontend (Streaming)
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "User", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "User":
                                            # Flush previous if exists
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                                self.memory_manager.append_message(self.chat_buffer["sender"], self.chat_buffer["text"], project=self.project_manager.current_project)
                                            # Start new
                                            self.chat_buffer = {"sender": "User", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        if response.server_content.output_transcription:
                            transcript = response.server_content.output_transcription.text
                            if transcript:
                                # Skip if this is an exact duplicate event
                                if transcript != self._last_output_transcription:
                                    # Calculate delta (Gemini may send cumulative or chunk-based text)
                                    delta = transcript
                                    if transcript.startswith(self._last_output_transcription):
                                        delta = transcript[len(self._last_output_transcription):]
                                    self._last_output_transcription = transcript
                                    
                                    # Only send if there's new text
                                    if delta:
                                        # Send to frontend (Streaming)
                                        if self.on_transcription:
                                             self.on_transcription({"sender": "FRIDAY", "text": delta})
                                        
                                        # Buffer for Logging
                                        if self.chat_buffer["sender"] != "FRIDAY":
                                            # Flush previous
                                            if self.chat_buffer["sender"] and self.chat_buffer["text"].strip():
                                                self.project_manager.log_chat(self.chat_buffer["sender"], self.chat_buffer["text"])
                                                self.memory_manager.append_message(self.chat_buffer["sender"], self.chat_buffer["text"], project=self.project_manager.current_project)
                                            # Start new
                                            self.chat_buffer = {"sender": "FRIDAY", "text": delta}
                                        else:
                                            # Append
                                            self.chat_buffer["text"] += delta
                        
                        # Flush buffer on turn completion if needed, 
                        # but usually better to wait for sender switch or explicit end.
                        # We can also check turn_complete signal if available in response.server_content.model_turn etc

                    # 3. Handle Tool Calls
                    if response.tool_call:
                        print("The tool was called")
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            if fc.name in ["generate_cad", "run_web_agent", "write_file", "read_directory", "read_file", "create_project", "switch_project", "list_projects", "search_memory", "list_smart_devices", "control_light", "discover_printers", "print_stl", "get_print_status", "iterate_cad", "computer_control", "computer_settings", "manage_files", "open_application", "get_system_status", "get_local_time", "gmail_read", "gmail_thread_read", "gmail_create_draft", "google_contacts_read", "google_contacts_import", "google_contacts_sync", "sync_google_services", "google_drive_list", "google_calendar_availability", "build_custom_tool", "test_custom_tool", "run_custom_tool", "build_agent", "test_agent", "manage_plugins", "openclaw_plan", "openclaw_execute", "openclaw_capabilities", "openclaw_delegate", "execution_history", "autonomy_status", "approve_autonomy_proposal", "get_weather", "google_calendar_create", "google_calendar_list", "google_calendar_update", "google_calendar_delete", "google_calendar_recurring", "set_reminder", "desktop_control", "web_search", "send_message", "youtube_video", "browser_control", "code_helper", "build_project", "find_flights", "game_updater", "process_file", "manage_monitors", "contacts_manager", "mute_alert_category", "undo_last_action", "manage_uploads", "cancel_current_task", "self_maintenance", "run_powershell_command", "git_workflow", "deploy_agent", "schedule_agent", "manage_tasks", "run_routine"]:
                                prompt = fc.args.get("prompt", "") # Prompt is not present for all tools
                                self.start_action_plan(fc.name, fc.args)

                                precondition_error = self.check_tool_preconditions(fc.name, fc.args)
                                if precondition_error:
                                    print(f"[FRIDAY DEBUG] [PRECONDITION] {fc.name}: {precondition_error}")
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={"result": f"Tool not executed: {precondition_error}"},
                                    ))
                                    self.finish_action_plan(False)
                                    continue

                                if self._active_plan:
                                    self._update_plan_step(0, "done")
                                    self._update_plan_step(1, "done")
                                    self._update_plan_step(2, "active")
                                
                                policy = decision(fc.name, fc.args)
                                confirmation_required = policy["tier"] in {"approval_required", "always_confirm"}

                                if not confirmation_required:
                                    print(f"[FRIDAY DEBUG] [TOOL] Permission check: '{fc.name}' -> AUTO-ALLOW")
                                    # Skip confirmation block and jump to execution
                                    pass
                                elif not self.on_tool_confirmation:
                                    if confirmation_required:
                                        result = f"Safety stop: explicit confirmation is required. {policy['reason']}"
                                        print(f"[FRIDAY DEBUG] [BLOCKED] {result}")
                                        function_responses.append(types.FunctionResponse(
                                            id=fc.id, name=fc.name, response={"result": result}
                                        ))
                                        self.finish_action_plan(False)
                                        continue
                                    print(f"[FRIDAY DEBUG] [TOOL] No confirmation callback configured for '{fc.name}' -> AUTO-ALLOW")
                                else:
                                    # Confirmation Logic
                                    import uuid
                                    request_id = str(uuid.uuid4())
                                    print(f"[FRIDAY DEBUG] [STOP] Requesting confirmation for '{fc.name}' (ID: {request_id})")
                                    
                                    future = asyncio.Future()
                                    self._pending_confirmations[request_id] = future
                                    
                                    self.on_tool_confirmation({
                                        "id": request_id, 
                                        "tool": fc.name, 
                                        "args": fc.args
                                    })
                                    
                                    timed_out = False
                                    try:
                                        # Wait for user response, then expire safely.
                                        confirmed = await asyncio.wait_for(future, timeout=30)
                                    except asyncio.TimeoutError:
                                        timed_out = True
                                        confirmed = False
                                        print(f"[FRIDAY DEBUG] [TIMEOUT] Confirmation expired for '{fc.name}' (ID: {request_id})")
                                        if self.on_confirmation_expired:
                                            self.on_confirmation_expired({
                                                "id": request_id,
                                                "tool": fc.name,
                                            })

                                    finally:
                                        self._pending_confirmations.pop(request_id, None)

                                    print(f"[FRIDAY DEBUG] [CONFIRM] Request {request_id} resolved. Confirmed: {confirmed}")

                                    if not confirmed:
                                        print(f"[FRIDAY DEBUG] [DENY] Tool call '{fc.name}' denied by user.")
                                        function_response = types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={
                                                "result": "Confirmation timed out; the tool was not executed." if timed_out else "User denied the request to use this tool.",
                                            }
                                        )
                                        function_responses.append(function_response)
                                        self.finish_action_plan(False)
                                        continue

                                # If confirmed (or no callback configured, or auto-allowed), proceed
                                if fc.name == "generate_cad":
                                    print(f"\n[FRIDAY DEBUG] --------------------------------------------------")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call Detected: 'generate_cad'")
                                    print(f"[FRIDAY DEBUG] [IN] Arguments: prompt='{prompt}'")
                                    
                                    self._plan_pending = True
                                    self.spawn_background_task(self.handle_cad_request(prompt))
                                    # No function response needed - model already acknowledged when user asked
                                
                                elif fc.name == "run_web_agent":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'run_web_agent' with prompt='{prompt}'")
                                    self._plan_pending = True
                                    self.spawn_background_task(self.handle_web_agent_request(prompt))
                                    
                                    result_text = "Web Navigation started. Do not reply to this message."
                                    function_response = types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={
                                            "result": result_text,
                                        }
                                    )
                                    print(f"[FRIDAY DEBUG] [RESPONSE] Sending function response: {function_response}")
                                    function_responses.append(function_response)



                                elif fc.name == "write_file":
                                    path = fc.args["path"]
                                    content = fc.args["content"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'write_file' path='{path}'")
                                    self.spawn_background_task(self.handle_write_file(path, content))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Writing file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_directory":
                                    path = fc.args["path"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'read_directory' path='{path}'")
                                    self.spawn_background_task(self.handle_read_directory(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading directory..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "read_file":
                                    path = fc.args["path"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'read_file' path='{path}'")
                                    self.spawn_background_task(self.handle_read_file(path))
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": "Reading file..."}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "create_project":
                                    name = fc.args["name"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'create_project' name='{name}'")
                                    success, msg = self.project_manager.create_project(name)
                                    if success:
                                        # Auto-switch to the newly created project
                                        self.project_manager.switch_project(name)
                                        msg += f" Switched to '{name}'."
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "switch_project":
                                    name = fc.args["name"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'switch_project' name='{name}'")
                                    previous_project = self.project_manager.current_project
                                    success, msg = self.project_manager.switch_project(name)
                                    if success:
                                        self.undo_manager.record_project_switch(previous_project)
                                        if self.on_project_update:
                                            self.on_project_update(name)
                                        # Gather project context and send to AI (silently, no response expected)
                                        context = self.project_manager.get_project_context()
                                        print(f"[FRIDAY DEBUG] [PROJECT] Sending project context to AI ({len(context)} chars)")
                                        try:
                                            await self.session.send(input=f"System Notification: {msg}\n\n{context}", end_of_turn=False)
                                        except Exception as e:
                                            print(f"[FRIDAY DEBUG] [ERR] Failed to send project context: {e}")
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": msg}
                                    )
                                    function_responses.append(function_response)
                                
                                elif fc.name == "list_projects":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'list_projects'")
                                    projects = self.project_manager.list_projects()
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": f"Available projects: {', '.join(projects)}"}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "search_memory":
                                    query = fc.args["query"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'search_memory' query='{query}'")
                                    matches = self.memory_manager.search(
                                        query,
                                        limit=15,
                                        project=self.project_manager.current_project,
                                    )
                                    if matches:
                                        result_lines = [f"[{m.get('timestamp')}] {m.get('sender')}: {m.get('text')}" for m in matches]
                                        result = "Found in long-term memory:\n" + "\n".join(result_lines)
                                    else:
                                        result = "No matching memories found."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "list_smart_devices":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'list_smart_devices'")
                                    # Use cached devices directly for speed
                                    # devices_dict is {ip: SmartDevice}
                                    
                                    dev_summaries = []
                                    frontend_list = []
                                    
                                    for ip, d in self.kasa_agent.devices.items():
                                        dev_type = "unknown"
                                        if d.is_bulb: dev_type = "bulb"
                                        elif d.is_plug: dev_type = "plug"
                                        elif d.is_strip: dev_type = "strip"
                                        elif d.is_dimmer: dev_type = "dimmer"
                                        
                                        # Format for Model
                                        info = f"{d.alias} (IP: {ip}, Type: {dev_type})"
                                        if d.is_on:
                                            info += " [ON]"
                                        else:
                                            info += " [OFF]"
                                        dev_summaries.append(info)
                                        
                                        # Format for Frontend
                                        frontend_list.append({
                                            "ip": ip,
                                            "alias": d.alias,
                                            "model": d.model,
                                            "type": dev_type,
                                            "is_on": d.is_on,
                                            "brightness": d.brightness if d.is_bulb or d.is_dimmer else None,
                                            "hsv": d.hsv if d.is_bulb and d.is_color else None,
                                            "has_color": d.is_color if d.is_bulb else False,
                                            "has_brightness": d.is_dimmable if d.is_bulb or d.is_dimmer else False
                                        })
                                    
                                    result_str = "No devices found in cache."
                                    if dev_summaries:
                                        result_str = "Found Devices (Cached):\n" + "\n".join(dev_summaries)
                                    
                                    # Trigger frontend update
                                    if self.on_device_update:
                                        self.on_device_update(frontend_list)

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "control_light":
                                    target = fc.args["target"]
                                    action = fc.args["action"]
                                    brightness = fc.args.get("brightness")
                                    color = fc.args.get("color")
                                    
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'control_light' Target='{target}' Action='{action}'")
                                    
                                    result_msg = f"Action '{action}' on '{target}' failed."
                                    success = False
                                    
                                    if action == "turn_on":
                                        success = await self.kasa_agent.turn_on(target)
                                        if success:
                                            result_msg = f"Turned ON '{target}'."
                                    elif action == "turn_off":
                                        success = await self.kasa_agent.turn_off(target)
                                        if success:
                                            result_msg = f"Turned OFF '{target}'."
                                    elif action == "set":
                                        success = True
                                        result_msg = f"Updated '{target}':"
                                    
                                    # Apply extra attributes if 'set' or if we just turned it on and want to set them too
                                    if success or action == "set":
                                        if brightness is not None:
                                            sb = await self.kasa_agent.set_brightness(target, brightness)
                                            if sb:
                                                result_msg += f" Set brightness to {brightness}."
                                        if color is not None:
                                            sc = await self.kasa_agent.set_color(target, color)
                                            if sc:
                                                result_msg += f" Set color to {color}."

                                    # Notify Frontend of State Change
                                    if success:
                                        # We don't need full discovery, just refresh known state or push update
                                        # But for simplicity, let's get the standard list representation
                                        # KasaAgent updates its internal state on control, so we can rebuild the list
                                        
                                        # Quick rebuild of list from internal dict
                                        updated_list = []
                                        for ip, dev in self.kasa_agent.devices.items():
                                            # We need to ensure we have the correct dict structure expected by frontend
                                            # We duplicate logic from KasaAgent.discover_devices a bit, but that's okay for now or we can add a helper
                                            # Ideally KasaAgent has a 'get_devices_list()' method.
                                            # Use the cached objects in self.kasa_agent.devices
                                            
                                            dev_type = "unknown"
                                            if dev.is_bulb: dev_type = "bulb"
                                            elif dev.is_plug: dev_type = "plug"
                                            elif dev.is_strip: dev_type = "strip"
                                            elif dev.is_dimmer: dev_type = "dimmer"

                                            d_info = {
                                                "ip": ip,
                                                "alias": dev.alias,
                                                "model": dev.model,
                                                "type": dev_type,
                                                "is_on": dev.is_on,
                                                "brightness": dev.brightness if dev.is_bulb or dev.is_dimmer else None,
                                                "hsv": dev.hsv if dev.is_bulb and dev.is_color else None,
                                                "has_color": dev.is_color if dev.is_bulb else False,
                                                "has_brightness": dev.is_dimmable if dev.is_bulb or dev.is_dimmer else False
                                            }
                                            updated_list.append(d_info)
                                            
                                        if self.on_device_update:
                                            self.on_device_update(updated_list)
                                    else:
                                        # Report Error
                                        if self.on_error:
                                            self.on_error(result_msg)

                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_msg}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "discover_printers":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'discover_printers'")
                                    printers = await self.printer_agent.discover_printers()
                                    # Format for model
                                    if printers:
                                        printer_list = []
                                        for p in printers:
                                            printer_list.append(f"{p['name']} ({p['host']}:{p['port']}, type: {p['printer_type']})")
                                        result_str = "Found Printers:\n" + "\n".join(printer_list)
                                    else:
                                        result_str = "No printers found on network. Ensure printers are on and running OctoPrint/Moonraker."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "print_stl":
                                    stl_path = fc.args["stl_path"]
                                    printer = fc.args["printer"]
                                    profile = fc.args.get("profile")
                                    
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'print_stl' STL='{stl_path}' Printer='{printer}'")
                                    
                                    # Resolve 'current' to project STL
                                    if stl_path.lower() == "current":
                                        stl_path = "output.stl" # Let printer agent resolve it in root_path

                                    # Get current project path
                                    project_path = str(self.project_manager.get_current_project_path())
                                    
                                    result = await self.printer_agent.print_stl(
                                        stl_path, 
                                        printer, 
                                        profile, 
                                        root_path=project_path
                                    )
                                    result_str = result.get("message", "Unknown result")
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "get_print_status":
                                    printer = fc.args["printer"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'get_print_status' Printer='{printer}'")
                                    
                                    status = await self.printer_agent.get_print_status(printer)
                                    if status:
                                        result_str = f"Printer: {status.printer}\n"
                                        result_str += f"State: {status.state}\n"
                                        result_str += f"Progress: {status.progress_percent:.1f}%\n"
                                        if status.time_remaining:
                                            result_str += f"Time Remaining: {status.time_remaining}\n"
                                        if status.time_elapsed:
                                            result_str += f"Time Elapsed: {status.time_elapsed}\n"
                                        if status.filename:
                                            result_str += f"File: {status.filename}\n"
                                        if status.temperatures:
                                            temps = status.temperatures
                                            if "hotend" in temps:
                                                result_str += f"Hotend: {temps['hotend']['current']:.0f}°C / {temps['hotend']['target']:.0f}°C\n"
                                            if "bed" in temps:
                                                result_str += f"Bed: {temps['bed']['current']:.0f}°C / {temps['bed']['target']:.0f}°C"
                                    else:
                                        result_str = f"Could not get status for printer '{printer}'. Ensure it is discovered first."
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "iterate_cad":
                                    prompt = fc.args["prompt"]
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'iterate_cad' Prompt='{prompt}'")
                                    
                                    # Emit status
                                    if self.on_cad_status:
                                        self.on_cad_status("generating")
                                    
                                    # Get project cad folder path
                                    cad_output_dir = str(self.project_manager.get_current_project_path() / "cad")
                                    
                                    # Call CadAgent to iterate on the design
                                    cad_data = await self.cad_agent.iterate_prototype(prompt, output_dir=cad_output_dir)
                                    
                                    if cad_data:
                                        print(f"[FRIDAY DEBUG] [OK] CadAgent iteration returned data successfully.")
                                        
                                        # Dispatch to frontend
                                        if self.on_cad_data:
                                            print(f"[FRIDAY DEBUG] [SEND] Dispatching iterated CAD data to frontend...")
                                            self.on_cad_data(cad_data)
                                            print(f"[FRIDAY DEBUG] [SENT] Dispatch complete.")
                                        
                                        # Save to Project
                                        self.project_manager.save_cad_artifact("output.stl", f"Iteration: {prompt}")
                                        
                                        result_str = f"Successfully iterated design: {prompt}. The updated 3D model is now displayed."
                                    else:
                                        print(f"[FRIDAY DEBUG] [ERR] CadAgent iteration returned None.")
                                        result_str = f"Failed to iterate design with prompt: {prompt}"
                                    
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "computer_control":
                                    action = fc.args.get("action", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'computer_control' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    result_str = await asyncio.to_thread(computer_control_module.computer_control, params)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "computer_settings":
                                    action = fc.args.get("action", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'computer_settings' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    if action in ("volume_up", "volume_down", "volume_set"):
                                        previous_value = await asyncio.to_thread(computer_settings_module.get_current_volume)
                                        if previous_value is not None:
                                            self.undo_manager.record_setting("volume_set", previous_value)
                                    elif action in ("brightness_up", "brightness_down"):
                                        previous_value = await asyncio.to_thread(computer_settings_module.get_current_brightness)
                                        if previous_value is not None:
                                            self.undo_manager.record_setting("brightness_set", previous_value)
                                    result_str = await asyncio.to_thread(computer_settings_module.computer_settings, params)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "manage_files":
                                    action = fc.args.get("action", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'manage_files' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    result_str = await asyncio.to_thread(file_controller_module.file_controller, params)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "open_application":
                                    app_name = fc.args.get("app_name", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'open_application' app_name='{app_name}'")
                                    result_str = await asyncio.to_thread(open_app_module.open_app, {"app_name": app_name})
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "get_system_status":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'get_system_status'")
                                    status = await asyncio.to_thread(system_monitor_module.get_system_status)
                                    result_str = (
                                        f"CPU: {status['cpu_percent']}%, RAM: {status['ram_percent']}% "
                                        f"({status['ram_used_gb']}/{status['ram_total_gb']} GB), "
                                        f"GPU: {status['gpu_percent']}%, CPU Temp: {status['cpu_temp_c']}°C, "
                                        f"Uptime: {status['uptime']}, Processes: {status['process_count']}"
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "get_local_time":
                                    local_time = datetime.now(ZoneInfo("Africa/Johannesburg"))
                                    result_str = local_time.strftime("%A, %d %B %Y at %H:%M:%S SAST (Johannesburg, South Africa)")
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "google_calendar_create":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'google_calendar_create'")
                                    try:
                                        event = await asyncio.to_thread(
                                            self.google_account.create_calendar_event,
                                            fc.args.get("title", "Friday reminder"),
                                            fc.args.get("date", ""),
                                            fc.args.get("time", ""),
                                            fc.args.get("duration_minutes", 30),
                                            fc.args.get("description", ""),
                                        )
                                        result_str = json.dumps({"success": True, "event": event}, ensure_ascii=False)
                                        if self.on_notification:
                                            self.on_notification({"category": "google_calendar", "title": "Google Calendar", "message": "Event created.", "service": "calendar", "items": [event]})
                                    except Exception as exc:
                                        result_str = f"Google Calendar unavailable: {exc}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "google_calendar_list":
                                    try:
                                        events = await asyncio.to_thread(self.google_account.list_calendar_events, fc.args.get("query", ""), fc.args.get("days", 7), fc.args.get("limit", 25))
                                        result_str = json.dumps(events, ensure_ascii=False)
                                        if self.on_notification:
                                            self.on_notification({"category": "google_calendar", "title": "Google Calendar", "message": f"Found {len(events)} upcoming event(s).", "service": "calendar", "items": events})
                                    except Exception as exc:
                                        result_str = f"Google Calendar unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_calendar_availability":
                                    try:
                                        availability = await asyncio.to_thread(
                                            self.google_account.check_calendar_availability,
                                            fc.args.get("date", ""), fc.args.get("time", ""), fc.args.get("duration_minutes", 60)
                                        )
                                        result_str = json.dumps(availability, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Google Calendar availability unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_calendar_update":
                                    try:
                                        event = await asyncio.to_thread(self.google_account.update_calendar_event, fc.args.get("event_id", ""), fc.args.get("title"), fc.args.get("date"), fc.args.get("time"), fc.args.get("duration_minutes", 30), fc.args.get("description"))
                                        result_str = json.dumps({"success": True, "event": event}, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Google Calendar update unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_calendar_delete":
                                    try:
                                        await asyncio.to_thread(self.google_account.delete_calendar_event, fc.args.get("event_id", ""))
                                        result_str = json.dumps({"success": True, "deleted": fc.args.get("event_id", "")})
                                    except Exception as exc:
                                        result_str = f"Google Calendar delete unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_calendar_recurring":
                                    try:
                                        event = await asyncio.to_thread(self.google_account.create_recurring_event, fc.args.get("title", "Friday event"), fc.args.get("date", ""), fc.args.get("time", ""), fc.args.get("recurrence", ""), fc.args.get("duration_minutes", 30), fc.args.get("description", ""))
                                        result_str = json.dumps({"success": True, "event": event}, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Recurring Google Calendar event unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "mute_alert_category":
                                    action = fc.args.get("action", "").lower().strip()
                                    category = fc.args.get("category", "").lower().strip()
                                    if action == "mute":
                                        result_str = self.system_monitor.mute_category(category)
                                    elif action == "unmute":
                                        result_str = self.system_monitor.unmute_category(category)
                                    elif action == "enable":
                                        result_str = self.system_monitor.set_alerts_enabled(True)
                                    elif action == "disable":
                                        result_str = self.system_monitor.set_alerts_enabled(False)
                                    elif action == "list":
                                        muted = ", ".join(sorted(self.system_monitor.muted_categories)) or "none"
                                        state = "enabled" if self.system_monitor.alerts_enabled else "disabled"
                                        result_str = f"System alerts are {state}; muted categories: {muted}."
                                    else:
                                        result_str = f"Unknown alert control action: '{action}'"
                                    if self.on_alert_settings_update:
                                        self.on_alert_settings_update({
                                            "system_alerts_enabled": self.system_monitor.alerts_enabled,
                                            "muted_alert_categories": sorted(self.system_monitor.muted_categories),
                                        })
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "undo_last_action":
                                    result_str = await asyncio.to_thread(
                                        self.undo_manager.undo_last,
                                        desktop_module=desktop_module,
                                        computer_settings_module=computer_settings_module,
                                        project_manager=self.project_manager,
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "manage_uploads":
                                    action = fc.args.get("action", "").lower().strip()
                                    path = fc.args.get("path")
                                    if action == "list":
                                        uploads = self.memory_manager.list_uploads()
                                        result_str = json.dumps(uploads, ensure_ascii=False) if uploads else "No uploaded files found."
                                    elif action == "save":
                                        result_str = self.memory_manager.save_upload(path or "")
                                    elif action == "forget":
                                        result_str = self.memory_manager.forget_uploads(path=path, temporary_only=not bool(path))
                                    elif action == "cleanup":
                                        result_str = self.memory_manager.cleanup_expired_uploads()
                                    else:
                                        result_str = f"Unknown upload action: '{action}'"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "cancel_current_task":
                                    result_str = self.cancel_current_action()
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "self_maintenance":
                                    action = fc.args.get("action", "full_check")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'self_maintenance' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("self_maintenance", self_maintenance_module.self_maintenance, params))
                                    result_str = f"Self-maintenance ({action}) started. This can take a few minutes."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "run_powershell_command":
                                    command = fc.args.get("command", "")
                                    cwd = fc.args.get("cwd")
                                    timeout = fc.args.get("timeout", 120)
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'run_powershell_command' command='{command[:120]}'")
                                    params = {"command": command, "cwd": cwd, "timeout": timeout}
                                    result_str = await asyncio.to_thread(
                                        powershell_command_module.run_powershell_command,
                                        params,
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "git_workflow":
                                    action = fc.args.get("action", "status")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'git_workflow' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    result_str = await asyncio.to_thread(git_workflow_module.git_workflow, params)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "deploy_agent":
                                    action = fc.args.get("action", "deploy")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'deploy_agent' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    # Deploying/polling/listing/cancelling agents is instantaneous (thread-based agents
                                    # run independently), so this never blocks the tool-call loop.
                                    result = agent_dispatcher_module.agent_dispatcher_action(params)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "schedule_agent":
                                    action = fc.args.get("action", "list").lower()
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'schedule_agent' action='{action}'")
                                    if action == "schedule":
                                        result = self.agent_scheduler.schedule(
                                            fc.args["agent_type"],
                                            fc.args.get("goal", "Run scheduled agent task."),
                                            int(fc.args["interval_seconds"]),
                                            fc.args.get("repo_path", "."),
                                            int(fc.args.get("max_retries", 3)),
                                        )
                                    elif action == "cancel":
                                        result = {"cancelled": self.agent_scheduler.cancel(fc.args["schedule_id"])}
                                    elif action in {"enable", "disable"}:
                                        result = {"updated": self.agent_scheduler.set_enabled(fc.args["schedule_id"], action == "enable")}
                                    elif action == "run_now":
                                        result = self.agent_scheduler.run_now(fc.args["schedule_id"])
                                    elif action == "list":
                                        result = self.agent_scheduler.list()
                                    else:
                                        result = {"error": "Unsupported schedule action. Use schedule, list, cancel, enable, disable, or run_now."}
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}
                                    ))

                                elif fc.name == "execution_history":
                                    result = agent_dispatcher_module.ledger.list(int(fc.args.get("limit", 50)))
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False, default=str)}
                                    ))

                                elif fc.name == "autonomy_status":
                                    result = self.autonomy_pipeline.run_cycle()
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False, default=str)}
                                    ))

                                elif fc.name == "approve_autonomy_proposal":
                                    try:
                                        result = self.autonomy_pipeline.approve(fc.args.get("proposal_id", ""))
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False, default=str)}
                                    ))

                                elif fc.name == "manage_tasks":
                                    action = fc.args.get("action", "list").lower()
                                    try:
                                        if action == "plan_week":
                                            result = {"tasks": self.task_manager.list("open"), "overdue": self.task_manager.overdue(), "message": "Use these open tasks and deadlines to plan the week."}
                                        else:
                                            result = self.task_manager.manage(action, **dict(fc.args))
                                        if action in {"create", "create_from_email", "complete"} and self.on_notification:
                                            title = "Task completed" if action == "complete" else "Task created"
                                            message = result.get("title", "Task updated") if isinstance(result, dict) else "Task updated"
                                            self.on_notification({"category": "tasks", "title": title, "message": message, "tasks": self.task_manager.list("open")})
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}
                                    ))

                                elif fc.name == "get_weather":
                                    city = fc.args.get("city", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'get_weather' city='{city}'")
                                    weather_card = None
                                    try:
                                        weather_card = await asyncio.to_thread(weather_report_module.get_weather_data, city)
                                    except Exception:
                                        pass
                                    if weather_card and self.on_notification:
                                        self.on_notification({"category": "weather", "title": "Weather", "message": weather_card["summary"], "weather": weather_card})
                                    result_str = await asyncio.to_thread(
                                        weather_report_module.weather_action,
                                        {"city": city, "time": fc.args.get("time", "today")}
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "set_reminder":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'set_reminder' date='{fc.args.get('date')}' time='{fc.args.get('time')}'")
                                    result_str = await asyncio.to_thread(
                                        reminder_module.reminder,
                                        {"date": fc.args.get("date", ""), "time": fc.args.get("time", ""), "message": fc.args.get("message", "Reminder")}
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "desktop_control":
                                    action = fc.args.get("action", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'desktop_control' action='{action}'")
                                    # Dispatch to an explicit whitelist of safe functions only - deliberately
                                    # bypassing desktop_control()'s fallback that generates and exec()s AI code.
                                    if action == "wallpaper":
                                        previous_wallpaper = await asyncio.to_thread(desktop_module.get_current_wallpaper)
                                        result_str = await asyncio.to_thread(desktop_module.set_wallpaper, fc.args.get("path", ""))
                                        if not result_str.lower().startswith("no ") and not result_str.lower().startswith("could not"):
                                            self.undo_manager.record_wallpaper(previous_wallpaper)
                                    elif action == "wallpaper_url":
                                        result_str = await asyncio.to_thread(desktop_module.set_wallpaper_from_url, fc.args.get("url", ""))
                                    elif action == "current_wallpaper":
                                        result_str = await asyncio.to_thread(desktop_module.get_current_wallpaper)
                                    elif action == "organize":
                                        result_str = await asyncio.to_thread(desktop_module.organize_desktop, fc.args.get("mode", "by_type"))
                                    elif action == "clean":
                                        result_str = await asyncio.to_thread(desktop_module.clean_desktop)
                                    elif action == "list":
                                        result_str = await asyncio.to_thread(desktop_module.list_desktop)
                                    elif action == "stats":
                                        result_str = await asyncio.to_thread(desktop_module.get_desktop_stats)
                                    else:
                                        result_str = f"Unknown desktop action: '{action}'"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "web_search":
                                    query = fc.args.get("query", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'web_search' query='{query}'")
                                    result_str = await asyncio.to_thread(
                                        web_search_module.web_search,
                                        {"query": query, "mode": fc.args.get("mode", "search"), "items": fc.args.get("items", []), "aspect": fc.args.get("aspect", "general")}
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "gmail_read":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'gmail_read'")
                                    try:
                                        emails = await asyncio.to_thread(
                                            self.google_account.read_emails,
                                            fc.args.get("query", "is:unread"),
                                            fc.args.get("limit", 10),
                                        )
                                        result_str = json.dumps(emails, ensure_ascii=False)
                                        if self.on_notification:
                                            self.on_notification({"category": "google_gmail", "title": "Gmail", "message": f"Found {len(emails)} email(s).", "service": "gmail", "items": emails})
                                    except Exception as exc:
                                        result_str = f"Gmail unavailable: {exc}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "gmail_thread_read":
                                    try:
                                        messages = await asyncio.to_thread(self.google_account.read_gmail_thread, fc.args.get("thread_id", ""))
                                        result_str = json.dumps(messages, ensure_ascii=False)
                                        if self.on_notification:
                                            self.on_notification({"category": "google_gmail", "title": "Gmail thread", "message": f"Loaded {len(messages)} message(s).", "service": "gmail", "items": messages})
                                    except Exception as exc:
                                        result_str = f"Gmail thread unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "gmail_create_draft":
                                    try:
                                        result_str = json.dumps(await asyncio.to_thread(self.google_account.create_gmail_draft, fc.args.get("to", ""), fc.args.get("subject", ""), fc.args.get("body", ""), fc.args.get("thread_id", "")), ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Gmail draft unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_contacts_read":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'google_contacts_read'")
                                    try:
                                        contacts = await asyncio.to_thread(
                                            self.google_account.read_contacts,
                                            fc.args.get("query", ""),
                                            fc.args.get("limit", 25),
                                        )
                                        result_str = json.dumps(contacts, ensure_ascii=False)
                                        if self.on_notification:
                                            self.on_notification({"category": "google_contacts", "title": "Google Contacts", "message": f"Found {len(contacts)} contact(s).", "service": "contacts", "items": contacts})
                                    except Exception as exc:
                                        result_str = f"Google Contacts unavailable: {exc}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "google_contacts_import":
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'google_contacts_import'")
                                    try:
                                        contacts = await asyncio.to_thread(
                                            self.google_account.read_contacts,
                                            fc.args.get("query", ""),
                                            min(fc.args.get("limit", 500), 500),
                                        )
                                        platform = fc.args.get("platform", "whatsapp")
                                        saved = 0
                                        skipped = 0
                                        for contact in contacts:
                                            name = contact.get("name", "").strip()
                                            recipient = (contact.get("emails") or contact.get("phones") or [""])[0].strip()
                                            if not name or not recipient:
                                                skipped += 1
                                                continue
                                            self.contacts_manager.add_or_update(name, recipient, platform)
                                            saved += 1
                                        result_str = json.dumps({"found": len(contacts), "saved": saved, "skipped": skipped, "platform": platform})
                                    except Exception as exc:
                                        result_str = f"Google Contacts import unavailable: {exc}"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "google_contacts_sync":
                                    direction = fc.args.get("direction", "from_google")
                                    platform = fc.args.get("platform", "whatsapp")
                                    try:
                                        if direction == "from_google":
                                            contacts = await asyncio.to_thread(self.google_account.read_contacts, "", min(fc.args.get("limit", 500), 500))
                                            saved = 0
                                            for contact in contacts:
                                                name = contact.get("name", "").strip()
                                                recipient = (contact.get("emails") or contact.get("phones") or [""])[0].strip()
                                                if name and recipient:
                                                    self.contacts_manager.add_or_update(name, recipient, platform)
                                                    saved += 1
                                            result_str = json.dumps({"direction": direction, "found": len(contacts), "saved": saved, "platform": platform})
                                        elif direction == "to_google":
                                            local_contacts = self.contacts_manager.list_contacts()
                                            created = 0
                                            for contact in local_contacts[:min(fc.args.get("limit", 500), 500)]:
                                                channels = contact.get("channels", {})
                                                email = channels.get("email", "")
                                                phone = channels.get("phone", "") or channels.get("whatsapp", "")
                                                await asyncio.to_thread(self.google_account.create_contact, contact.get("name", ""), email, phone)
                                                created += 1
                                            result_str = json.dumps({"direction": direction, "found": len(local_contacts), "created": created})
                                        else:
                                            result_str = "Sync direction must be from_google or to_google."
                                    except Exception as exc:
                                        result_str = f"Google Contacts sync unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "sync_google_services":
                                    try:
                                        result = await asyncio.to_thread(self.google_account.sync_snapshot, min(fc.args.get("limit", 25), 100))
                                        result_str = json.dumps({"success": True, "synced": result}, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Google sync unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "google_drive_list":
                                    try:
                                        files = await asyncio.to_thread(self.google_account.list_drive_files, fc.args.get("query", "trashed = false"), fc.args.get("limit", 25))
                                        result_str = json.dumps(files, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = f"Google Drive unavailable: {exc}"
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "send_message":
                                    receiver = fc.args.get("receiver", "")
                                    platform = fc.args.get("platform", "whatsapp")
                                    resolved_receiver = self.contacts_manager.resolve(receiver, platform)
                                    if resolved_receiver:
                                        receiver = resolved_receiver
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'send_message' receiver='{receiver}'")
                                    result_str = await asyncio.to_thread(
                                        send_message_module.send_message,
                                        {"receiver": receiver, "message_text": fc.args.get("message_text", ""), "platform": platform}
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "contacts_manager":
                                    action = fc.args.get("action", "").lower().strip()
                                    name = fc.args.get("name", "")
                                    platform = fc.args.get("platform", "whatsapp")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'contacts_manager' action='{action}' name='{name}'")
                                    if action in ("add", "update"):
                                        result_str = self.contacts_manager.add_or_update(
                                            name, fc.args.get("recipient", ""), platform
                                        )
                                    elif action == "remove":
                                        result_str = self.contacts_manager.remove(name, platform if fc.args.get("recipient") else "")
                                    elif action == "list":
                                        result_str = self.contacts_manager.format_contacts()
                                    elif action == "find":
                                        contact = self.contacts_manager.find(name)
                                        result_str = json.dumps(contact, ensure_ascii=False) if contact else f"Contact not found: {name}"
                                    else:
                                        result_str = f"Unknown contacts_manager action: '{action}'"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "youtube_video":
                                    action = fc.args.get("action", "play")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'youtube_video' action='{action}'")
                                    result_str = await asyncio.to_thread(
                                        youtube_video_module.youtube_video,
                                        {
                                            "action": action,
                                            "query": fc.args.get("query", ""),
                                            "url": fc.args.get("url", ""),
                                            "region": fc.args.get("region", "TR"),
                                            "save": fc.args.get("save", False),
                                        }
                                    )
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "browser_control":
                                    action = fc.args.get("action", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'browser_control' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    fields_raw = params.get("fields")
                                    if isinstance(fields_raw, str) and fields_raw.strip():
                                        try:
                                            params["fields"] = json.loads(fields_raw)
                                        except json.JSONDecodeError:
                                            pass
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("browser_control", browser_control_module.browser_control, params))
                                    result_str = "Browser action started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "code_helper":
                                    action = fc.args.get("action", "auto")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'code_helper' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("code_helper", code_helper_module.code_helper, params))
                                    result_str = "Code helper task started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "build_project":
                                    description_arg = fc.args.get("description", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'build_project' description='{description_arg}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("build_project", dev_agent_module.dev_agent, params))
                                    result_str = "Project build started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "find_flights":
                                    origin = fc.args.get("origin", "")
                                    destination = fc.args.get("destination", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'find_flights' {origin} -> {destination}")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("find_flights", flight_finder_module.flight_finder, params))
                                    result_str = "Flight search started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "game_updater":
                                    action = fc.args.get("action", "update")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'game_updater' action='{action}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("game_updater", game_updater_module.game_updater, params))
                                    result_str = "Game update task started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "process_file":
                                    file_path_arg = fc.args.get("file_path", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'process_file' file_path='{file_path_arg}'")
                                    params = {k: v for k, v in fc.args.items()}
                                    self._plan_pending = True
                                    self.spawn_background_task(self.run_background_tool("process_file", file_processor_module.file_processor, params))
                                    result_str = "File processing started."
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "manage_monitors":
                                    action = fc.args.get("action", "")
                                    topic = fc.args.get("topic", "")
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'manage_monitors' action='{action}' topic='{topic}'")
                                    if action == "add":
                                        result_str = await asyncio.to_thread(background_monitor_module.add_monitor, topic)
                                    elif action == "remove":
                                        result_str = await asyncio.to_thread(background_monitor_module.remove_monitor, topic)
                                    elif action == "list":
                                        monitors = await asyncio.to_thread(background_monitor_module.list_monitors)
                                        result_str = ", ".join(monitors) if monitors else "No topics are being monitored."
                                    else:
                                        result_str = f"Unknown manage_monitors action: '{action}'"
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "run_routine":
                                    routine_name = fc.args.get("name", "")
                                    payload = fc.args.get("payload", {})
                                    if isinstance(payload, str):
                                        try:
                                            payload = json.loads(payload)
                                        except json.JSONDecodeError:
                                            payload = {}
                                    print(f"[FRIDAY DEBUG] [TOOL] Tool Call: 'run_routine' name='{routine_name}'")
                                    try:
                                        result = self.routine_manager.execute_runtime(routine_name, payload, runtime=self)
                                        result_str = json.dumps(result, ensure_ascii=False)
                                    except ValueError as exc:
                                        result_str = json.dumps({"error": str(exc)}, ensure_ascii=False)
                                    function_response = types.FunctionResponse(
                                        id=fc.id, name=fc.name, response={"result": result_str}
                                    )
                                    function_responses.append(function_response)

                                elif fc.name == "build_custom_tool":
                                    try:
                                        result = self.tool_builder.build(fc.args.get("name", ""), fc.args.get("description", ""), fc.args.get("operation", ""), fc.args.get("parameters", {}), fc.args.get("config", {}), fc.args.get("governance", {}))
                                        manifest = result["tool"]
                                        declaration = {"name": manifest["name"], "description": manifest["description"], "parameters": {"type": "OBJECT", "properties": manifest.get("parameters", {})}}
                                        declarations = tools[1]["function_declarations"]
                                        existing_index = next((index for index, item in enumerate(declarations) if item.get("name") == declaration["name"]), None)
                                        if existing_index is None:
                                            declarations.append(declaration)
                                        else:
                                            declarations[existing_index] = declaration
                                        if self.session and result["tool"].get("governance", {}).get("approval") == "approved":
                                            await self.session.send(
                                                input=(
                                                    f"System Notification: Custom tool '{declaration['name']}' was built, tested, verified, and registered live. "
                                                    "Use run_custom_tool with this exact name when the user requests it."
                                                ),
                                                end_of_turn=False,
                                            )
                                        result_str = json.dumps(result, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = json.dumps({"registered": False, "error": str(exc)})
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "test_custom_tool":
                                    manifest = self.tool_builder.tools.get(fc.args.get("name", ""))
                                    result_str = json.dumps(self.tool_builder.test(manifest) if manifest else {"ok": False, "error": "Tool is not registered"})
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "run_custom_tool":
                                    custom_name = fc.args.get("name", "")
                                    try:
                                        result_str = json.dumps(self.tool_builder.execute(custom_name, fc.args.get("arguments", {})), ensure_ascii=False)
                                    except Exception as exc:
                                        self_maintenance_module.record_tool_failure(custom_name or "run_custom_tool", str(exc))
                                        result_str = json.dumps({"ok": False, "error": str(exc)})
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "build_agent":
                                    try:
                                        result = self.agent_builder.build(fc.args.get("name", ""), fc.args.get("description", ""), fc.args.get("code", ""), fc.args.get("parameters", {}), fc.args.get("governance", {}))
                                        agent_name = result["agent"]["name"]
                                        if is_active(result["agent"]):
                                            agent_dispatcher_module.dispatcher.register_agent(agent_name, self.agent_builder.load_callable(agent_name))
                                        result_str = json.dumps({**result, "deploy_with": "deploy_agent", "agent_type": agent_name}, ensure_ascii=False)
                                    except Exception as exc:
                                        result_str = json.dumps({"registered": False, "error": str(exc)})
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "test_agent":
                                    result_str = json.dumps(self.agent_builder.test(fc.args.get("name", "")), ensure_ascii=False)
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))

                                elif fc.name == "manage_plugins":
                                    action = fc.args.get("action", "list").lower()
                                    try:
                                        if action == "list":
                                            result = {"plugins": self.plugin_manager.list_plugins()}
                                        elif action == "health":
                                            result = self.plugin_manager.health()
                                        elif action == "snapshot":
                                            result = self.plugin_manager.snapshot(fc.args.get("label", "manual"))
                                        elif action == "snapshots":
                                            result = {"snapshots": self.plugin_manager.list_snapshots()}
                                        elif action == "rollback":
                                            result = self.plugin_manager.rollback(fc.args.get("snapshot", ""))
                                        elif action in {"enable", "disable"}:
                                            result = self.plugin_manager.set_enabled(fc.args.get("kind", "tool"), fc.args.get("name", ""), action == "enable")
                                        elif action == "propose":
                                            result = self.plugin_manager.propose(fc.args.get("kind", "tool"), fc.args.get("name", ""), fc.args.get("permissions"), fc.args.get("dependencies"), fc.args.get("resource_limits"), fc.args.get("test_fixtures"), int(fc.args.get("expires_days", 90)))
                                        elif action == "review":
                                            result = self.plugin_manager.review(fc.args.get("kind", "tool"), fc.args.get("name", ""), bool(fc.args.get("approved", False)), fc.args.get("security_review", "approved"))
                                        elif action == "expire":
                                            result = {"expired": self.plugin_manager.expire()}
                                        elif action == "score":
                                            result = self.plugin_manager.score(fc.args.get("kind", "tool"), fc.args.get("name", ""), bool(fc.args.get("success", False)))
                                        else:
                                            result = {"error": "Plugin action must be list, health, snapshot, snapshots, rollback, enable, disable, propose, review, expire, or score."}
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}))

                                elif fc.name == "openclaw_plan":
                                    try:
                                        result = self.openclaw_bridge.plan(fc.args.get("goal", ""))
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}))

                                elif fc.name == "openclaw_execute":
                                    try:
                                        result = self.openclaw_bridge.execute_plan(fc.args.get("plan", {}), fc.args.get("repo_path", "."))
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False, default=str)}))

                                elif fc.name == "openclaw_capabilities":
                                    result = self.openclaw_bridge.capabilities()
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False, default=str)}))

                                elif fc.name == "openclaw_delegate":
                                    try:
                                        result = self.openclaw_bridge.delegate(fc.args.get("agent_type", ""), fc.args.get("goal", ""), fc.args.get("repo_path", "."))
                                    except Exception as exc:
                                        result = {"error": str(exc)}
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": json.dumps(result, ensure_ascii=False)}))

                                elif fc.name in self.tool_builder.tools:
                                    try:
                                        result_str = json.dumps(self.tool_builder.execute(fc.name, fc.args), ensure_ascii=False)
                                    except Exception as exc:
                                        self_maintenance_module.record_tool_failure(fc.name, str(exc))
                                        result_str = json.dumps({"ok": False, "error": str(exc)})
                                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str}))
                        if not self._plan_pending:
                            self.finish_action_plan(True)
                        if function_responses:
                            await self.session.send_tool_response(function_responses=function_responses)
                
                # Turn/Response Loop Finished
                self.flush_chat()

                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            print(f"Error in receive_audio: {e}")
            traceback.print_exc()
            # CRITICAL: Re-raise to crash the TaskGroup and trigger outer loop reconnect
            raise e

    async def play_audio(self):
        self.output_stream = await asyncio.to_thread(
            sd.RawOutputStream,
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=self.output_device_index,
            blocksize=CHUNK_SIZE,
        )
        await asyncio.to_thread(self.output_stream.start)
        try:
            while True:
                bytestream = await self.audio_in_queue.get()
                if self.on_audio_data:
                    self.on_audio_data(bytestream)
                await asyncio.to_thread(self.output_stream.write, bytestream)
        finally:
            if self.output_stream:
                await asyncio.to_thread(self.output_stream.close)
                self.output_stream = None

    async def get_frames(self):
        # AVFoundation is macOS-only; use DirectShow on Windows and the default backend elsewhere.
        camera_backend = cv2.CAP_DSHOW if sys.platform == "win32" else (cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY)
        self.camera_capture = await asyncio.to_thread(cv2.VideoCapture, 0, camera_backend)
        try:
            while True:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue
                frame = await asyncio.to_thread(self._get_frame, self.camera_capture)
                if frame is None:
                    break
                await asyncio.sleep(1.0)
                if self.out_queue:
                    await self.out_queue.put(frame)
        finally:
            if self.camera_capture:
                await asyncio.to_thread(self.camera_capture.release)
                self.camera_capture = None

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        image_bytes = image_io.read()
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    def _get_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            img = PIL.Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.thumbnail([1024, 1024])
            image_io = io.BytesIO()
            img.save(image_io, format="jpeg")
            image_io.seek(0)
            image_bytes = image_io.read()
            return {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while True:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            frame = await asyncio.to_thread(self._get_screen)
            await asyncio.sleep(1.0)
            if self.out_queue:
                await self.out_queue.put(frame)

    async def monitor_system(self):
        """Poll system, Google, and long-running state through one notification channel."""
        seen_calendar = set()
        seen_email = set()
        while True:
            await asyncio.sleep(20)
            alert = await asyncio.to_thread(self.system_monitor.check)
            if alert:
                print(f"[FRIDAY DEBUG] [MONITOR] {alert}")
                await self.notifications.notify("system_overload", "System health", alert, "high")

            if self.google_account.credentials and self.google_account.credentials.valid:
                try:
                    important = await asyncio.to_thread(self.google_account.read_emails, "is:unread is:important", 5)
                    for email in important:
                        if email["id"] not in seen_email:
                            seen_email.add(email["id"])
                            await self.notifications.notify("important_email", "Important email", f"New important email from {email['from']}: {email['subject']}")
                    events = await asyncio.to_thread(self.google_account.list_calendar_events, "", 1, 10)
                    for event in events:
                        event_id = event.get("id")
                        start = event.get("start", {}).get("dateTime", "")
                        if event_id and event_id not in seen_calendar and start:
                            seen_calendar.add(event_id)
                            local_start = start
                            try:
                                local_start = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M %Z")
                            except ValueError:
                                pass
                            await self.notifications.notify("calendar_event", "Upcoming calendar event", f"{event.get('summary', 'Untitled')} starts at {local_start}.")
                except Exception as error:
                    print(f"[FRIDAY DEBUG] [NOTIFY] Google polling failed: {error}")

    async def autonomy_loop(self):
        """Continuously observe Friday's world and escalate risky decisions for approval."""
        while True:
            await asyncio.sleep(30)
            try:
                report = await asyncio.to_thread(self.autonomy_supervisor.inspect)
                for notification in report.notifications:
                    await self.notifications.notify(
                        notification["category"], notification["title"], notification["message"], notification.get("priority", "normal")
                    )
                if report.observations:
                    print(f"[FRIDAY DEBUG] [AUTONOMY] {'; '.join(report.observations)}")
            except asyncio.CancelledError:
                break
            except Exception as error:
                print(f"[FRIDAY DEBUG] [ERR] Autonomy loop failed: {error}")

    async def proactive_loop(self):
        """Periodically checks if Friday should speak unprompted based on silence, stall patterns, and system state."""
        while True:
            await asyncio.sleep(60)
            if not self.session or not self.proactive_engine.should_trigger(self._last_user_speech):
                continue
            try:
                alerts = await asyncio.to_thread(background_monitor_module.check_all)
                memory = await asyncio.to_thread(load_legacy_memory)
                monitors = await asyncio.to_thread(background_monitor_module.list_monitors)
                recent_turns = self.memory_manager.get_recent_messages(limit=10)
                recent_text = [item.get("text", "") for item in recent_turns if item.get("text")]
                system_status = await asyncio.to_thread(system_monitor_module.get_system_status)
                missing_context = None
                if self._active_plan and self._active_plan.get("steps"):
                    for step in self._active_plan["steps"]:
                        if step.get("status") == "active":
                            missing_context = {"tool": self._active_plan.get("title", "action").lower(), "issue": "The current task may need more detail before continuing."}
                            break

                prompt = self.proactive_engine.build_prompt(
                    memory,
                    monitors=monitors,
                    recent_turns=recent_text,
                    system_status=system_status,
                    missing_context=missing_context,
                )
                if alerts:
                    prompt += "\n\nNew monitor alerts:\n" + "\n".join(alerts)
                if self.proactive_engine.detect_stall(recent_turns=recent_text) or self.proactive_engine.detect_system_overload(system_status):
                    print(f"[FRIDAY DEBUG] [PROACTIVE] Triggering intervention for stalled work or overload.")
                else:
                    print(f"[FRIDAY DEBUG] [PROACTIVE] Triggering unprompted check-in.")
                await self.session.send(input=prompt, end_of_turn=True)
                self.proactive_engine.mark_triggered()
            except Exception as e:
                print(f"[FRIDAY DEBUG] [ERR] Proactive loop failed: {e}")


    async def run(self, start_message=None):
        retry_delay = 1
        is_reconnect = False
        
        while not self.stop_event.is_set():
            try:
                print(f"[FRIDAY DEBUG] [CONNECT] Connecting to Gemini Live API...")
                async with (
                    client.aio.live.connect(model=MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session

                    if self._pending_runtime_notifications:
                        pending_events = self._pending_runtime_notifications
                        self._pending_runtime_notifications = []
                        for event in pending_events:
                            await self.session.send(input=event, end_of_turn=True)
                        print(f"[FRIDAY DEBUG] [RUNTIME EVENT] delivered {len(pending_events)} queued event(s)")

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=10)

                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    # tg.create_task(self._process_video_queue()) # Removed in favor of VAD

                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    elif self.video_mode == "screen":
                        tg.create_task(self.get_screen())

                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                    tg.create_task(self.monitor_system())
                    tg.create_task(self.autonomy_loop())
                    tg.create_task(self.proactive_loop())
                    tg.create_task(self.compact_memory())
                    tg.create_task(self._send_live_video())

                    # Handle Startup vs Reconnect Logic
                    if not is_reconnect:
                        # Load global long-term memory (survives server restarts, not project-scoped)
                        compact_context = self.memory_manager.get_compact_context(recent_limit=20)
                        if compact_context != "Compact long-term memory:\n":
                            print("[FRIDAY DEBUG] [STARTUP] Loading compact long-term memory and recent conversation...")
                            memory_msg = "System Notification: Load this compact long-term memory silently and use it when relevant:\n\n" + compact_context
                            await self.session.send(input=memory_msg, end_of_turn=True)

                        if start_message:
                            print(f"[FRIDAY DEBUG] [INFO] Sending start message: {start_message}")
                            await self.session.send(input=start_message, end_of_turn=True)
                        
                        # Sync Project State
                        if self.on_project_update and self.project_manager:
                            self.on_project_update(self.project_manager.current_project)
                    
                    else:
                        print(f"[FRIDAY DEBUG] [RECONNECT] Connection restored.")
                        # Restore Context (global memory, same source used on fresh startup)
                        # Each reconnect starts a brand-new Live session with empty context, so
                        # durable facts (name, relationships, preferences, etc.) must be resent
                        # here too, not just the raw recent chat tail - otherwise they silently
                        # fall out of context after any disconnect/reconnect cycle.
                        print(f"[FRIDAY DEBUG] [RECONNECT] Fetching compact long-term memory and recent chat history to restore context...")
                        compact_context = self.memory_manager.get_compact_context(recent_limit=10)

                        context_msg = "System Notification: Connection was lost and just re-established. Load this compact long-term memory silently and use it when relevant, then resume the conversation seamlessly:\n\n"
                        if compact_context != "Compact long-term memory:\n":
                            context_msg += compact_context + "\n\n"

                        context_msg += "\nPlease acknowledge the reconnection to the user (e.g. 'I lost connection for a moment, but I'm back...') and resume what you were doing."
                        
                        print(f"[FRIDAY DEBUG] [RECONNECT] Sending restoration context to model...")
                        await self.session.send(input=context_msg, end_of_turn=True)

                    # Reset retry delay on successful connection
                    retry_delay = 1
                    
                    # Wait until stop event, or until the session task group exits (which happens on error)
                    # Actually, the TaskGroup context manager will exit if any tasks fail/cancel.
                    # We need to keep this block alive.
                    # The original code just waited on stop_event, but that doesn't account for session death.
                    # We should rely on the TaskGroup raising an exception when subtasks fail (like receive_audio).
                    
                    # However, since receive_audio is a task in the group, if it crashes (connection closed), 
                    # the group will cancel others and exit. We catch that exit below.
                    
                    # We can await stop_event, but if the connection dies, receive_audio crashes -> group closes -> we exit `async with` -> restart loop.
                    # To ensure we don't block indefinitely if connection dies silently (unlikely with receive_audio), we just wait.
                    await self.stop_event.wait()

            except asyncio.CancelledError:
                print(f"[FRIDAY DEBUG] [STOP] Main loop cancelled.")
                break
                
            except Exception as e:
                # This catches the ExceptionGroup from TaskGroup or direct exceptions
                print(f"[FRIDAY DEBUG] [ERR] Connection Error: {e}")
                if isinstance(e, BaseExceptionGroup):
                    for nested_error in e.exceptions:
                        print(f"[FRIDAY DEBUG] [ERR] Task failure: {nested_error!r}")
                        traceback.print_exception(type(nested_error), nested_error, nested_error.__traceback__)
                else:
                    traceback.print_exception(type(e), e, e.__traceback__)
                
                # Notify user of connection error
                try:
                    if hasattr(self, 'session') and self.session:
                        await self.session.send(input=f"System Notification: Connection error occurred. Reconnecting... Error: {str(e)}", end_of_turn=True)
                except Exception as notify_error:
                    print(f"[FRIDAY DEBUG] [ERR] Failed to notify user of error: {notify_error}")
                
                if self.stop_event.is_set():
                    break
                
                print(f"[FRIDAY DEBUG] [RETRY] Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10) # Exponential backoff capped at 10s
                is_reconnect = True # Next loop will be a reconnect
                
            finally:
                await self.cleanup_resources()

def get_input_devices():
    devices = []
    for i, info in enumerate(sd.query_devices()):
        if info.get('max_input_channels', 0) > 0:
            devices.append((i, info.get('name')))
    return devices

def get_output_devices():
    devices = []
    for i, info in enumerate(sd.query_devices()):
        if info.get('max_output_channels', 0) > 0:
            devices.append((i, info.get('name')))
    return devices

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())