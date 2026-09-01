# Function definitions
generate_cad = {
    "name": "generate_cad",
    "description": "Generates a 3D CAD model based on a prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The description of the object to generate."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

run_web_agent = {
    "name": "run_web_agent",
    "description": "Opens a web browser and performs a task according to the prompt.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The detailed instructions for the web browser agent."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

create_project_tool = {
    "name": "create_project",
    "description": "Creates a new project folder to organize files.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the new project."}
        },
        "required": ["name"]
    }
}

switch_project_tool = {
    "name": "switch_project",
    "description": "Switches the current active project context.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "The name of the project to switch to."}
        },
        "required": ["name"]
    }
}

list_projects_tool = {
    "name": "list_projects",
    "description": "Lists all available projects.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

search_memory_tool = {
    "name": "search_memory",
    "description": "Searches all long-term memory (every conversation ever had, across all projects and server restarts) for a keyword or topic. Use this when the user references something from a past conversation that isn't in the current context, e.g. 'what did we talk about last year' or 'do you remember when I mentioned...'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Keywords describing what to search for in past conversations."}
        },
        "required": ["query"]
    }
}

list_smart_devices_tool = {
    "name": "list_smart_devices",
    "description": "Lists all available smart home devices (lights, plugs, etc.) on the network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

control_light_tool = {
    "name": "control_light",
    "description": "Controls a smart light device.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "The IP address of the device to control. Always prefer the IP address over the alias for reliability."
            },
            "action": {
                "type": "STRING",
                "description": "The action to perform: 'turn_on', 'turn_off', or 'set'."
            },
            "brightness": {
                "type": "INTEGER",
                "description": "Optional brightness level (0-100)."
            },
            "color": {
                "type": "STRING",
                "description": "Optional color name (e.g., 'red', 'cool white') or 'warm'."
            }
        },
        "required": ["target", "action"]
    }
}

discover_printers_tool = {
    "name": "discover_printers",
    "description": "Discovers 3D printers available on the local network.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

print_stl_tool = {
    "name": "print_stl",
    "description": "Prints an STL file to a 3D printer. Handles slicing the STL to G-code and uploading to the printer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "stl_path": {"type": "STRING", "description": "Path to STL file, or 'current' for the most recent CAD model."},
            "printer": {"type": "STRING", "description": "Printer name or IP address."},
            "profile": {"type": "STRING", "description": "Optional slicer profile name."}
        },
        "required": ["stl_path", "printer"]
    }
}

get_print_status_tool = {
    "name": "get_print_status",
    "description": "Gets the current status of a 3D printer including progress, time remaining, and temperatures.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "printer": {"type": "STRING", "description": "Printer name or IP address."}
        },
        "required": ["printer"]
    }
}

iterate_cad_tool = {
    "name": "iterate_cad",
    "description": "Modifies or iterates on the current CAD design based on user feedback. Use this when the user asks to adjust, change, modify, or iterate on the existing 3D model (e.g., 'make it taller', 'add a handle', 'reduce the thickness').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {"type": "STRING", "description": "The changes or modifications to apply to the current design."}
        },
        "required": ["prompt"]
    },
    "behavior": "NON_BLOCKING"
}

