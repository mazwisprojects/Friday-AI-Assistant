import re

f = 'app/src/main/kotlin/com/friday/remote/network/FridaySocketManager.kt'
content = open(f, encoding='utf-8').read()

# Fix 1: onTaskCards - task_cards is streamed directly, not nested. 
# args[0] is the JSONArray directly
old_task_cards = '''    private fun onTaskCards(args: Array<Any?>) {
        if (args.isEmpty) return
        try {
            val arr = (args[0] as JSONObject).getJSONArray("task_cards")
            val list = ArrayList<FridayTask>()
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
    }'''

new_task_cards = '''    private fun onTaskCards(args: Array<Any?>) {
        if (args.isEmpty) return
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
    }'''

content = content.replace(old_task_cards, new_task_cards)

# Fix 2: onRemindersList - reminders_list is streamed directly too
old_reminders = '''    private fun onRemindersList(args: Array<Any?>) {
        if (args.isEmpty) return
        try {
            val arr = (args[0] as JSONObject).getJSONArray("reminders")
            val list = ArrayList<FridayReminder>()
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
    }'''

new_reminders = '''    private fun onRemindersList(args: Array<Any?>) {
        if (args.isEmpty) return
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
    }'''

content = content.replace(old_reminders, new_reminders)

# Fix 3: Remove duplicate listener block (the second "Tier 1 additions" block)
content = re.sub(
    r'\n\n            // Tier 1 additions for full F\.R\.I\.D\.A\.Y server contract\r?\n'
    r'            socket\?\.on\("task_cards"\).*?\r?\n'
    r'            socket\?\.on\("task_action_response"\).*?\r?\n'
    r'            socket\?\.on\("autonomy_status"\).*?\r?\n'
    r'            socket\?\.on\("autonomy_approval_result"\).*?\r?\n'
    r'            socket\?\.on\("reminders_list"\).*?\r?\n'
    r'            socket\?\.on\("unified_notification"\).*?\r?\n',
    '\n',
    content,
    flags=re.DOTALL
)

# Fix 4: Also remove the second copy of the listeners if they exist (for the duplicate block that might be at wrong indent)
content = re.sub(
    r'\n\n                        // Tier 1 additions for full F\.R\.I\.D\.A\.Y server contract\r?\n'
    r'                        socket\?\.on\("task_cards"\).*?\r?\n'
    r'                        socket\?\.on\("task_action_response"\).*?\r?\n'
    r'                        socket\?\.on\("autonomy_status"\).*?\r?\n'
    r'                        socket\?\.on\("autonomy_approval_result"\).*?\r?\n'
    r'                        socket\?\.on\("reminders_list"\).*?\r?\n'
    r'                        socket\?\.on\("unified_notification"\).*?\r?\n',
    '\n',
    content,
    flags=re.DOTALL
)

open(f, 'w', encoding='utf-8').write(content)
print('All fixes applied successfully')
