import curses
import curses.textpad
import re
import websocket
import urllib3
import fileinput
import ssl
from sys import argv, platform
from textwrap import wrap
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from subprocess import DEVNULL, STDOUT, check_call
from datetime import datetime
from os import system, path
from requests import get, post
try:
    import magic
except ImportError:
    import mimetypes
    print('warning: please install python-magic. this is not fatal.')
    pass
if 'win32' in platform:
    from win10toast import ToastNotifier

urllib3.disable_warnings()

settings = {
    'ip': '192.168.0.180',
    'fallback': '192.168.0.180',
    'port': '8741',
    'secure': True,
    'socket_port': '8740',
    'pass': 'toor',
    'req': 'requests',
    'post': 'send',
    'chats_scroll_factor': 2,
    'messages_scroll_factor': 5,
    'current_chat_indicator': '>',
    'my_chat_end': '╲▏',
    'their_chat_end': '▕╱',
    'chat_underline': '▔',
    'chat_vertical_offset': 1,
    'title_offset': 5,
    'chats_title': '| chats |',
    'messages_title': '| messages |',
    'input_title': '| input here :) |',
    'help_title': '| help |',
    'to_title': '| to: |',
    'compose_title': '| message: |',
    'colorscheme': 'soft',
    'help_inset': 5,
    'ping_interval': 10,
    'poll_exit': 0.5,
    'timeout': 10,
    'default_num_messages': 100,
    'default_num_chats': 30,
    'max_past_commands': 10,
    'reload_on_change': False,
    'debug': False,
}

help_message = ['COMMANDS:',
':h, :H, help - ',
'displays this help message',
'j, J - ',
'scrolls down in the selected window',
'k, K - ',
'scrolls up in the selected window',
'h, l - ',
'switches selected window between messages and conversations',
':q, exit, quit - ',
'exits the window, cleaning up. recommended over ctrl+c.',
':c, :C, chat - ',
'this should be immediately followed by a number, specifically the index of the conversation whose texts you want to view. the indices are displayed to the left of each conversation in the leftmost box. eg \':c 25\'',
':s, :S, send - ',
'starts the process for sending a text with the currently selected conversation. after you hit enter on \':s\', You will then be able to input the content of your text, and hit <enter> once you are ready to send it, or hit <esc> to cancel. You can also enter enter your text with a space between it and the \':s\', e.g.: \':s hello!\'',
':f, :F, file - ',
'sends attachments to the specified chat. Specify the files specifically as full path strings, surrounded by single or double quotes, e.g. "/home/user/Documents/file.txt" or \'/home/user/Pictures/file.jpeg\'. You can select multiple files, and they will all be send in the order that they were specified.',
':a, :A - ',
'this, along with the number of the attachment, will open the selected attachment in your browser. For example, if you see \'Attachment 5: image/jpeg\', type \':a 5\' and the attachment will be opened to be viewed in your browser',
':b, :B, bind - ',
'these allow you to change variables in settings at runtime. all available variables are displayed within lines 11 - 32 in main.py. To change one, you would simply need to do ":b <var> <val>". E.G. ":b ip 192.168.0.127". there is no need to encapsulate strings in quotes, and booleans can be typed as either true/false or True/False. If you change something that is displayed on the screen, such as window titles, the windows will not be automatically reloaded.',
':d, :D, display - ',
'this allows you view the value of any variable in settings at runtime. just type ":d <var>", and it will display its current value. E.G. ":d ping_interval"',
':r, :R, reload - ',
'this reloads the chats, getting current chats from the currently set ip address and port.',
':n, :N, new - ',
'this shows a new composition box, from which you can send a text to a new conversation (or to a conversation that you can\'t quickly access. Type in the recipient(s), then hit enter, and you\'ll be able to enter the body of the message. Once you enter the body, you won\'t be able to change the recipients. Hit ctrl+g to send the text.',
'if characters are not appearing, or the program is acting weird, just type a bunch of random characters and hit enter. No harm will be done for a bad command. For more information, visit: https://github.com/iandwelker/smserver_receiver']

color_schemes = {
    # [0]: Selected box, [1]: My text underline, [2]: their text underline
    # [3]: Unselected box, [4]: Chat indicator color, [5]: Unread indicator color,
    # [6]: Text color, [7]: Hints box color
    'default': [6, 39, 248, -1, 219, 39, 231, 9],
    'outrun': [211, 165, 238, 6, 228, 205, 231, 209],
    'coral': [202, 117, 251, 208, 207, 73, 7, 79],
    'forest': [48, 81, 95, 36, 39, 207, 253, 217],
    'soft': [152, 67, 247, 151, 44, 216, 188, 230]
}

if settings['ip'] == '' or settings['port'] == '':
    if settings['ip'] == '':
        print('Please put in your device\'s private ip to communicate with')
    if settings['port'] == '':
        print('Please put in the port that your device will be hosting the web server on. If you changed nothing, it should be port 8741.')
    exit()

class Message:
    """Message, from either person."""
    from_me = True
    content = []
    timestamp = 0
    attachments = []
    attachment_types = []
    sender = ''

    def __init__(self, c = [], ts = 0, fm = True, att = '', att_t = '', s = ''):
        self.from_me = fm
        self.content = c
        self.timestamp = int(int(ts) / 1000000000 + 978307200) # This will auto-convert it to unix timestamp
        pa = att.split(':')
        self.attachments = pa[:len(pa) - 1]
        pa_t = att_t.split(':')
        self.attachment_types = pa_t[:len(pa_t) - 1]
        self.sender = s