computer_control_tool = {
    "name": "computer_control",
    "description": "Controls the mouse and keyboard: type text, click, drag, scroll, press hotkeys, take screenshots, read/write clipboard. Use for direct desktop input automation.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: type, smart_type, click, double_click, right_click, move, drag, hotkey, press, scroll, copy, paste, screenshot, wait, clear_field, focus_window, random_data, user_data."},
            "text": {"type": "STRING", "description": "Text to type or paste."},
            "x": {"type": "INTEGER", "description": "X coordinate for click/move/drag."},
            "y": {"type": "INTEGER", "description": "Y coordinate for click/move/drag."},
            "x1": {"type": "INTEGER", "description": "Drag start X."},
            "y1": {"type": "INTEGER", "description": "Drag start Y."},
            "x2": {"type": "INTEGER", "description": "Drag end X."},
            "y2": {"type": "INTEGER", "description": "Drag end Y."},
            "button": {"type": "STRING", "description": "Mouse button: 'left' or 'right'."},
            "keys": {"type": "STRING", "description": "Hotkey combo, e.g. 'ctrl+c'."},
            "key": {"type": "STRING", "description": "Single key name, e.g. 'enter'."},
            "direction": {"type": "STRING", "description": "Scroll direction: up, down, left, right."},
            "amount": {"type": "INTEGER", "description": "Scroll amount."},
            "seconds": {"type": "NUMBER", "description": "Seconds to wait for the 'wait' action."},
            "title": {"type": "STRING", "description": "Window title fragment for focus_window."},
            "clear_first": {"type": "BOOLEAN", "description": "Clear the field before typing (smart_type)."},
            "path": {"type": "STRING", "description": "Save path for screenshot (must be inside the home directory)."}
        },
        "required": ["action"]
    }
}

computer_settings_tool = {
    "name": "computer_settings",
    "description": "Controls OS-level settings: volume, brightness, window management (minimize/maximize/snap), browser tab/page navigation, dark mode, wifi toggle, lock screen, and restart/shutdown (requires confirmed='yes').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "e.g. volume_up, volume_down, volume_set, mute, brightness_up, brightness_down, close_window, minimize, maximize, snap_left, snap_right, switch_window, show_desktop, new_tab, close_tab, next_tab, prev_tab, go_back, go_forward, zoom_in, zoom_out, dark_mode, toggle_wifi, lock_screen, restart, shutdown."},
            "value": {"type": "STRING", "description": "Value for actions like volume_set (0-100)."},
            "confirmed": {"type": "STRING", "description": "Must be 'yes' to actually execute restart/shutdown."}
        },
        "required": ["action"]
    }
}

manage_files_tool = {
    "name": "manage_files",
    "description": "Manages real files/folders on the user's computer (Desktop, Downloads, Documents, Pictures, Music, Videos, or any path) - list, create, delete, move, copy, rename, read, write, find, and disk usage. This is distinct from the project-scoped write_file/read_file tools.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: list, create_file, create_folder, delete, move, copy, rename, read, write, find, largest, disk_usage, organize_desktop, info."},
            "path": {"type": "STRING", "description": "Folder shortcut (desktop, downloads, documents, pictures, music, videos, home) or an absolute path. Defaults to 'desktop'."},
            "name": {"type": "STRING", "description": "File or folder name relative to path."},
            "content": {"type": "STRING", "description": "Content for create_file/write."},
            "destination": {"type": "STRING", "description": "Destination path for move/copy."},
            "new_name": {"type": "STRING", "description": "New name for rename."},
            "append": {"type": "BOOLEAN", "description": "Append instead of overwrite for write."},
            "extension": {"type": "STRING", "description": "File extension filter for find, e.g. '.pdf'."},
            "max_results": {"type": "INTEGER", "description": "Max results for find."},
            "count": {"type": "INTEGER", "description": "Number of results for largest."}
        },
        "required": ["action"]
    }
}

open_application_tool = {
    "name": "open_application",
    "description": "Opens a desktop application by name, e.g. Chrome, Spotify, VS Code, Notepad, Steam, Discord.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {"type": "STRING", "description": "The name of the application to open."}
        },
        "required": ["app_name"]
    }
}

get_system_status_tool = {
    "name": "get_system_status",
    "description": "Gets the current CPU, RAM, and GPU usage, CPU temperature, uptime, and process count of the user's computer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

undo_last_action_tool = {
    "name": "undo_last_action",
    "description": "Reverses the most recent supported action. Currently restores overwritten/deletes newly created project files, restores a previous wallpaper when its path is available, and restores the previous project context.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

manage_uploads_tool = {
    "name": "manage_uploads",
    "description": "Manages uploaded files. List uploads, permanently save a temporary upload, forget one upload or all temporary uploads, or clean expired temporary files.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: list, save, forget, cleanup."},
            "path": {"type": "STRING", "description": "Exact upload path for save or forget. Omit to forget all temporary uploads."}
        },
        "required": ["action"]
    }
}

