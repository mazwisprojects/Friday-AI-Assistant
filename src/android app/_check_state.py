import re
f = 'app/src/main/kotlin/com/friday/remote/network/FridaySocketManager.kt'
content = open(f, encoding='utf-8').read()
lines = content.split('\n')
print(f'Total lines: {len(lines)}')

checks = [
    ('data class FridayTask', 'FridayTask data class'),
    ('data class AutonomyStatus', 'AutonomyStatus data class'),
    ('data class FridayReminder', 'FridayReminder data class'),
    ('_tasks = MutableStateFlow', '_tasks StateFlow'),
    ('_autonomyStatus = MutableStateFlow', '_autonomyStatus StateFlow'),
    ('_reminders = MutableStateFlow', '_reminders StateFlow'),
    ('get_task_cards', 'get_task_cards emit'),
    ('task_action', 'task_action emit'),
    ('get_autonomy_status', 'get_autonomy_status emit'),
    ('approve_autonomy_proposal', 'approve_autonomy_proposal emit'),
    ('resolve_security_finding', 'resolve_security_finding emit'),
    ('get_reminders', 'get_reminders emit'),
    ('add_reminder', 'add_reminder emit'),
    ('delete_reminder', 'delete_reminder emit'),
    ('onTaskCards', 'onTaskCards handler'),
    ('onTaskActionResponse', 'onTaskActionResponse handler'),
    ('onAutonomyStatus', 'onAutonomyStatus handler'),
    ('onAutonomyApprovalResult', 'onAutonomyApprovalResult handler'),
    ('onRemindersList', 'onRemindersList handler'),
    ('onUnifiedNotification', 'onUnifiedNotification handler'),
    ('performTaskAction', 'performTaskAction method'),
    ('approveAutonomyProposal', 'approveAutonomyProposal method'),
    ('resolveSecurityFinding', 'resolveSecurityFinding method'),
    ('getReminders', 'getReminders method'),
    ('addReminder', 'addReminder method'),
    ('deleteReminder', 'deleteReminder method'),
]

for pattern, label in checks:
    print(f'  {label}: {pattern in content}')

# Check socket listeners in connect
sockets = re.findall(r'socket\?\.on\("(\w+)"', content)
print(f'\nAll socket listeners: {sockets}')

print('\nSocket listener checks:')
for l in ['task_cards','task_action_response','autonomy_status','autonomy_approval_result','reminders_list','unified_notification']:
    print(f'  "{l}": {l in sockets}')