class Chat:
    """A conversation"""
    chat_id = ''
    display_name = ''
    has_unread = False

    def __init__(self, ci = '', dn = '', un = False):
        self.chat_id = ci
        self.display_name = dn
        self.has_unread = un

chats = []
messages = []
displayed_attachments = []
past_commands = []

current_chat_id = ''
current_chat_index = 0
num_requested_chats = 0

chat_padding = 2
chat_offset = 6

cbox_offset = 0
mbox_offset = 0

total_messages_height = 0

selected_box = 'c' # Gonna be 'm' or 'c', between cbox and mbox.

end_all = False
displaying_help = False
displaying_new = False
has_authenticated = False

def parseArgs():
    global settings
    edit_param = ''
    for i in argv[1:]:
        if i in ('--help', '-h'):
            print('Usage: python3 ./main.py [options]')
            print('Options (format as --option value, e.g. \'--port 80\')\n')
            l = len(max(settings, key=len)) + 3
            print('\tOption' + ' '*(l - len('Option')) + 'Type\tCurrent Value\n')
            for i in settings:
                t = str(type(settings[i])).split("'")[1]
                v = ("'" + settings[i] + "'") if type(settings[i]) == str else str(settings[i])
                print('\t' + i + ' '*(l-len(i)) + t + '\t' + v)
            
            exit()

        if edit_param == '':
            if i[:2] != '--' or i[2:] not in settings:
                print(f'Invalid option {i}') 
                exit()
            else:
                edit_param = i[2:]
        else:
            if type(settings[edit_param]) == int: 
                try:
                    settings[edit_param] = int(i)
                    print(f'Set {edit_param} to {i}')
                except:
                    print(f'Cannot convert \'{i}\' to type int')
                    exit()
            elif type(settings[edit_param]) == bool:
                try:
                    settings[edit_param] = True if i in ('True', 'true') else False
                    print(f'Set {edit_param} to {i}')
                except ValueError:
                    print(f'Cannot convert \'{i}\' to type bool')
                    exit()
            elif type(settings[edit_param]) == float:
                try:
                    settings[edit_param] = float(i)
                    print(f'Set {edit_param} to {i}')
                except ValueError:
                    print(f'Cannot convert \'{i}\' to type float')
                    exit()
            else:
                if edit_param == 'colorscheme' and i not in color_schemes:
                    print(f'{i} is not an available colorscheme. Available colorschemes are:')
                    for i in color_schemes:
                        print(i)
                    exit()
                print(f'Set {edit_param} to {i}')
                settings[edit_param] = i
            
            edit_param = ''

def getDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')

def getChats(num = settings['default_num_chats'], offset = 0):
    global num_requested_chats
    global has_authenticated
    if not has_authenticated:
        authenticate()

    req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['req']}?chat=0&num_chats={str(num)}&chats_offset={str(offset)}"

    num_requested_chats = num if offset == 0 else num_requested_chats + num

    try:
        new_chats = get(req_string, timeout=settings['timeout'], verify=False)
    except:
        print('Failed to actually download the chats after authenticating.')
    new_json = new_chats.json()
    chat_items = new_json['chats']
    if len(chat_items) == 0:
        authenticate()
        try:
            chat_items = get(req_string, timeout=settings['timeout'], verify=False).json()['chats']
        except:
            print('Failed to actually download the chats after authenticating.')

    if settings['debug']: print('chats_len: %d' % len(chat_items))
    return_val = []
    for i in chat_items:
        new_chat = Chat(i['chat_identifier'], i['display_name'], False if i['has_unread'] == "false" else True)
        return_val.append(new_chat)
        if settings['debug']: print("new chat:")
        if settings['debug']: print(new_chat)
        
    return return_val

def authenticate():
    global has_authenticated
    auth_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['req']}?password={settings['pass']}"
    try:
        response = get(auth_string, timeout=settings['timeout'], verify=False)
    except:
        print('Fault was in original authentication, string: %s' % auth_string)
    if response.text != 'true':
        print('Your password is wrong. Please change it and try again.')
        exit()
    has_authenticated = True

def loadInChats():
    global chats
    global chats_height
    global num_requested_chats

    if num_requested_chats != 0:
        chats += getChats(settings['default_num_chats'], num_requested_chats)

    cbox.clear()
    chats_height = (len(chats) + 1) * chat_padding
    cbox.resize(chats_height, chats_width - 2)

    for n, c in enumerate(chats, 0):
        d_name = c.display_name if c.display_name != '' else c.chat_id
        if len(d_name) > chats_width - 2 - chat_offset:
            d_name = d_name[:chats_width - 2 - chat_offset - 3] + '...'
        vert_pad = (chat_padding * n) + settings['chat_vertical_offset']
        if vert_pad >= chats_height - 1:
            break
        try:
            cbox.addstr(vert_pad, 1, str(n), curses.color_pair(7))
            cbox.addstr(vert_pad, chat_offset - 2, '•',curses.color_pair(5)) if c.has_unread else 0
            cbox.addstr(vert_pad, chat_offset, d_name, curses.color_pair(7))
        except curses.error:
            if settings['debug']: updateHbox('failed to add chat ' + str(n) + ' to box')

    updateHbox('chats loaded in')
    refreshCBox()