cancel_current_task_tool = {
    "name": "cancel_current_task",
    "description": "Stops the currently running cancellable action, such as CAD generation, browser automation, project building, flight search, game updates, or file processing. Use when the user says stop or cancel what you are doing.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
}

self_maintenance_tool = {
    "name": "self_maintenance",
    "description": "Runs Friday's own maintenance tasks: run the backend test suite, a specific test file, compile-check the backend for syntax errors, build the frontend, or install missing Python/Node dependencies. Use when the user asks Friday to test itself, self-compile, build the frontend, install missing dependencies, or check for errors and warnings. Reports issues found for the user to review and fix; does not auto-fix code.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: run_tests, compile_check, build_frontend, install_python_deps, install_frontend_deps, full_check. Defaults to full_check."},
            "args": {"type": "STRING", "description": "Optional extra pytest arguments for run_tests. Examples: '-k auth' or 'tests/test_authenticator.py'."},
            "target": {"type": "STRING", "description": "Optional single test target to run, such as 'tests/test_authenticator.py' or 'tests/test_kasa_agent.py::TestKasaDiscovery::test_initialize_known_devices'."}
        },
        "required": ["action"]
    }
}

git_workflow_tool = {
    "name": "git_workflow",
    "description": "Inspects git status, creates or switches branches, shows diffs, commits staged or all changes, and checks for obvious regressions. Use when the user asks Friday to manage the repository, review changes, or prepare a branch/commit.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: status, create_branch, checkout_branch, diff, review_diff, commit, regression_check."},
            "repo_path": {"type": "STRING", "description": "Optional repo path. Defaults to the current workspace."},
            "branch_name": {"type": "STRING", "description": "Branch name for create_branch or checkout_branch."},
            "message": {"type": "STRING", "description": "Commit message for commit actions."},
            "max_chars": {"type": "NUMBER", "description": "Maximum characters to return for review_diff."}
        },
        "required": ["action"]
    }
}

run_powershell_command_tool = {
    "name": "run_powershell_command",
    "description": "Executes an arbitrary PowerShell command on this machine and returns stdout/stderr. Use only when the user explicitly asks Friday to run a shell command or PowerShell script.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "The exact PowerShell command to execute, such as 'Get-ChildItem' or 'Get-Process | Select-Object -First 5'."},
            "cwd": {"type": "STRING", "description": "Optional working directory for the command."},
            "timeout": {"type": "NUMBER", "description": "Timeout in seconds. Defaults to 120."}
        },
        "required": ["command"]
    }
}

deploy_agent_tool = {
    "name": "deploy_agent",
    "description": "Deploys an independent background agent to handle a long-running task (e.g. repo repair: inspect, run targeted checks, verify, summarize) so Friday never hangs waiting on it. Use 'deploy' to start an agent, 'status' to poll one by agent_id, 'list' to see all deployed agents, and 'cancel' to stop one early.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: deploy, status, list, cancel."},
            "agent_type": {"type": "STRING", "description": "Agent to deploy. Currently supported: repo_repair."},
            "goal": {"type": "STRING", "description": "High-level goal for the deployed agent, e.g. 'clean up this repo and fix failing tests'."},
            "repo_path": {"type": "STRING", "description": "Repository path for the agent to operate on. Defaults to the current workspace."},
            "agent_id": {"type": "STRING", "description": "Agent id for status or cancel actions."}
        },
        "required": ["action"]
    }
}

mute_alert_category_tool = {
    "name": "mute_alert_category",
    "description": "Controls proactive system alerts. Mute or unmute one category (cpu, ram, temp, gpu), enable or disable all system alerts, or list the current alert settings. Use this when the user asks Friday to stop repeatedly warning about CPU or another system metric.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: mute, unmute, enable, disable, list."},
            "category": {"type": "STRING", "description": "Alert category: cpu, ram, temp, or gpu."}
        },
        "required": ["action"]
    }
}

