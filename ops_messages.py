import re

# Header strings and operations in multiple languages

translation_header = {"en":{
"default": "This is a translated message from the channel %s (t.me/%s).\n\n%s",
"simple": "This is a translated message from the channel %s (t.me/%s).",
"regex": re.compile("^This is a translated message from the channel .+ \(.+\).\n.*")
},
                      "ar":{
"default": "هذه رسالة مترجمة من قناة" + " %s (t.me/%s)\n\n%s",
"simple": "هذه رسالة مترجمة من قناة" + " %s (t.me/%s)",
"regex": re.compile(".+ \(.+\).*")
},
                      "zh-CN":{
"default": "该信息翻译自" + " %s (t.me/%s) "+ "的信息\n\n%s",
"simple": "该信息翻译自" + " %s (t.me/%s) "+ "的信息",
"regex": re.compile("^"+"该信息翻译自 .+ \(.+\) 的信息\n")
},
                      "ur":{
"default": "یہ چینل کا ترجمہ شدہ پیغام ہے" + " %s (t.me/%s)\n\n%s",
"simple": "یہ چینل کا ترجمہ شدہ پیغام ہے" + " %s (t.me/%s)",
"regex": re.compile("^" + "یہ چینل کا ترجمہ شدہ پیغام ہے" + ".+ \(.+\).*")
}
                     }

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