def reloadChats():
    global chats
    global end_all
    updateHbox('reloading chats. hold on...')
    try:
        chats = getChats()
    except:
        updateHbox('failed to connect to server. please check your host.')
        curses.echo()
        curses.nocbreak()
        curses.endwin()
        print('failed to connect to server. please check your host.')
        end_all = True
        exit()
    loadInChats()
    screen.refresh()
    updateHbox('reloaded chats!')

    if displaying_help:
        displayHelp()

def selectChat(cmd):
    global current_chat_index
    global current_chat_id
    try:
        num = int(cmd[cmd.index(' ') + 1:])
    except:
        updateHbox('you input the index incorrectly. please try again.')
        return
    
    if num >= len(chats):
        updateHbox('that index is out of range. please load more chats or try again')
        return

    if settings['debug']: updateHbox('Selected chat with ' + cmd)
    cbox.addstr((current_chat_index * 2) + settings['chat_vertical_offset'], chat_offset - 2, ' ')
    cbox.addstr((num * 2) + settings['chat_vertical_offset'], chat_offset - 2, settings['current_chat_indicator'], curses.color_pair(5))
    refreshCBox(cbox_offset)
    current_chat_id = chats[num].chat_id
    current_chat_index = num
    loadMessages(current_chat_id, settings['default_num_messages'], 0)

def getMessages(id, num = settings['default_num_messages'], offset = 0):
    global single_width
    id = id.replace('+', '%2B')

    req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['req']}?person={id}&num={str(num)}&offset={str(offset)}"
    if settings['debug']: updateHbox('req: ' + req_string)
    new_messages = get(req_string, timeout=settings['timeout'], verify=False)
    if settings['debug']: updateHbox('got new_messages')
    new_json = new_messages.json()
    if settings['debug']: updateHbox('parsed json of new messages')
    message_items = new_json['texts']
    return_val = []
    for n, i in enumerate(message_items):
        try:
            att = i['attachment_file'] if 'attachment_file' in i.keys() else ''
            att_t = i['attachment_type'] if 'attachment_type' in i.keys() else ''
            s = i['sender'] if ('sender' in i.keys() and i['sender'] != 'nil') else ''
            new_m = Message(wrap(i['text'], single_width), i['date'], True if i['is_from_me'] == '1' else False, att, att_t, s)
            return_val.append(new_m)
        except:
            updateHbox(f'failed to get message from index {str(n)}')
            pass
        if settings['debug']: updateHbox(f'unpacking item {str(n + 1)}/{str(len(message_items))}, val[:3] is {i["text"][:3]}')

    return_val.reverse()
    return return_val