get_weather_tool = {
    "name": "get_weather",
    "description": "Opens a weather search in the browser for a given city and time period.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {"type": "STRING", "description": "The city to get the weather for."},
            "time": {"type": "STRING", "description": "Time period, e.g. 'today', 'tomorrow', 'this week'. Defaults to 'today'."}
        },
        "required": ["city"]
    }
}

set_reminder_tool = {
    "name": "set_reminder",
    "description": "Schedules an OS-level reminder notification for a specific date and time.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format."},
            "time": {"type": "STRING", "description": "Time in 24-hour HH:MM format."},
            "message": {"type": "STRING", "description": "The reminder message."}
        },
        "required": ["date", "time"]
    }
}

desktop_control_tool = {
    "name": "desktop_control",
    "description": "Manages the desktop: set wallpaper from a local path or URL, get the current wallpaper, organize/clean/list desktop files, or get desktop stats.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: wallpaper, wallpaper_url, current_wallpaper, organize, clean, list, stats."},
            "path": {"type": "STRING", "description": "Local image path, required for the 'wallpaper' action."},
            "url": {"type": "STRING", "description": "Image URL, required for the 'wallpaper_url' action."},
            "mode": {"type": "STRING", "description": "'by_type' or 'by_date', for the 'organize' action."}
        },
        "required": ["action"]
    }
}

web_search_tool = {
    "name": "web_search",
    "description": "Searches the web for information, news, research, prices, or comparisons using Gemini-grounded search and DuckDuckGo.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search query."},
            "mode": {"type": "STRING", "description": "One of: search, news, research, price, compare. Defaults to 'search'."},
            "items": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of items to compare, required for mode='compare'."},
            "aspect": {"type": "STRING", "description": "Aspect to compare on, for mode='compare'."}
        },
        "required": ["query"]
    }
}

send_message_tool = {
    "name": "send_message",
    "description": "Sends a message to a contact via WhatsApp, Telegram, Discord, Signal, Instagram, or Messenger using desktop/browser automation.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {"type": "STRING", "description": "The name of the contact/recipient."},
            "message_text": {"type": "STRING", "description": "The message content to send."},
            "platform": {"type": "STRING", "description": "One of: whatsapp, telegram, discord, signal, instagram, messenger. Defaults to whatsapp."}
        },
        "required": ["receiver", "message_text"]
    }
}

youtube_video_tool = {
    "name": "youtube_video",
    "description": "Plays a YouTube video by search query, gets info about a video, lists trending videos, or summarizes a video's transcript. Note: 'summarize' and 'get_info' require an explicit 'url'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: play, summarize, get_info, trending."},
            "query": {"type": "STRING", "description": "Search query, for the 'play' action."},
            "url": {"type": "STRING", "description": "The YouTube video URL, required for 'summarize' and 'get_info'."},
            "region": {"type": "STRING", "description": "Region code for 'trending', e.g. 'US'. Defaults to 'TR'."},
            "save": {"type": "BOOLEAN", "description": "Save the summary to Desktop, for the 'summarize' action."}
        },
        "required": ["action"]
    }
}

contacts_manager_tool = {
    "name": "contacts_manager",
    "description": "Manages Friday's persistent local contacts. Add or update a contact, remove a contact or channel, list contacts, or find a contact. Use saved contact names with send_message.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: add, update, remove, list, find."},
            "name": {"type": "STRING", "description": "Contact's display name."},
            "recipient": {"type": "STRING", "description": "Username, phone number, or other recipient identifier for the selected platform."},
            "platform": {"type": "STRING", "description": "Messaging platform, e.g. whatsapp, telegram, discord, signal, instagram, messenger."}
        },
        "required": ["action"]
    }
}

