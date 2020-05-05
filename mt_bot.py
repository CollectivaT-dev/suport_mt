import re
import yaml
import json
import telebot
from gtts import gTTS

from utils import *
from tasks_db import *
from ops_messages import *

CONFIG = yaml.load(open('config.yml'), Loader=yaml.BaseLoader)
#target_languages = ['es', 'ar', 'test']
target_languages = ['test', 'ar'] # also collection names TODO take from yaml

bot = telebot.TeleBot(CONFIG['bot_token'])
dbs = {lang:TasksDB(collection_name=lang) for lang in target_languages}

@bot.message_handler(commands=['help'])
def command_help(message):
    # Prints help
    # TODO print text according to language
    out_message = HELP_TEXT
    bot.send_message(chat_id=CONFIG['translators_group_id'], text=out_message)

@bot.channel_post_handler(func=lambda message: message.chat.username ==\
         CONFIG['src_channel_name'], content_types=['text', 'photo', 'video'])
def channel_listener(message):
    # Listens to the given channel (listens to one channel only)
    
    # Check if message has text
    message_with_text = False
    forward = True
    new_task = {'translated': False,
                'src_channel_name': message.chat.username,
                'tgt_channel_name': CONFIG['tgt_channel_name']}
    if message.content_type in ['photo', 'video'] and\
       'caption' in message.json and message.json['caption']:
        message_with_text = True
        message_text_content = message.json['caption']
        new_task['text_field'] = 'caption'
    elif message.content_type in ['photo', 'video'] and\
         not 'caption' in message.json and\
         'media_group_id' in message.json:
        # forward only the first image when it's an album with caption 
        # (TODO: This is temporary since album photos arrive separately.
        # Later forward all as album)
        forward = False
    elif message.content_type == 'text':
        message_with_text = True
        message_text_content = message.text
        new_task['text_field'] = 'text'

    if not message_with_text:
        if forward:
            # just forward the message 
            bot.forward_message('@' + CONFIG['tgt_channel_name'],
                                '@' + message.chat.username,
                                message.message_id)
    else:
        # Send message text to MT
        try:
            message_tr = translate_message(message_text_content,
                                           target_lang=CONFIG['target_lang'],
                                           source_lang=CONFIG['source_lang'])
        except:
            # TODO from ops_messages
            message_tr = "(ERROR: Couldn't send message to machine translation)"
        mt_message_text = TRANSLATION_HEADER%(message.chat.title,
                                       message.chat.username, message_tr)

        new_task['task_taker'] = None
        new_task['task_originalmessage'] =  message.json
        new_task['content_type'] = message.content_type
        with open('debug.json', 'w') as out:
            json.dump(new_task, out)
        translation_task_id = dbs[CONFIG['target_lang']].insert_task(new_task)

        # TODO is saving request task really necessary?
        request_text = REQUEST_TEXT%(
                            new_task['task_originalmessage']['chat']['title'],
                                                              new_task['_id'],
                     new_task['task_originalmessage'][new_task['text_field']],
                                                              new_task['_id'])


        request_message = bot.send_message(chat_id=CONFIG['translators_group_id'],
                                           text=request_text)
        mt_message = bot.send_message(chat_id=CONFIG['translators_group_id'],
                                      text = mt_message_text)

        # save the message id of the request message in translators group
        new_task['request_message_id'] = request_message.json['message_id']
        dbs[CONFIG['target_lang']].update_task(new_task)

