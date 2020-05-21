import re
import yaml
import json
import telebot
import config

from gtts import gTTS
from utils import *
from tasks_db import *
from ops_messages import *

bot = telebot.TeleBot(config.config['token'])
dbs = {lang:TasksDB(collection_name=lang) for lang in config.collections}
groups = config.config['groups']

@bot.message_handler(commands=['help'])
def command_help(message):
    # Prints help
    if message.chat.title not in config.config['groups'].keys():
        out_message = "WARNING: Group not yet added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        print(message.chat)
    else:
        out_message = HELP_TEXT
    bot.send_message(chat_id=message.chat.id, text=out_message)

@bot.channel_post_handler(content_types=['text', 'photo', 'video'])
def channel_listener(message):
    # Listens to the source channels in config
    source_channel = message.chat.username

    if source_channel not in config.source_channels:
        print('%s not in %s'%(source_channel, config.source_channels.keys()))
        return None

    for translator_group in \
                  config.source_channels[source_channel]['translator groups']:
        # Get translator group specific values
        target_channel = [target for source, target in \
                         groups[translator_group]['source vs target channels']
                         if source == source_channel][0]
        translators_group_id, collection, (source_lang, target_lang) = \
                                            get_group_values(translator_group)

        # Check if message has text
        message_with_text = False
        forward = True
        new_task = {'translated': False,
                    'src_channel_name': source_channel,
                    'tgt_channel_name': target_channel}
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
                bot.forward_message('@' + target_channel,
                                    '@' + source_channel,
                                    message.message_id)
        else:
            # Send message text to MT
            try:
                message_tr = translate_message(message_text_content,
                                               target_lang=target_lang,
                                               source_lang=source_lang)
                new_task['mt_message'] = message_tr
            except:
                # TODO from ops_messages
                message_tr = "(ERROR: Couldn't send message to machine translation)"
            header = (translation_header.get(target_lang) or\
                      translation_header['en'])
            mt_message_text = header['default']%(message.chat.title,
                                           source_channel, message_tr)

            new_task['task_taker'] = None
            new_task['task_originalmessage'] =  message.json
            new_task['content_type'] = message.content_type
            with open('debug.json', 'w') as out:
                json.dump(new_task, out)
            translation_task_id = dbs[collection].insert_task(new_task)

            # TODO is saving request task really necessary?
            request_text = REQUEST_TEXT%(
                                new_task['task_originalmessage']['chat']['title'],
                                                                  new_task['_id'],
                         new_task['task_originalmessage'][new_task['text_field']],
                                                                  new_task['_id'])


            request_message = bot.send_message(chat_id=translators_group_id,
                                               text=request_text)
            mt_message = bot.send_message(chat_id=translators_group_id,
                                          text = mt_message_text)

            # save the message id of the request message in translators group
            new_task['request_message_id'] = request_message.json['message_id']
            dbs[collection].update_task(new_task)