browser_control_tool = {
    "name": "browser_control",
    "description": "Controls a real web browser (Chrome, Firefox, Edge, Brave, using the user's own profile): navigate, search, open tabs, click, type, scroll, fill forms, read page text, screenshot, and manage multiple browser sessions.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: go_to, search, new_tab, switch, list_browsers, close, close_all, click, type, scroll, fill_form, smart_click, smart_type, get_text, get_url, press, close_tab, screenshot, back, forward, reload."},
            "url": {"type": "STRING", "description": "URL for go_to/new_tab."},
            "query": {"type": "STRING", "description": "Search query, for the 'search' action."},
            "engine": {"type": "STRING", "description": "Search engine, e.g. 'google', 'bing'. Defaults to google."},
            "browser": {"type": "STRING", "description": "Browser name, e.g. chrome, firefox, edge, brave. Uses the active/default browser if omitted."},
            "selector": {"type": "STRING", "description": "CSS selector, for 'click'/'type'."},
            "text": {"type": "STRING", "description": "Text to type, or button text to click."},
            "description": {"type": "STRING", "description": "Natural-language element description, for 'smart_click'/'smart_type'."},
            "fields": {"type": "STRING", "description": "JSON object string of {selector: value} pairs, for 'fill_form'."},
            "direction": {"type": "STRING", "description": "Scroll direction, for 'scroll'."},
            "amount": {"type": "INTEGER", "description": "Scroll amount, for 'scroll'."},
            "key": {"type": "STRING", "description": "Keyboard key, for 'press'."},
            "path": {"type": "STRING", "description": "Save path, for 'screenshot'."},
            "clear_first": {"type": "BOOLEAN", "description": "Clear the field before typing, for 'type'."}
        },
        "required": ["action"]
    }
}

code_helper_tool = {
    "name": "code_helper",
    "description": "AI-powered code generation, editing, execution, and debugging. Writes new code files, runs/builds code with iterative auto-fixing, or explains/optimizes existing code. Can execute code on the user's machine.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: write, edit, explain, run, build, optimize, auto. Defaults to 'auto' (intent is auto-detected)."},
            "description": {"type": "STRING", "description": "What the code should do, or what change to make, or what problem to analyze."},
            "language": {"type": "STRING", "description": "Programming language. Defaults to 'python'."},
            "output_path": {"type": "STRING", "description": "Where to save the generated file."},
            "file_path": {"type": "STRING", "description": "Path to an existing file, for edit/explain/run/build/optimize."},
            "code": {"type": "STRING", "description": "Raw code string, for explain/optimize without a file."},
            "args": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "CLI arguments, for run/build."},
            "timeout": {"type": "INTEGER", "description": "Execution timeout in seconds. Defaults to 30."}
        },
        "required": ["action", "description"]
    }
}

build_project_tool = {
    "name": "build_project",
    "description": "Creates a complete, runnable software project from a natural language description: plans files, writes code, installs dependencies, and can open it in VS Code. Higher risk: this installs packages and executes code on the user's machine.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {"type": "STRING", "description": "What the project should do."},
            "language": {"type": "STRING", "description": "Programming language. Defaults to 'python'."},
            "project_name": {"type": "STRING", "description": "Name for the project folder."},
            "timeout": {"type": "INTEGER", "description": "Execution timeout in seconds. Defaults to 30."}
        },
        "required": ["description"]
    }
}

find_flights_tool = {
    "name": "find_flights",
    "description": "Searches Google Flights for flights between two cities on a given date.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "origin": {"type": "STRING", "description": "Departure city or airport."},
            "destination": {"type": "STRING", "description": "Arrival city or airport."},
            "date": {"type": "STRING", "description": "Departure date."},
            "return_date": {"type": "STRING", "description": "Return date, for round trips."},
            "passengers": {"type": "INTEGER", "description": "Number of passengers. Defaults to 1."},
            "cabin": {"type": "STRING", "description": "Cabin class, e.g. economy, business. Defaults to economy."},
            "save": {"type": "BOOLEAN", "description": "Save results to Desktop."}
        },
        "required": ["origin", "destination", "date"]
    }
}