def loadMessages(id, num = settings['default_num_messages'], offset = 0):
    global total_messages_height
    global messages
    global mbox_offset
    global displayed_attachments
    global single_width
    updateHbox('loading ' + ('more ' if offset != 0 else '') + 'messages. please wait...')

    if offset == 0:
        messages = getMessages(id, num, offset)
        displayed_attachments = []
    else:
        messages = getMessages(id, num, len(messages)) + messages

    total_messages_height = 0
    for n, m in enumerate(messages):
        total_messages_height += len(m.content)
        total_messages_height += len(m.attachments) + 1
        total_messages_height += 2 if n == len(messages) - 1 or m.sender != messages[n + 1].sender or m.from_me != messages[n + 1] else 1
        total_messages_height += 2 if n == 0 or m.timestamp - messages[n - 1].timestamp >= 3600 else 0
        total_messages_height += 1 if m.sender != '' and n != 0 and m.sender != messages[n - 1].sender else 0

    top_offset = 1
    if settings['debug']: updateHbox('set top offset')

    mbox.clear()
    mbox_wrapper.clear()
    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
    mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.refresh()

    if settings['debug']: updateHbox('set mw attr, tmh:' + str(total_messages_height) + ', mw:' + str(messages_width))
    mbox.resize(total_messages_height, messages_width - 2)

    for n, m in enumerate(messages):
        if settings['debug']: updateHbox('entered message enumeration on item ' + str(n + 1))
        longest_att = 0
        for i in m.attachment_types:
            if len('Attachment 00: ' + i) > longest_att:
                longest_att = len('Attachment 00: ' + i)

        text_width = max(len(i) for i in m.content) if len(m.content) > 0 else 0
        text_width = min(max(text_width, longest_att), single_width)
        if settings['debug']: updateHbox('passed text_width for item ' + str(n + 1))
        left_padding = 0
        underline = settings['their_chat_end'] + settings['chat_underline']*(text_width - len(settings['their_chat_end']) + 1)
        if settings['debug']: updateHbox('set first section of message ' + str(n + 1) + ', to = ' + str(top_offset) + ', h = ' + str(total_messages_height))

        if n == 0 or m.timestamp - messages[n - 1].timestamp >= 3600:
            if settings['debug']: updateHbox('checking timestamps on item ' + str(n + 1))
            time_string = getDate(m.timestamp)
            if settings['debug']: updateHbox('got string on item ' + str(n + 1) + '. m=' + str(m.timestamp) + ' & n+1=' + str(messages[n-1].timestamp))
            mbox.addstr(top_offset, int((messages_width - 2 - len(time_string)) / 2), time_string, curses.color_pair(7))
            if settings['debug']: updateHbox('added time string on item ' + str(n))
            top_offset += 2

        if m.from_me == True:
            if settings['debug']: updateHbox('entered if_from_me for item ' + str(n + 1))
            left_padding = messages_width - 3 - text_width # I feel like it shouldn't be 3 but ok
            if settings['debug']: updateHbox('set left padding on item ' + str(n + 1))
            underline = settings['chat_underline']*(text_width - len(settings['my_chat_end'])) + settings['my_chat_end']
            if settings['debug']: updateHbox('past setting underline on item ' + str(n + 1))

        if m.sender != '' and n != 0 and m.sender != messages[n - 1].sender:
            if settings['debug']: updateHbox('Entered sender section on item ' + str(n + 1))
            mbox.addstr(top_offset, left_padding, m.sender)
            top_offset += 1

        for i in range(len(m.attachments)):
            if settings['debug']: updateHbox('Entered attachments section on item ' + str(n + 1))
            att_str = 'Attachment ' + str(len(displayed_attachments)) + ': '
            att_str += m.attachment_types[i][:single_width - len(att_str)]
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, att_str, curses.color_pair(7))
            displayed_attachments.append(str(m.attachments[i]))
            top_offset += 1

        for j, l in enumerate(m.content):
            if settings['debug']: updateHbox('On item ' + str(j + 1) + ' of content on item ' + str(n + 1))
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, l, curses.color_pair(7))
            top_offset += 1

        if n == len(messages) - 1 or (m.sender != '' and m.sender == messages[n + 1].sender) or m.from_me == messages[n + 1].from_me: underline = settings['chat_underline']*len(underline)

        if settings['debug']: updateHbox('settings underline on item ' + str(n))
        mbox.addstr(top_offset, left_padding, underline, curses.color_pair(2) if m.from_me else curses.color_pair(3)) if text_width > 0 else 0
        top_offset += 2 if n != len(messages) - 1 and m.sender != messages[n + 1].sender else 1

        if settings['debug']: updateHbox('added text ' + str(n) + '/' + str(num))

    total_messages_height = top_offset + 1
    mbox_offset = offset
    refreshMBox(mbox_offset)
    updateHbox('loaded Messages!')

def refreshCBox(down = cbox_offset):
    if down < 0:
        return
    cbox.refresh(down, 0, 1, 1, t_y - 2, chats_width - 2)

def refreshMBox(down = mbox_offset):
    if down < 0:
        return
    mbox.refresh(total_messages_height - down - messages_height, 0, 1, chats_width + 2, t_y - 2, cols - 2)

def getTboxText():
    global t_width
    global past_commands
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    right_offset = 0
    past_command_offset = -1
    
    # This whole section is a nightmare. But it seems to work...?
    while True:
        ch = tbox.getch(1, min(1 + len(whole_string) - right_offset, t_width - 2) if len(whole_string) < t_width - 2 else t_width - 2 - right_offset)
        if (chr(ch) in ('j', 'J', '^[B') and len(whole_string) == 0):
            scrollDown()
        elif (chr(ch) in ('k', 'K', '^[A') and len(whole_string) == 0):
            scrollUp()
        elif (chr(ch) in ('l', 'L', 'h', 'H') and len(whole_string) == 0): 
            switchSelected()
        elif ch in (curses.KEY_UP,) and len(past_commands) > 0:
            past_command_offset += 1 if past_command_offset < len(past_commands) - 1 else 0
            whole_string = past_commands[min(past_command_offset, settings['max_past_commands'] - 1)][:t_width - 2]
            if settings['debug']: updateHbox('up; set whole_string, pco is ' + str(past_command_offset))
            tbox.addstr(1, 1, whole_string + ' '*(t_width - 2 - len(whole_string)))
        elif ch in (curses.KEY_DOWN,):
            past_command_offset -= 1 if past_command_offset >= 0 else 0
            whole_string = past_commands[past_command_offset][:t_width - 2] if past_command_offset != -1 else ''
            if settings['debug']: updateHbox('down; set whole_string, pco is ' + str(past_command_offset))
            tbox.addstr(1, 1, whole_string + ' '*(t_width - 2 - len(whole_string)))
        elif ch in (10, curses.KEY_ENTER):
            return whole_string
        elif ch in (127, curses.KEY_BACKSPACE):
            if right_offset == 0:
                whole_string = whole_string[:len(whole_string) - 1]
            else:
                whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
            tbox.addstr(1, 1, str(whole_string + ' '*max((t_width - len(whole_string) - 3), 0))[max((len(whole_string) - t_width + 3), 0):])
        elif ch in (curses.KEY_LEFT,):
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,):
            right_offset -= 1 if right_offset > 0 else 0
        elif ch in (27, curses.KEY_CANCEL,):
            return ''
        elif len(chr(ch)) == 1: 
            if right_offset != 0:
                whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
            else:
                whole_string += chr(ch)
            
            if len(whole_string) < t_width - 2:
                tbox.addstr(1, 1, whole_string)
            else:
                tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 3:])
                
    if settings['debug']: updateHbox('returning whole_string from tbox')
    return whole_string