@bot.message_handler(commands=['take'])
def command_take(message):
    # Function to allow the user to take task
    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, source_target = \
                                            get_group_values(translator_group)

    # Check if poster set username
    id_message_to_translate = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None

    # Check if the user has a task assigned
    found_task = dbs[collection].get_nontranslated_of_user(requester_username)
    if found_task:
        bot.send_message(chat_id=translators_group_id,
                         text="You can take only one task at a time. "\
                              "You currently have %i assigned to you."\
                              ""%found_task["_id"]) 
        return None
 
    # parse the take command for task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=translators_group_id,
           text="Please include ID of the task you want to take. e.g. /take 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=translators_group_id,
                     text="You can take only one task at a time. e.g. /take 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_translate = int(parameters[0])
        except:
            bot.send_message(chat_id=translators_group_id,
                             text="Bad task ID. Please include ID of the "\
                                  "task you want to take. e.g. /take 5")
            # TODO text from text list 
    if id_message_to_translate:
        found_task = dbs[collection].get(id_message_to_translate)
        if found_task:
            # TODO check if task cancelled if so don't allow "take"
            # found task could already been translated
            # but in this case it would say it is assigned to someone
            # since only nontranslated tasks can be dropped 
            taker_assigned = found_task.get('task_taker')
            if taker_assigned:
                # message has a translator assigned
                if taker_assigned == requester_username:
                    bot.send_message(chat_id=translators_group_id,
                                     text="You (%s) already took on "\
                                          "task %i."%(requester_username,
                                                      id_message_to_translate))
                    # TODO text from text list
                else:
                    bot.send_message(chat_id=translators_group_id,
                                     text="Task already taken by "\
                                          "%s"%found_task['task_taker'])
                    # TODO text from text list
            else:
                # message does not have a translator
                user_taken_task = None
                for active_task in dbs[collection].get_active_tasks():
                    # check if user has another task
                    if active_task['task_taker'] == requester_username:
                        user_taken_task_id = active_task['_id']
                        break

                if user_taken_task:
                    bot.send_message(chat_id=translators_group_id,
                                     text="You (%s) already have task %i "\
                                          "assigned to you. \nIf you want "\
                              "to drop this task: /drop"%(requester_username,
                                                          user_taken_task_id))
                    # TODO text from text list
                else:
                    # Give translation task to user
                    task = dbs[collection].get(id_message_to_translate)
                    task['task_taker'] = requester_username
                    dbs[collection].update_task(task)
                    bot.send_message(chat_id=translators_group_id,
                                     text="Task %i granted to %s.\nNext "\
                                          "message posted by them will "\
                                          "be considered as a translation "\
                                          "submission."%(id_message_to_translate,
                                                         requester_username))
                    # TODO text from text list
        else:
            # if task not found
            nontaken_tasks = [t for t in dbs[collection].get_passive_tasks()]
            if len(nontaken_tasks) == 0:
                bot.send_message(chat_id=translators_group_id,
                                 text="There are currently no active tasks.")
            else:
                str_nontaken_request_ids = ", ".join([str(task['_id']) \
                                                  for task in nontaken_tasks])
                bot.send_message(chat_id=translators_group_id,
                                 text="No task found with ID %i.\n"\
                                      "Active task IDs:"\
                                      " %s"%(id_message_to_translate,
                                             str_nontaken_request_ids))
                #TODO text from text list

def get_poster_name(message):
    return message.from_user.username

def get_group_values(translator_group):
    translators_group_id = groups[translator_group]['id']
    collection = (groups[translator_group].get('db') or \
                  groups[translator_group]['target language'])
    source_lang = groups[translator_group]['source language']
    target_lang = groups[translator_group]['target language']

    return translators_group_id, collection, (source_lang, target_lang)

@bot.message_handler(commands=['task', 'tasks'])
def command_tasks(message):
    # Shows a list of tasks to the user

    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, source_target =\
                                            get_group_values(translator_group)


    active_tasks = [t for t in dbs[collection].get_nontranslated_tasks()]
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

    bot.send_message(chat_id=translators_group_id,
                     text=out_message)

@bot.message_handler(commands=['drop'])
def command_drop(message):
    # Drops the task from the user
    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, source_target =\
                                            get_group_values(translator_group)


    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None

    found_task = dbs[collection].get_nontranslated_of_user(requester_username)
    if found_task:
        found_task['task_taker'] = None
        dbs[collection].update_task(found_task)
        bot.send_message(chat_id=translators_group_id,
                         text="%s has dropped task %i. To take this task type:"\
                              " /take %i"%(requester_username,
                                           found_task["_id"], found_task["_id"]))
    else:
        bot.send_message(chat_id=translators_group_id,
                         text="You (%s) do not have any task on you."%(requester_username))

@bot.message_handler(commands=['goto'])
def command_goto(message):    
    # References to the task message

    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, source_target =\
                                            get_group_values(translator_group)

    # Check if username is set
    id_message_to_translate = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # parse the task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=translators_group_id,
                         text="Please include ID of the task you want to see."\
                              " e.g. /goto 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=translators_group_id,
                         text="You can request one task to see. e.g. /goto 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_translate = int(parameters[0])
        except:
            bot.send_message(chat_id=translators_group_id,
                             text="Bad task ID. Please include ID of the task"\
                                  " you want to see. e.g. /goto 5")
            # TODO text from text list
    
    if id_message_to_translate:
        # check if id in db
        found_task = dbs[collection].get(id_message_to_translate)
        if found_task:
            reply_message = "Here's the message linked to task %i"\
                            ""%id_message_to_translate
            # TODO text from text list
            if found_task.get("task_taker"):
                reply_message += "\nTask taken by %s"%found_task['task_taker']
            # TODO text from text list
            if found_task.get('request_message_id'):
                bot.send_message(chat_id=translators_group_id,
                         reply_to_message_id=found_task['request_message_id'],
                         text=reply_message)
            else:
                bot.send_message(chat_id=translators_group_id,
                                 text="Unexpected DB error.")
                # TODO text from text list
        else:
            bot.send_message(chat_id=translators_group_id,
                             text="No task found with ID %i."\
                                  ""%(id_message_to_translate))

