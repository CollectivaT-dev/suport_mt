import re

'''
#Strings in target language
TRANSLATION_HEADER = "This is a translated message from the channel %s (t.me/%s).\n\n%s"
TRANSLATION_HEADER_SIMPLE = "This is a translated message from the channel %s (t.me/%s)."
TRANSLATION_HEADER_REGEX = re.compile("^This is a translated message from the channel .+ \(.+\).\n.*") #To check if it's placed well on submissions
'''
#Strings in target language
TRANSLATION_HEADER = "هذه رسالة مترجمة من قناة" + " %s (t.me/%s) \n\n%s"
TRANSLATION_HEADER_SIMPLE = "هذه رسالة مترجمة من قناة" + " %s (t.me/%s)"
TRANSLATION_HEADER_REGEX = re.compile("^" + "هذه رسالة مترجمة من قناة" + " .+ \(.+\).\n.*") #To check if it's placed well on submissions


#English strings (TODO: Carry the rest here)
MSG_USERNAME_NOT_SET = "SuportMT requires that you have a unique username to take translation tasks. Please set your username from your Telegram settings."

REQUEST_TEXT = '''
New message arrived to channel: %s
Translation task ID: %i
------------------------------
%s
------------------------------
To take this task, type: /take %i
You can use the message below as a template.'''

HELP_TEXT = '''
Command list:
/help: Displays this message
/task: List current tasks
/take <task_ID>: Take on task with <task_ID>
/goto <task_ID>: See message associated with task <task_ID>
/send: Confirm the translation just submitted to be sent out to channels
/drop: Drop task on poster 
'''