def sendTextCmd(cmd):
    global current_chat_id
    if current_chat_id == '':
        updateHbox('you have not selected a conversation. please do so before attempting to send texts')
        return
    if cmd.rstrip() in (':s', ':S', 'send'):
        updateHbox('please enter the content of your text! note that as soon as you hit enter, the text will be sent :)')
        new_text = getTextText()
    else:
        new_text = cmd[3:]
    if new_text == '':
        updateHbox('cancelled; text was not sent.')
        return
        
    vals = {'text': new_text, 'chat': current_chat_id}
    req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['post']}"
    if settings['debug']: updateHbox('set req_string')
    try:
        post(req_string, files={"attachments": (None, '0')}, data=vals, timeout=settings['timeout'], verify=False) # You have to put some value for files or the server will crash; idk why tho
        updateHbox('text sent!')
    except: 
        updateHbox('failed to send text :(')

    sleep(0.1)
    onMsg(None, 'text:' + current_chat_id, from_me = True)

def sendFileCmd(cmd):
    global current_chat_id
    if settings['debug']: updateHbox('entered file cmd')

    if current_chat_id == '':
        updateHbox('you have not selected a conversation. please do so before attempting to send texts')
        return

    req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['post']}"
    vals = {'chat': current_chat_id}
    strings = [f for f in re.split('\'|"', cmd[3:]) if len(f.strip()) != 0]
    files = []

    if settings['debug']: updateHbox('set initiail vars')

    for f in strings:
        if not path.isfile(f):
            updateHbox('one of your files did not exist, please try again')
            return
        if settings['debug']: updateHbox('setting mime type for file ')
        mime_type = ''
        try:
            mime_type = magic.from_file(f, mime=True)
        except:
            mime_type = mimetypes.MimeTypes().guess_type(f)[0]
        if settings['debug']: updateHbox('got mime type')
        filename = f.split('/')[-1]
        if settings['debug']: updateHbox('split filename')
        files.append((str(filename), open(f, 'rb'), str(mime_type)))
        if settings['debug']: updateHbox('appended to files')

    if settings['debug']: updateHbox('exited for')

    for f in files:
        file_post = {'attachments': f}
        post(req_string, files=file_post, data=vals, verify=False)

    updateHbox('sent it!')

def getTextText():
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    right_offset = 0
    while True:
        ch = tbox.getch(1, min(1 + len(whole_string) - right_offset, t_width - 2) if len(whole_string) < t_width - 2 else t_width - 2 - right_offset)
        if ch in (27, curses.KEY_CANCEL):
            return ''
        elif ch in (10, curses.KEY_ENTER):
            return whole_string
        elif ch in (127, curses.KEY_BACKSPACE):
            whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:] # This should work even when right_offset == 0
                
            tbox.addstr(1, 1, str(whole_string + ' '*max((t_width - len(whole_string) - 3), 0))[max((len(whole_string) - t_width + 3), 0):])

        elif ch in (curses.KEY_LEFT,):
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,):
            right_offset -= 1 if right_offset > 0 else 0
        elif len(chr(ch)) == 1:
            whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:] # Should work even when right_offset == 0

            if len(whole_string) < t_width - 2:
                tbox.addstr(1, 1, whole_string)
            else:
                tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 3:])

def updateHbox(string):
    hbox.clear()
    hbox.addstr(0, 0, string, curses.color_pair(8))
    hbox.refresh()

def switchSelected():
    global selected_box
    global mbox_offset
    global cbox_offset
    selected_box = 'c' if selected_box == 'm' else 'm'

    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
    mbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(1))
    mbox_wrapper.refresh()
    refreshMBox(mbox_offset)

    cbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'c' else cbox_wrapper.attron(curses.color_pair(4))
    cbox_wrapper.box()
    cbox_wrapper.addstr(0, settings['title_offset'], settings['chats_title'])
    cbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'c' else cbox_wrapper.attron(curses.color_pair(1))
    cbox_wrapper.refresh()
    refreshCBox(cbox_offset)

def scrollUp():
    global selected_box
    global mbox_offset
    global cbox_offset
    global total_messages_height
    global messages

    if selected_box == 'm':
        if settings['debug']: updateHbox('scrolling m box, offset is ' + str(mbox_offset) + ', total height is ' + str(total_messages_height))
        if mbox_offset < total_messages_height - messages_height:
            mbox_offset += settings['messages_scroll_factor']
        elif len(messages) >= settings['default_num_messages']:
            loadMessages(current_chat_id, settings['default_num_messages'], mbox_offset - settings['messages_scroll_factor'])
        refreshMBox(mbox_offset)
    else:
        cbox_offset -= settings['chats_scroll_factor'] if cbox_offset > 0 else 0
        refreshCBox(cbox_offset)