game_updater_tool = {
    "name": "game_updater",
    "description": "Lists, installs, or updates games on Steam/Epic, checks download status, or schedules a nightly auto-update.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: list, install, update, download_status, schedule, cancel_schedule, schedule_status. Defaults to 'update'."},
            "platform": {"type": "STRING", "description": "One of: steam, epic, both. Defaults to 'both'."},
            "game_name": {"type": "STRING", "description": "Name of the game."},
            "app_id": {"type": "STRING", "description": "Steam app ID, if known."},
            "hour": {"type": "INTEGER", "description": "Hour (0-23) for 'schedule'."},
            "minute": {"type": "INTEGER", "description": "Minute (0-59) for 'schedule'."},
            "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down the computer after the update completes."}
        },
        "required": ["action"]
    }
}

process_file_tool = {
    "name": "process_file",
    "description": "Analyzes or transforms a file with AI: describe/OCR/resize images, summarize/extract PDFs and documents, analyze CSV/Excel, explain/review/fix code files, and more.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {"type": "STRING", "description": "Path to the file to process."},
            "action": {"type": "STRING", "description": "The action to perform, e.g. describe, ocr, summarize, extract_text, analyze, explain, review, fix. Depends on file type."},
            "instruction": {"type": "STRING", "description": "Additional natural-language instruction for the action."}
        },
        "required": ["file_path"]
    }
}

manage_monitors_tool = {
    "name": "manage_monitors",
    "description": "Adds, removes, or lists topics to passively monitor for news updates (checked once per day). Never monitors crypto or financial topics.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "One of: add, remove, list."},
            "topic": {"type": "STRING", "description": "The topic name, required for add/remove."}
        },
        "required": ["action"]
    }
}

run_routine_tool = {
    "name": "run_routine",
    "description": "Runs a predefined Jarvis workflow routine such as morning briefing, focus mode, work summary, or a dev assistant plan.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Routine name: morning_briefing, focus_mode, work_summary, or dev_assistant."},
            "payload": {"type": "OBJECT", "description": "Optional routine payload with context, tasks, system health, repo, or issue details."}
        },
        "required": ["name"]
    }
}

generate_cad_prototype_tool = {
    "name": "generate_cad_prototype",
    "description": "Generates a 3D wireframe prototype based on a user's description. Use this when the user asks to 'visualize', 'prototype', 'create a wireframe', or 'design' something in 3D.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "The user's description of the object to prototype."
            }
        },
        "required": ["prompt"]
    }
}

write_file_tool = {
    "name": "write_file",
    "description": "Writes content to a file at the specified path. Overwrites if exists.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to write to."
            },
            "content": {
                "type": "STRING",
                "description": "The content to write to the file."
            }
        },
        "required": ["path", "content"]
    }
}

read_directory_tool = {
    "name": "read_directory",
    "description": "Lists the contents of a directory.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the directory to list."
            }
        },
        "required": ["path"]
    }
}

read_file_tool = {
    "name": "read_file",
    "description": "Reads the content of a file.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "The path of the file to read."
            }
        },
        "required": ["path"]
    }
}

tools_list = [{"function_declarations": [
    generate_cad_prototype_tool,
    write_file_tool,
    read_directory_tool,
    read_file_tool,
    generate_cad,
    iterate_cad_tool,
    run_web_agent,
    create_project_tool,
    switch_project_tool,
    list_projects_tool,
    search_memory_tool,
    list_smart_devices_tool,
    control_light_tool,
    discover_printers_tool,
    print_stl_tool,
    get_print_status_tool,
    computer_control_tool,
    computer_settings_tool,
    manage_files_tool,
    open_application_tool,
    get_system_status_tool,
    undo_last_action_tool,
    manage_uploads_tool,
    cancel_current_task_tool,
    self_maintenance_tool,
    git_workflow_tool,
    run_powershell_command_tool,
    deploy_agent_tool,
    mute_alert_category_tool,
    get_weather_tool,
    set_reminder_tool,
    desktop_control_tool,
    web_search_tool,
    send_message_tool,
    youtube_video_tool,
    contacts_manager_tool,
    browser_control_tool,
    code_helper_tool,
    build_project_tool,
    find_flights_tool,
    game_updater_tool,
    process_file_tool,
    manage_monitors_tool,
    run_routine_tool
]}]