@bot.message_handler(commands=['take'])
def command_take(message):
    # Function to allow the user to take task
    id_message_to_translate = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text=MSG_USERNAME_NOT_SET)
        return #None?

    # check if the user has a task assigned
    found_task = dbs[CONFIG['target_lang']].get_nontranslated_of_user(requester_username)
    if found_task:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="You can take only one task at a time. "\
                              "You currently have %i assigned to you."\
                              ""%found_task["_id"]) 
        return None
 
    # parse the take command for task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
           text="Please include ID of the task you want to take. e.g. /take 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                     text="You can take only one task at a time. e.g. /take 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_translate = int(parameters[0])
        except:
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text="Bad task ID. Please include ID of the "\
                                  "task you want to take. e.g. /take 5")
            # TODO text from text list 
    if id_message_to_translate:
        # TODO call db from target_language
        found_task = dbs[CONFIG['target_lang']].get(id_message_to_translate)
        if found_task:
            # found task could already been translated
            # but in this case it would say it is assigned to someone
            # since only nontranslated tasks can be dropped 
            taker_assigned = found_task.get('task_taker')
            if taker_assigned:
                # message has a translator assigned
                if taker_assigned == requester_username:
                    bot.send_message(chat_id=CONFIG['translators_group_id'],
                                     text="You (%s) already took on "\
                                          "task %i."%(requester_username,
                                                      id_message_to_translate))
                    # TODO text from text list
                else:
                    bot.send_message(chat_id=CONFIG['translators_group_id'],
                                     text="Task already taken by "\
                                          "%s"%found_task['task_taker'])
                    # TODO text from text list
            else:
                # message does not have a translator
                user_taken_task = None
                for active_task in dbs[CONFIG['target_lang']].get_active_tasks():
                    # check if user has another task
                    if active_task['task_taker'] == requester_username:
                        user_taken_task_id = active_task['_id']
                        break

                if user_taken_task:
                    bot.send_message(chat_id=CONFIG['translators_group_id'],
                                     text="You (%s) already have task %i "\
                                          "assigned to you. \nIf you want "\
                              "to drop this task: /drop"%(requester_username,
                                                          user_taken_task_id))
                    # TODO text from text list
                else:
                    # Give translation task to user
                    task = dbs[CONFIG['target_lang']].get(id_message_to_translate)
                    # TODO db key from lang
                    task['task_taker'] = requester_username
                    dbs[CONFIG['target_lang']].update_task(task)
                    # TODO db key from lang
                    bot.send_message(chat_id=CONFIG['translators_group_id'],
                                     text="Task %i granted to %s.\nNext "\
                                          "message posted by them will "\
                                          "be considered as a translation "\
                                          "submission."%(id_message_to_translate,
                                                         requester_username))
                    # TODO text from text list
        else:
            # if task not found
            nontaken_tasks = [t for t in dbs[CONFIG['target_lang']].get_passive_tasks()]
            if len(nontaken_tasks) == 0:
                bot.send_message(chat_id=CONFIG['translators_group_id'],
                                 text="There are currently no active tasks.")
            else:
                str_nontaken_request_ids = ", ".join([str(task['_id']) \
                                                  for task in nontaken_tasks])
                bot.send_message(chat_id=CONFIG['translators_group_id'],
                                 text="No task found with ID %i.\n"\
                                      "Active task IDs:"\
                                      " %s"%(id_message_to_translate,
                                             str_nontaken_request_ids))
                #TODO text from text list

def get_poster_name(message):
    return message.from_user.username

@bot.message_handler(commands=['task', 'tasks'])
def command_tasks(message):
    # Shows a list of tasks to the user
    active_tasks = [t for t in dbs[CONFIG['target_lang']].get_nontranslated_tasks()]
    # TODO call db from source language
    if active_tasks:
        out_message = "%i active tasks with IDs:\n"%len(active_tasks)
        for i, active_task in enumerate(active_tasks):
            out_message += "- %i"%active_task["_id"]
            if active_task.get('task_taker'):
                if active_task.get('submitted'):
                    # element cannot be both translated: False and submitted: True
                    out_message += \
                        " (awaiting confirmation by %s)"%active_task['task_taker']
                    # TODO text from text list
                else:
                    out_message += " (taken by %s)"%active_task['task_taker']
                    # TODO text from text list
            if i+1 == len(active_tasks):
                out_message += ",\n"
            else:
                out_message += "\n"
        out_message += "In order to see a task, type /goto <task-ID> e.g. /goto 5"
        # TODO text from text list
    else:
        out_message = "No active tasks."
        # TODO text from text list

    bot.send_message(chat_id=CONFIG['translators_group_id'],
                     text=out_message)

@bot.message_handler(commands=['drop'])
def command_drop(message):
    # drops the task from the user
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text=MSG_USERNAME_NOT_SET)
        return None

    found_task = dbs[CONFIG['target_lang']].get_nontranslated_of_user(requester_username)
    if found_task:
        found_task['task_taker'] = None
        dbs[CONFIG['target_lang']].update_task(found_task)
        # TODO db call from source language
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="%s has dropped task %i. To take this task type:"\
                              " /take %i"%(requester_username,
                                           found_task["_id"], found_task["_id"]))
    else:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="You (%s) do not have any task on you."%(requester_username))