def scrollDown():
    global selected_box
    global mbox_offset
    global cbox_offset
    global chats
    if selected_box == 'm':
        if settings['debug']: updateHbox('scrolling m down, offset is ' + str(mbox_offset))
        mbox_offset -= settings['messages_scroll_factor'] if mbox_offset > 0 else 0
        refreshMBox(mbox_offset)
    else:
        if cbox_offset + settings['chats_scroll_factor'] >= chats_height - cbox_wrapper_height - 2:
            updateHbox('Updating chats...')
            loadInChats()
        else:
            if settings['debug']: updateHbox('just scrolling')
            cbox_offset += settings['chats_scroll_factor'] if cbox_offset < chats_height - cbox_wrapper_height - 2 else 0
        refreshCBox(cbox_offset)

def displayHelp():
    global displaying_help
    updateHbox('displaying help')

    curses.noecho()

    help_height = int(rows * 0.6)
    help_width = int(cols * 0.6)
    help_x = int((cols - help_width) / 2)
    help_y = int((rows - help_height) / 2)
    help_offset = 0

    help_messages_wrapped = [[]]
    
    for n, l in enumerate(help_message):
        help_messages_wrapped.append(wrap(l, help_width - 2) if n % 2 == 1 and not n == 0 else wrap(l, help_width - 2 - settings['help_inset']))

    text_rows = sum(len(m) for m in help_messages_wrapped)

    hbox_wrapper = curses.newwin(help_height, help_width, help_y, help_x)
    hbox_wrapper.attron(curses.color_pair(1))
    hbox_wrapper.box()
    hbox_wrapper.addstr(0, settings['title_offset'], settings['help_title'])
    hbox_wrapper.attron(curses.color_pair(4))
    hbox_wrapper.refresh()

    help_box = curses.newpad(text_rows + 2, help_width - 2)
    help_box.keypad(1)
    top_offset = 0

    for n, m in enumerate(help_messages_wrapped):
        for r in m:
            help_box.addstr(top_offset, 0, r if n % 2 == 0 or n == 1 else ' '*settings['help_inset'] + r)
            top_offset += 1

    help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)

    displaying_help = True

    while True:
        c = screen.getch()
        if chr(c) in ('j', 'J', '^[B') or c == curses.KEY_DOWN:
            help_offset += 1 if help_offset < text_rows - help_height + 2 else 0
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 1)
        elif chr(c) in ('k', 'K', '^[A') or c == curses.KEY_UP:
            help_offset -= 1 if help_offset > 0 else 0
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)
        elif chr(c) in ('q', 'Q'):
            break
        if settings['debug']: updateHbox('scrolling, rows is ' + str(text_rows) + ', height is ' + str(help_height) + ', offset is ' + str(help_offset))
    
    hbox_wrapper.clear()
    hbox_wrapper.refresh()
    help_box.clear()
    help_box.refresh(0, 0, 0, 0, 0, 0)
    del hbox_wrapper
    del help_box

    displaying_help = False

    switchSelected()
    switchSelected()

    updateHbox('enter a command, or type :h to get help!')

def setVar(cmd):
    firstSpace = cmd.find(' ')
    secondSpace = cmd.find(' ', firstSpace + 1)
    var = cmd[firstSpace + 1:secondSpace]
    val = cmd[secondSpace + 1:]
    oldval = settings[var]

    if var == 'colorscheme' and val not in color_schemes.keys():
        updateHbox(val + ' is not an existing colorscheme.')
        return

    if var not in settings:
        updateHbox('variable (' + var + ') not found.')
        return

    if type(settings[var]) == int and not val.isdigit():
        updateHbox('bad input type for ' + var + ' (must be int)')
        return
    elif type(settings[var]) == bool and val not in ('False', 'True', 'false', 'true'):
        updateHbox('bad input type for ' + var + ' (must be bool)')
        return

    if type(settings[var]) == int:
        if settings['debug']: updateHbox('type is int')
        settings[var] = int(val)
    elif type(settings[var]) == float:
        if settings['debug']: updateHbox('type is float') 
        settings[var] = float(val)
    elif type(settings[var]) == bool:
        if settings['debug']: updateHbox('type is bool')
        settings[var] = True if val in ('True', 'true') else False
    else:
        if settings['debug']: updateHbox('type is str')
        settings[var] = val
    
    if type(oldval) == str:
        val = "'" + val + "'"
        oldval = "'" + oldval + "'"
    elif type(oldval) == bool:
        val = 'True' if val in ('true', 'True') else 'False'

    if platform in ('linux', 'freebsd', 'openbsd'):
        sed_string = 'sed -i "s/\'' + var + '\': ' + str(oldval) + '/\'' + var + '\': ' + str(val) + '/" ' + path.realpath(__file__)
        system(sed_string)
    elif platform == 'darwin':
        sed_string = 'sed -i \'\' -e "s+\'' + var + '\': ' + str(oldval) + '+\'' + var + '\': ' + str(val) + '+" ' + path.realpath(__file__)
        system(sed_string)

    updateHbox('updated ' + var + ' to ' + val)

def showVar(cmd):
    var = cmd[cmd.find(' ') + 1:]

    if var not in settings:
        updateHbox('variable not found.')
    else:
        updateHbox('current value: ' + str(settings[var]))

