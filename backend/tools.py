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
    get_weather_tool,
    set_reminder_tool,
    desktop_control_tool,
    web_search_tool,
    send_message_tool,
    youtube_video_tool
]}]


