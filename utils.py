import re
from googletrans import Translator
from ops_messages import translation_header

rich_emoji_string = "["\
                u"\U0001F600-\U0001F64F"\
                u"\U0001F300-\U0001F5FF"\
                u"\U0001F680-\U0001F6FF"\
                u"\U0001F1E0-\U0001F1FF"\
                u"\U00002702-\U000027B0"\
                u"\U000024C2-\U0001F251"\
                u"\U0001f926-\U0001f937"\
                u'\U00010000-\U0010ffff'\
                u"\u200d"\
                u"\u2640-\u2642"\
                u"\u2600-\u2B55"\
                u"\u23cf"\
                u"\u23e9"\
                u"\u231a"\
                u"\u3030"\
                u"\ufe0f"\
    "]+|:[\S+]+:|\n+"
rich_emoji_pattern = re.compile(rich_emoji_string, flags=re.UNICODE)
rich_emoji_pattern_zh = re.compile(rich_emoji_string.replace(
                                                 u"\U000024C2-\U0001F251",""),
                                  flags=re.UNICODE)
mt_translator = Translator()

def emoji_header_clean(message, target_lang):
    header = (translation_header.get(target_lang) or\
              translation_header['en'])
    clean_message = header['regex'].sub(r'', message)
    if target_lang == 'zh-CN':
        clean_message = rich_emoji_pattern_zh.sub(r'', clean_message)
    else:
        clean_message = rich_emoji_pattern.sub(r'', clean_message)
    return clean_message

def translate_message(message_text, target_lang, source_lang='ca'):
    #Cuts the message from emojis
    if len(re.findall(rich_emoji_pattern, message_text)) == 0:
        translated_message = mt_translator.translate(message_text,
                                                     src=source_lang,
                                                     dest=target_lang).text
    else:
        translated_message = ''
        last_end = 0
        source_segments = []
        source_tokens = []
        result_segments = []
        for token in re.finditer(rich_emoji_pattern, message_text):
            begin = token.span()[0]
            end = token.span()[1]
            source_segments.append(message_text[last_end:begin])
            source_tokens.append(token.group())
            last_end = end
        if end < len(message_text):
            source_segments.append(message_text[last_end:])

        for text_portion_to_translate in source_segments:
            if text_portion_to_translate and not text_portion_to_translate.isspace(): 
                try:
                    result_segments.append(mt_translator.translate(\
                                                    text_portion_to_translate,
                                                    src=source_lang,
                                                    dest=target_lang).text)
                except:
                    print("ERROR: Couldn't translate segment")
                    print("|" + text_portion_to_translate+ "|")
            if source_tokens:
                result_segments.append(source_tokens.pop(0))

    return ' '.join(result_segments)