def openAttachment(att_num):
    global displayed_attachments
    if len(displayed_attachments) <= int(att_num):
        updateHbox('attachment ' + str(att_num) + ' does not exist.')
        return
    http_string = f'http{"s" if settings["secure"] else ""}://{settings["ip"]}:{settings["port"]}/data?path={str(displayed_attachments[int(att_num)]).replace(" ", "%20")}'
    
    if 'darwin' in platform:
        check_call(['open', http_string], stdout=DEVNULL, stderr=STDOUT)
    elif platform in ('linux', 'freebsd', 'openbsd'):
        check_call(['xdg-open', http_string], stdout=DEVNULL, stderr=STDOUT)
    elif 'win32' in platform:
        system('explorer "' + http_string + '"')
    
def newComposition():
    global displaying_new
    
    to_height = 3
    to_width = int(cols * 0.7)

    new_height = int(rows * 0.7) - to_height
    new_width = int(cols * 0.7)
    new_x = int((cols - new_width) / 2)
    new_y = int((rows - new_height) / 2) + to_height

    to_x = int((cols - to_width) / 2)
    to_y = new_y - to_height

    to_box = curses.newwin(to_height, to_width, to_y, to_x)
    to_box.attron(curses.color_pair(1))
    to_box.box()
    to_box.addstr(0, settings['title_offset'], settings['to_title'])
    to_box.attron(curses.color_pair(7))
    to_box.refresh()

    comp_box = curses.newwin(new_height, new_width, new_y, new_x)
    comp_box.attron(curses.color_pair(4))
    comp_box.box()
    comp_box.addstr(0, settings['title_offset'], settings['compose_title'])
    comp_box.addstr(new_height - 1, settings['title_offset'], '| ctrl+g to send |')
    comp_box.attron(curses.color_pair(7))
    comp_box.refresh()

    sub_comp = curses.newwin(new_height - 2, new_width - 2, new_y + 1, new_x + 1)
    sub_comp.keypad(1)
    edit_box = curses.textpad.Textbox(sub_comp, insert_mode=True)

    displaying_new = True

    right_offset = 0
    whole_to = ''
    whole_message = ''
    sent = False

    def msg_validator(ch):
        global whole_message
        if ch in (27, curses.KEY_CANCEL):
            whole_message = ''
            return 7
        elif ch in (127, curses.KEY_BACKSPACE):
            edit_box.do_command(curses.KEY_BACKSPACE)

        return ch

    while True:
        ch = to_box.getch(1, min(1 + len(whole_to) - right_offset, t_width - 2) if len(whole_to) < to_width - 2 else to_width - 2 - right_offset)
        if ch in (27, curses.KEY_CANCEL):
            whole_to = ''
            break
        elif ch in (10, curses.KEY_ENTER):
            break
        elif ch in (127, curses.KEY_BACKSPACE):
            whole_to = whole_to[:len(whole_to) - right_offset - 1] + whole_to[len(whole_to) - right_offset:]
            to_box.addstr(1, 1, str(whole_to + ' '*max((to_width - len(whole_to) - 3), 0))[max((len(whole_to) - to_width + 3), 0):])
        elif ch in (curses.KEY_LEFT,) and right_offset < len(whole_to):
            right_offset += 1
        elif ch in (curses.KEY_RIGHT,) and right_offset > 0:
            right_offset -= 1
        elif len(chr(ch)) == 1:
            whole_to = whole_to[:len(whole_to) - right_offset] + chr(ch) + whole_to[len(whole_to) - right_offset:]

            if len(whole_to) < to_width - 2:
                to_box.addstr(1, 1, whole_to)
            else:
                tbox.addstr(1, 1, whole_to[len(whole_to) - t_width + 3:])
                
    if len(whole_to) != 0:
        whole_message = edit_box.edit(msg_validator)

    if len(whole_message) != 0 and len(whole_to) != 0:
        vals = {'text': whole_message, 'chat': whole_to}
        req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/{settings['post']}"
        updateHbox('sending...')
        try:
            post(req_string, files={"attachments": (None, '0')}, data=vals, timeout=settings['timeout'], verify=False)
            updateHbox('text sent!')
            sent = True
        except:
            updateHbox('failed to send text :(')

    else:
        updateHbox('cancelled; text was not sent')

    to_box.clear()
    to_box.refresh()
    comp_box.clear()
    comp_box.refresh()
    del to_box
    del comp_box

    displaying_new = False

    switchSelected()
    switchSelected()

    if sent:
        reloadChats()

def onMsg(ws, msg, from_me = False):
    global current_chat_id

    prefix = msg.split(':')[0]
    content = msg.split(':')[1]

    if settings['debug']: updateHbox('rec: prefix: ' + prefix + ', content: ' + content + ', currentid: ' + current_chat_id)

    if prefix == 'text':
        if content != chats[0].chat_id:
            updateHbox('does not equal. ctn: ' + content + ', 0: ' + chats[0].chat_id)
            reloadChats()
        elif not from_me:
            cbox.addstr(settings['chat_vertical_offset'], chat_offset - 2, '•', curses.color_pair(5))
            refreshCBox()

        if content.strip() == current_chat_id:
            loadMessages(current_chat_id)

        if not from_me:
            req_string = f"http{'s' if settings['secure'] else ''}://{settings['ip']}:{settings['port']}/requests?name={content}"
            name = get(req_string, verify=False, timeout=settings['timeout']).text

            if platform in ('linux', 'freebsd', 'openbsd'): system('notify-send "you got new texts from ' + name + '!"')
            elif 'darwin' in platform: system('osascript -e \'display notification "You received new texts from ' + name + '!" with title "New Texts"\'')
            elif 'win32' in platform: ToastNotifier().show_toast('New texts!', 'You received new texts from ' + name + '!')

        updateHbox('loaded in new chats')