@bot.message_handler(commands=['send'])
def command_confirm(message):
    # Confirm and send the submission to the target channel

    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, (source_lang, target_lang) =\
                                            get_group_values(translator_group)
    tts_lang = (groups[translator_group].get('tts language') or\
                groups[translator_group]['target language'])

    # Check if username is set
    poster = get_poster_name(message)
    if not poster:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)

    # Check if poster has a task due, if not don't do anything
    found_submissions = [t for t in \
                        dbs[collection].get_nontranslated_submitted_tasks(poster)]

    if found_submissions:
        if len(found_submissions) > 1:
            # TODO logging
            print('WARNING multiple submissions found')

        found_task = found_submissions[0]
        # send submission to channel
        try:
            if found_task['content_type'] == 'text':
                bot.send_message(chat_id="@" + found_task['tgt_channel_name'],
                                 text=found_task['submission']['text'])
            elif found_task['content_type'] == 'photo':
                bot.send_photo("@" + found_task['tgt_channel_name'],
                  found_task['task_originalmessage']['photo'][-1]['file_id'],
                               caption=found_task['submission']['text'])
            elif found_task['content_type'] == 'video':
                bot.send_video("@" + found_task['tgt_channel_name'],
                    found_task['task_originalmessage']['video']['file_id'],
                    caption=found_task['submission']['text'])
        except Exception as e:
            bot.send_message(chat_id=translators_group_id,
                             text=str(e))
            return None
            
        bot.send_message(chat_id=translators_group_id,
                         text="Task %i completed. Translated message posted "\
                              "in t.me/%s"%(found_task["_id"],
                                            found_task['tgt_channel_name']))
        # TODO text from text list
        
        #Send audio
        msg_to_tts = emoji_header_clean(\
                            found_task['submission']['text'], target_lang)

        try:
            myobj = gTTS(text=msg_to_tts, lang=tts_lang)
            myobj.save("message.mp3")
            audio = open('message.mp3', 'rb')
            bot.send_voice("@" + found_task['tgt_channel_name'], audio)
        except:
            print("Message cannot be sent to TTS")
        found_task['translated'] = True
        dbs[collection].update_task(found_task)
    else:
        bot.send_message(chat_id=translators_group_id,
                         text="You (%s) haven't submitted any translation "\
                              "to confirm."%(poster))
        # TODO text from text list

@bot.message_handler(commands=['cancel'])
def command_cancel(message):
    # Remove the task from the task list

    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, (source_lang, target_lang) =\
                                            get_group_values(translator_group)

    # Check if username is set
    id_message_to_cancel = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # parse the task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=translators_group_id,
                         text="Please include ID of the task you want to cancel."\
                              " e.g. /cancel 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=translators_group_id,
                         text="You can request one task to cancel. e.g. /cancel 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_cancel = int(parameters[0])
        except:
            bot.send_message(chat_id=translators_group_id,
                             text="Bad task ID. Please include ID of the task"\
                                  " you want to cancel. e.g. /cancel 5")
            # TODO text from text list

    if id_message_to_cancel:
        found_task = dbs[collection].get(id_message_to_cancel)
        if found_task:
            # found task could already been translated
            # but in this case it would say it cannot be cancelled
            # since only nontranslated tasks can be cancelled
            translated = found_task.get('translated')
            if translated:
                bot.send_message(chat_id=translators_group_id,
                                 text="Task %i is already translated, cannot "\
                                      "be cancelled."%id_message_to_cancel)
            else:
                # TODO check if it is already cancelled
                found_task['cancelled'] = True
                # in order not to have conflicts if the task is activated later
                # also cancel the task taker assignment
                found_task['task_taker'] = None
                dbs[collection].update_task(found_task)
                bot.send_message(chat_id=translators_group_id,
                                 text="Task %i cancelled. It will not "\
                                      "show up in the tasks list.\n"\
                                      "In order to revert the status use "\
                                      "/activate %i"%(id_message_to_cancel,
                                                      id_message_to_cancel))
                # TODO text from text list
        else:
            # if task not found
            bot.send_message(chat_id=translators_group_id,
                             text="No task found with ID %i."\
                                  ""%(id_message_to_cancel))
            #TODO text from text list