@bot.message_handler(commands=['goto'])
def command_goto(message):    
    # References to the task message
    id_message_to_translate = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # parse the task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="Please include ID of the task you want to see."\
                              " e.g. /goto 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="You can request one task to see. e.g. /goto 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_translate = int(parameters[0])
        except:
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text="Bad task ID. Please include ID of the task"\
                                  " you want to see. e.g. /take 5")
            # TODO text from text list
    
    if id_message_to_translate:
        # check if id in db
        found_task = dbs[CONFIG['target_lang']].get(id_message_to_translate)
        # TODO db call from source language
        if found_task:
            reply_message = "Here's the message linked to task %i"\
                            ""%id_message_to_translate
            # TODO text from text list
            if found_task.get("task_taker"):
                reply_message += "\nTask taken by %s"%found_task['task_taker']
            # TODO text from text list
            if found_task.get('request_message_id'):
                bot.send_message(chat_id=CONFIG['translators_group_id'],
                         reply_to_message_id=found_task['request_message_id'],
                         text=reply_message)
            else:
                bot.send_message(chat_id=CONFIG['translators_group_id'],
                                 text="Unexpected DB error.")
                # TODO text from text list
        else:
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text="No task found with ID %i."\
                                  ""%(id_message_to_translate))

@bot.message_handler(commands=['send'])
def command_confirm(message):
    # confirm and send the submission to the target channel
    poster = get_poster_name(message)
    if not poster:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    #check if poster has a task due, if not don't do anything
    found_submissions = [t for t in \
                        dbs[CONFIG['target_lang']].get_nontranslated_submitted_tasks(poster)]

    if found_submissions:
        if len(found_submissions) > 1:
            # TODO smt
            print('ERROR multiple submissions found')
            #return None
        found_task = found_submissions[0]
        # send submission to channel
        try:
            if found_task['content_type'] == 'text':
                bot.send_message(chat_id="@" + CONFIG['tgt_channel_name'],
                                 text=found_task['submission']['text'])
            elif found_task['content_type'] == 'photo':
                bot.send_photo("@" + CONFIG['tgt_channel_name'],
                  found_task['task_originalmessage']['photo'][-1]['file_id'],
                               caption=found_task['submission']['text'])
            elif found_task['content_type'] == 'video':
                bot.send_video("@" + CONFIG['tgt_channel_name'],
                    found_task['task_originalmessage']['video']['file_id'],
                    caption=found_task['submission']['text'])
        except Exception as e:
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text=str(e))
            return None
            
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="Task %i completed. Translated message posted "\
                              "in t.me/%s"%(found_task["_id"],
                                            CONFIG['tgt_channel_name']))
        # TODO text from text list
        
        #Send audio
        msg_to_tts = emoji_header_clean(\
                           found_task['submission']['text'])
        try:
            myobj = gTTS(text=msg_to_tts, lang=CONFIG['target_lang'])
            myobj.save("message.mp3")
            audio = open('message.mp3', 'rb')
            bot.send_voice("@" + CONFIG['tgt_channel_name'], audio)
        except:
            print("Message cannot be sent to TTS")
        found_task['translated'] = True
        dbs[CONFIG['target_lang']].update_task(found_task)
        # TODO db call through source language
    else:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text="You (%s) haven't submitted any translation "\
                              "to confirm."%(poster))
        # TODO text from text list

@bot.message_handler(func=lambda message: message.chat.id == \
                        int(CONFIG['translators_group_id']))
def task_submission_listener(message):
    # Listen to the task submission
    poster = get_poster_name(message)
    if not poster:
        bot.send_message(chat_id=CONFIG['translators_group_id'],
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # Check if poster has a task due, if not don't do anything
    found_task = dbs[CONFIG['target_lang']].get_nontranslated_of_user(poster)
    # TODO db call through source language
    if found_task:
        if not re.match(TRANSLATION_HEADER_REGEX, message.text):
            # if the header message is not put warn the task taker
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text="Task submission rejected. It doesn't "\
                                  "include the translation header:\n" + \
                                  TRANSLATION_HEADER_SIMPLE%(\
                          found_task['task_originalmessage']['chat']['title'],
                      found_task['task_originalmessage']['chat']['username']))
        else:
            # take submission and ask for confirmation if everything is ok
            found_task['submission'] = message.json
            dbs[CONFIG['target_lang']].update_task(found_task)
            # TODO db call through source language
            bot.send_message(chat_id=CONFIG['translators_group_id'],
                             text="Translation for task %i submitted by %s. "\
                                  "In order to confirm your translation, type"\
                                  " /send. If not, your next message will "\
                               "override this submission."%(found_task["_id"],
                                                               poster))
            # TODO text from text list