def recSocket():
    global socket

    socket.run_forever(sslopt={'cert_reqs': ssl.CERT_NONE})

def mainTask():
    global past_commands
    global end_all
    while not end_all:

        cmd = getTboxText()

        if settings['debug']: updateHbox('command was sent')

        if len(cmd) == 0:
            updateHbox('command cancelled.')
        elif cmd[:3] in (':s ', ':S ') or cmd[:4] == 'send':
            sendTextCmd(cmd)
        elif cmd[:3] in (':c ', ':C ') or cmd[:4] == 'chat':
            selectChat(cmd)
        elif cmd[:2] in (':f', ':F') or cmd[:4] == 'file':
            sendFileCmd(cmd)
        elif cmd in (':r', ':R', 'reload'):
            reloadChats()
        elif cmd in (':h', ':H', 'help'):
            displayHelp()
        elif cmd[:3] in (':b ', ':B ') or cmd[:4] == 'bind':
            setVar(cmd)
        elif cmd[:3] in (':d ', ':D ') or cmd[:7] == 'display':
            showVar(cmd)
        elif cmd[:3] in (':a ', ':A ') or cmd[:10] == 'attachment':
            openAttachment(cmd[3:])
        elif cmd.strip() in (':n', ':N', 'new'):
            newComposition()
        elif cmd in (':q', ':Q', 'exit', 'quit'):
            break
        else:
            updateHbox('sorry, this command isn\'t supported .')

        if len(past_commands) > 0 and len(cmd) != 0:
            past_commands = ([cmd] + past_commands[:min(len(past_commands), settings['max_past_commands'] - 1)])
        else:
            past_commands = [cmd]

    updateHbox('exiting...')
    end_all = True
        
def setupAsync():
    global end_all
    
    executor = ThreadPoolExecutor(max_workers=2)

    executor.submit(mainTask)
    executor.submit(recSocket)

    while not end_all:
        sleep(settings['poll_exit'])

    socket.close()

    print('exiting...theoretically...')
    executor.shutdown(wait=False)

parseArgs()

print('Loading ...')

try:          
    chats = getChats(settings['default_num_chats'])
except:
    print('Original ip failed, trying fallback...')
    try:
        settings['ip'] = settings['fallback']
        chats = getChats(settings['default_num_chats'])
    except: 
        print('Could not authenticate. Check to make sure your host server is running.')
        exit()

screen = curses.initscr()

curses.noecho()
curses.start_color()
curses.use_default_colors()

# pylint: disable=fixme, no-member
rows = curses.LINES
cols = curses.COLS

for i in range(len(color_schemes['default'])):
    curses.init_pair(i + 1, color_schemes[settings['colorscheme']][i], -1)

h_height = 1
h_width = cols
h_x = 0
h_y = rows - h_height

t_height = 3
t_width = h_width
t_x = 0
t_y = rows - t_height - h_height 

min_chat_width = 24
chats_width = int(cols * 0.3) if cols * 0.3 > min_chat_width else min_chat_width
chats_height = (len(chats) + settings['chat_vertical_offset']) * chat_padding
chats_x = t_x
chats_y = 0
cbox_wrapper_height = t_y

messages_width = cols - chats_width
messages_height = t_y
messages_x = chats_width + chats_x
messages_y = chats_y
single_width = int(messages_width * 0.6)

screen.clear()
screen.refresh()

cbox_wrapper = curses.newwin(cbox_wrapper_height, chats_width, chats_y, chats_x)
cbox_wrapper.attron(curses.color_pair(1))
cbox_wrapper.box()
cbox_wrapper.addstr(0, settings['title_offset'], settings['chats_title'])

cbox_wrapper.attron(curses.color_pair(4))
cbox_wrapper.refresh()
cbox_wrapper.attron(curses.color_pair(7))
cbox = curses.newpad(chats_height, chats_width - 2)
cbox.scrollok(True)

mbox_wrapper = curses.newwin(messages_height, messages_width, messages_y, messages_x)
mbox_wrapper.attron(curses.color_pair(4))
mbox_wrapper.box()
mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
mbox_wrapper.refresh()
mbox_wrapper.attron(curses.color_pair(7))
mbox = curses.newpad(messages_height - 2, messages_width - 2)
mbox.scrollok(True)

tbox = curses.newwin(t_height, t_width, t_y, t_x)
tbox.attron(curses.color_pair(4))
tbox.box()
tbox.addstr(0, settings['title_offset'], settings['input_title'])
tbox.keypad(1)
tbox.refresh()
tbox.attron(curses.color_pair(7))

hbox = curses.newwin(h_height, h_width, h_y, h_x)

screen.refresh()

loadInChats()

updateHbox('type \':h\' to get help!')

screen.refresh()

url='ws' + ('s' if settings['secure'] else '') + '://' + settings['ip'] + ':' + settings['socket_port']
socket = websocket.WebSocketApp(url, on_message = onMsg)

setupAsync()

curses.echo()
curses.endwin()

socket.close()