@bot.message_handler(commands=['activate'])
def command_cancel(message):
    # Remove the task from the task list

    if message.chat.title not in config.config['groups'].keys():
        out_message = "ERROR: Group not added to the bot's own list"\
                      ".\n%s"%HELP_TEXT
        bot.send_message(chat_id=message.chat.id, text=out_message)
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, (source_lang, target_lang) =\
                                            get_group_values(translator_group)

    # Check if username is set
    id_message_to_activate = None
    requester_username = get_poster_name(message)
    if not requester_username:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # parse the task id
    parameters = message.text.split(" ")[1:]
    if len(parameters) == 0:
        bot.send_message(chat_id=translators_group_id,
                         text="Please include ID of the task you want to activate."\
                              " e.g. /activate 5")
        # TODO text from text list
    elif len(parameters) > 1:
        bot.send_message(chat_id=translators_group_id,
                         text="You can request one task to activate. e.g. /activate 5")
        # TODO text from text list
    elif len(parameters) == 1:
        try:
            id_message_to_activate = int(parameters[0])
        except:
            bot.send_message(chat_id=translators_group_id,
                             text="Bad task ID. Please include ID of the task"\
                                  " you want to activate. e.g. /activate 5")
            # TODO text from text list

    if id_message_to_activate:
        found_task = dbs[collection].get(id_message_to_activate)
        if found_task:
            # only cancelled tasks can be activated
            cancelled = found_task.get('cancelled')
            if not cancelled:
                bot.send_message(chat_id=translators_group_id,
                                 text="Task %i is not cancelled, hence cannot"\
                                      " be activated."%id_message_to_activate)
            else:
                # TODO check if it is already cancelled
                found_task['cancelled'] = False
                dbs[collection].update_task(found_task)
                bot.send_message(chat_id=translators_group_id,
                                 text="Task %i activated. It will now "\
                                      "show up in the tasks list."\
                                      ""%(id_message_to_activate))
                # TODO text from text list
        else:
            # if task not found
            bot.send_message(chat_id=translators_group_id,
                             text="No task found with ID %i."\
                                  ""%(id_message_to_activate))
            #TODO text from text list

@bot.message_handler()
def task_submission_listener(message):
    # Listen to the task submission

    if message.chat.title not in config.config['groups'].keys():
        return None

    # Get group specific values
    translator_group = message.chat.title
    translators_group_id, collection, (source_lang, target_lang) =\
                                            get_group_values(translator_group)
    header = (translation_header.get(target_lang) or\
              translation_header['en'])

    poster = get_poster_name(message)
    if not poster:
        bot.send_message(chat_id=translators_group_id,
                         text=MSG_USERNAME_NOT_SET)
        return None
    
    # Check if poster has a task due, if not don't do anything
    found_task = dbs[collection].get_nontranslated_of_user(poster)
    if found_task:
        if not re.match(header['regex'], message.text):
            # if the header message is not put warn the task taker
            bot.send_message(chat_id=translators_group_id,
                             text="Task submission rejected. It doesn't "\
                                  "include the translation header:\n" + \
                                  header['simple']%(\
                          found_task['task_originalmessage']['chat']['title'],
                      found_task['task_originalmessage']['chat']['username']))
        else:
            # take submission and ask for confirmation if everything is ok
            found_task['submission'] = message.json
            dbs[collection].update_task(found_task)
            bot.send_message(chat_id=translators_group_id,
                             text="Translation for task %i submitted by %s. "\
                                  "In order to confirm your translation, type"\
                                  " /send. If not, your next message will "\
                               "override this submission."%(found_task["_id"],
                                                               poster))
            # TODO text from text list


