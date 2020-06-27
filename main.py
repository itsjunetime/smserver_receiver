import curses
from requests import get
from textwrap import wrap
from time import sleep
from multiprocessing.pool import ThreadPool
import os
import sys
from datetime import datetime
# import locale

# TODO:
# [ ] Extensively test text input
# [ ] Fix help display so it shows all help messages
# [ ] Set conversation to read on device when you view it on here
# [x] TIME!! Do (ts / 1000000000) + 978307200 . I dont know why, but that's it!

settings = {
    'ip': '192.168.50.10',
    'port': '8741',
    'pass': 'toor',
    'req': 'requests',
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
    'help_inset': 5,
    'ping_interval': 60,
    'poll_exit': 0.5,
    'default_num_messages': 500,
    'default_num_chats': 40,
    'buggy_mode': True,
    'debug': False,
    'has_authenticated': False
}

help_message = ['COMMANDS:',
':h, :H, help - ',
'displays this help message',
':s, :S, send - ',
'starts the process for sending a text with the currently selected conversation. after you hit enter on \':s\', You will then be able to input the content of your text, and hit <enter> once you are ready to send it, or hit <esc> to cancel. You can also enter enter your text with a space between it and the \':s\', e.g.: \':s hello!\'',
':c, :C, chat - ',
'this should be immediately followed by a number, specifically the index of the conversation whose texts you want to view. the indices are displayed to the left of each conversation in the leftmost box. eg \':c 25\'',
'j, J - ',
'scrolls down in the selected window',
'k, K - ',
'scrolls up in the selected window',
':f, h, l - ',
'switches selected window between messages and conversations',
':q, exit, quit - ',
'exits the window, cleaning up. recommended over ctrl+c.',
':b, :B, bind - ',
'these allow you to change variables in settings at runtime. all available variables are displayed within lines 11 - 32 in main.py. To change one, you would simply need to do ":b <var> <val>". E.G. ":b ip 192.168.0.127". there is no need to encapsulate strings in quotes, and booleans can be typed as either true/false or True/False. If you change something that is displayed on the screen, such as window titles, the windows will not be automatically reloaded.',
':d, :D, display - ',
'this allows you view the value of any variable in settings at runtime. just type ":d <var>", and it will display its current value. E.G. ":d ping_interval"',
':r, :R, reload - ',
'this reloads the chats, getting current chats from the currently set ip address and port.',
'if characters are not appearing, or the program is acting weird, just type a bunch of random characters and hit enter. No harm will be done for a bad command. For more information, visit: https://github.com/iandwelker/smserver_receiver']

print('Loading ...')

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

    def __init__(self, c = [], ts = 0, fm = True):
        self.from_me = fm
        self.content = c
        self.timestamp = int(int(ts) / 1000000000 + 978307200) # This will auto-convert it to unix timestamp

class Chat:
    """A conversation"""
    chat_id = ''
    display_name = ''
    has_unread = False
    recipients = {} # Would normally just be the chatid of the one recipient. 

    def __init__(self, ci = '', rc = {}, dn = '', un = False):
        self.chat_id = ci
        self.display_name = dn
        self.recipients[ci] = dn
        self.recipients.update(rc)
        self.has_unread = un

chats = []
messages = []
current_chat_id = ''
current_chat_index = 0

chat_padding = 2
chat_offset = 6

cbox_offset = 0
mbox_offset = 0

total_messages_height = 0

selected_box = 'c' # Gonna be 'm' or 'c', between cbox and mbox.

end_all = False
displaying_help = False

def getDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')

def getChats(num = settings['default_num_chats']):
    # To authenticate
    if not settings['has_authenticated']:
        auth_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?password=' + settings['pass']
        try:
            response = get(auth_string)
        except:
            print('Fault was in original authentication, string: %s' % auth_string)
        if response.text != 'true':
            print('Your password is wrong. Please change it and try again.')
            exit()

    settings['has_authenticated'] = True

    try:
        req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?chat=0&num_chats=' + str(num)
    except:
        print('Fault was in req_string')
    # locale.setlocale(locale.LC_ALL, '')

    try:
        new_chats = get(req_string)
    except:
        print('Failed to actually download the chats after authenticating.')
    new_json = new_chats.json()
    chat_items = new_json['chats']
    if settings['debug']: print('chats_len: %d' % len(chat_items))
    return_val = []
    for i in chat_items:
        # I need to start returning recipients to this request so I can initialize chats with them
        new_chat = Chat(i['chat_identifier'], {}, i['display_name'], False if i['has_unread'] == "false" else True)
        return_val.append(new_chat)
        print("new chat:") if settings['debug'] else 0
        print(new_chat) if settings['debug'] else 0
    return return_val

def loadInChats():

    cbox.clear()
    for n, c in enumerate(chats, 0):
        d_name = c.display_name if c.display_name != '' else c.chat_id
        if len(d_name) > chats_width - 2 - chat_offset:
            d_name = d_name[:chats_width - 2 - chat_offset - 3] + '...'
        vert_pad = (chat_padding * n) + settings['chat_vertical_offset']
        if vert_pad >= chats_height - 1:
            break
        try:
            cbox.addstr(vert_pad, 1, str(n))
            cbox.addstr(vert_pad, chat_offset - 2, '•') if c.has_unread else 0
            cbox.addstr(vert_pad, chat_offset, d_name)
        except curses.error:
            pass

    refreshCBox()

def reloadChats():
    global chats
    global end_all
    updateHbox('reloading chats. hold on...')
    try:
        chats = getChats()
    except:
        updateHbox('entered except') if settings['debug'] else 0
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

    cbox.addstr((current_chat_index * 2) + settings['chat_vertical_offset'], chat_offset - 2, ' ')
    cbox.addstr((num * 2) + settings['chat_vertical_offset'], chat_offset - 2, settings['current_chat_indicator'], curses.color_pair(5))
    refreshCBox(cbox_offset)
    current_chat_id = chats[num].chat_id
    current_chat_index = num
    loadMessages(current_chat_id, settings['default_num_messages'], single_width)

def getMessages(id, num = settings['default_num_messages'], offset = 0):
    global single_width
    id = id.replace('+', '%2B')

    req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?person=' + id + '&num=' + str(num)
    updateHbox('req: ' + req_string) if settings['debug'] else 0
    new_messages = get(req_string)
    updateHbox('got new_messages') if settings['debug'] else 0
    new_json = new_messages.json()
    updateHbox('parsed json of new messages') if settings['debug'] else 0
    message_items = new_json['texts']
    return_val = []
    for n, i in enumerate(message_items):
        try:
            new_m = Message(wrap(i['text'], single_width), i['date'], True if i['is_from_me'] == '1' else False)
            return_val.append(new_m)
        except:
            updateHbox('failed to get message from index %d' % n)
            pass
        updateHbox('unpacking item ' + str(n + 1) + '/' + str(len(message_items))) if settings['debug'] else 0
    return return_val

def loadMessages(id, num = settings['default_num_messages'], offset = 0):
    global total_messages_height
    updateHbox('loading messages. please wait...')

    messages = getMessages(id, num, offset)
    total_messages_height = sum(len(i.content) + 2 for i in messages) + sum((2 if messages[n].timestamp - messages[n - 1].timestamp > 3600 or n == 0 else 0) for n, m in enumerate(messages)) # Need to add 2 to account for gap  + underline
    top_offset = 1
    updateHbox('set top offset') if settings['debug'] else 0

    mbox.clear()
    mbox_wrapper.clear()
    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
    mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.refresh()

    updateHbox('set mbox_wrapper attributes') if settings['debug'] else 0
    mbox.resize(total_messages_height, messages_width - 2)

    for n, m in enumerate(messages):
        updateHbox('entered message enumeration on item ' + str(n + 1)) if settings['debug'] else 0
        text_width = max(len(i) for i in m.content) if len(m.content) > 0 else 0
        updateHbox('passed text_width for item ' + str(n + 1)) if settings['debug'] else 0
        left_padding = 0
        underline = settings['their_chat_end'] + settings['chat_underline']*(text_width - len(settings['their_chat_end']))
        updateHbox('set first section of message ' + str(n + 1)) if settings['debug'] else 0

        if n != 0 and m.timestamp - messages[n - 1].timestamp >= 3600:
            updateHbox('checking timestamps on item ' + str(n + 1)) if settings['debug'] else 0
            time_string = getDate(m.timestamp)
            updateHbox('got string. m=' + str(m.timestamp) + ' & n+1=' + str(messages[n-1].timestamp)) if settings['debug'] else 0
            mbox.addstr(top_offset, int((messages_width - len(time_string)) / 2), time_string)
            top_offset += 2

        if m.from_me == True:
            updateHbox('entered if_from_me for item ' + str(n + 1)) if settings['debug'] else 0
            left_padding = messages_width - 3 - text_width # I feel like it shouldn't be 3 but ok
            underline = settings['chat_underline']*(text_width - len(settings['my_chat_end'])) + settings['my_chat_end']

        for j, l in enumerate(m.content):
            updateHbox('going through lines of content, on line %d' % j) if settings['debug'] else 0
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, l)
            top_offset += 1
        
        updateHbox('settings underline on item %d' % n) if settings['debug'] else 0
        mbox.addstr(top_offset, left_padding, underline, curses.color_pair(2) if m.from_me else curses.color_pair(3)) if text_width > 0 else 0
        top_offset += 2

        updateHbox('added text ' + str(n) + '/' + str(num)) if settings['debug'] else 0

    total_messages_height = top_offset + 1
    refreshMBox()
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
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    right_offset = 0
    
    # This whole section is a nightmare. But it still doesn't work. 
    while True:
        ch = tbox.getch(1, min(1 + len(whole_string) - right_offset, t_width - 2) if len(whole_string) < t_width - 2 else t_width - 2 - right_offset)
        if (chr(ch) in ('j', 'J', '^[B') and len(whole_string) == 0) or ch in (curses.KEY_DOWN,):
            scrollDown()
        elif (chr(ch) in ('k', 'K', '^[A') and len(whole_string) == 0) or ch in (curses.KEY_UP,):
            scrollUp()
        elif (chr(ch) in ('l', 'L', 'h', 'H') and len(whole_string) == 0) or (not settings['buggy_mode'] and ch in (curses.KEY_LEFT, curses.KEY_RIGHT)):
            switchSelected()
        elif ch in (10, curses.KEY_ENTER):
            return whole_string
        elif ch in (127, curses.KEY_BACKSPACE):
            if settings['buggy_mode']:
                if right_offset == 0:
                    whole_string = whole_string[:len(whole_string) - 1]
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
                
                tbox.addstr(1, 1, str(whole_string + ' '*max((t_width - len(whole_string) - 3), 0))[max((len(whole_string) - t_width + 3), 0):])
            else:
                whole_string = whole_string[:len(whole_string) - 1]
                if len(whole_string) > t_width - 2:
                    tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 1:])
                else:
                    tbox.addstr(1, len(whole_string) + 1, ' ')
        elif ch in (curses.KEY_LEFT,) and settings['buggy_mode']:
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,) and settings['buggy_mode']:
            right_offset -= 1 if right_offset > 0 else 0
        elif len(chr(ch)) == 1: 
            if settings['buggy_mode'] and right_offset != 0:
                whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
            else:
                whole_string += chr(ch)
            
            if len(whole_string) < t_width - 2:
                tbox.addstr(1, 1, whole_string)
            else:
                tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 3:])

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
    req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?send=' + new_text + '&to=' + current_chat_id
    get(req_string)
    updateHbox('text sent!')

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
            if settings['buggy_mode']:
                if right_offset == 0:
                    whole_string = whole_string[:len(whole_string) - 1]
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
                
                tbox.addstr(1, 1, str(whole_string + ' '*max((t_width - len(whole_string) - 3), 0))[max((len(whole_string) - t_width + 3), 0):])
            else:
                whole_string = whole_string[:len(whole_string) - 1]
                if len(whole_string) > t_width - 2:
                    tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 1:])
                else:
                    tbox.addstr(1, len(whole_string) + 1, ' ')
        elif ch in (curses.KEY_LEFT,) and settings['buggy_mode']:
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,) and settings['buggy_mode']:
            right_offset -= 1 if right_offset > 0 else 0
        elif len(chr(ch)) == 1: 
            if settings['buggy_mode'] and right_offset != 0:
                whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
            else:
                whole_string += chr(ch)
            
            if len(whole_string) < t_width - 2:
                tbox.addstr(1, 1, whole_string)
            else:
                tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 3:])

def updateHbox(string):
    hbox.clear()
    hbox.addstr(0, 0, string)
    hbox.refresh()

def switchSelected():
    global selected_box
    global mbox_offset
    global cbox_offset
    selected_box = 'c' if selected_box == 'm' else 'm'

    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else 0
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
    mbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'm' else 0
    mbox_wrapper.refresh()
    refreshMBox(mbox_offset)

    cbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'c' else 0
    cbox_wrapper.box()
    cbox_wrapper.addstr(0, settings['title_offset'], settings['chats_title'])
    cbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'c' else 0
    cbox_wrapper.refresh()
    refreshCBox(cbox_offset)

def scrollUp():
    global selected_box
    global mbox_offset
    global cbox_offset
    if selected_box == 'm':
        mbox_offset += settings['messages_scroll_factor'] if mbox_offset < total_messages_height else 0
        refreshMBox(mbox_offset)
    else:
        cbox_offset -= settings['chats_scroll_factor'] if cbox_offset > 0 else 0
        refreshCBox(cbox_offset)

def scrollDown():
    global selected_box
    global mbox_offset
    global cbox_offset
    if selected_box == 'm':
        mbox_offset -= settings['messages_scroll_factor'] if mbox_offset > 0 else mbox_offset 
        refreshMBox(mbox_offset)
    else:
        cbox_offset += settings['chats_scroll_factor'] if cbox_offset < chats_height else 0
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

    text_rows = sum(len(wrap(l, help_width - 2)) for l in help_message)

    hbox_wrapper = curses.newwin(help_height, help_width, help_y, help_x)
    hbox_wrapper.attron(curses.color_pair(1))
    hbox_wrapper.box()
    hbox_wrapper.addstr(0, settings['title_offset'], settings['help_title'])
    hbox_wrapper.attron(curses.color_pair(4))
    hbox_wrapper.refresh()

    help_box = curses.newpad(text_rows + 1, help_width - 2)
    top_offset = 0
    for n, l in enumerate(help_message):
        aval_rows = wrap(l, help_width - 2 - settings['help_inset'])
        for r in aval_rows:
            try:
                help_box.addstr(top_offset, 0, r if n % 2 == 1 or n == 0 else ' '*settings['help_inset'] + r)
            except:
                pass
            top_offset += 1

    help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)

    displaying_help = True

    while True:
        c = screen.getch()
        if chr(c) in ('j', 'J'):
            help_offset += 1 if help_offset < text_rows - help_height + 3 else 0 # Feel like it shouldn't be 3 but oh well
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 1)
        elif chr(c) in ('k', 'K'):
            help_offset -= 1 if help_offset > 0 else 0
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)
        elif chr(c) in ('q', 'Q'):
            break
    
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

    if var not in settings:
        updateHbox('variable (' + var + ') not found.')
        return

    if type(settings[var]) == int and not val.isdigit():
        updateHbox('bad input type for variable.')
        return
    elif type(settings[var]) == bool and val not in ('False', 'True', 'false', 'true'):
        updateHbox('bad input type for variable.')
        return

    if type(settings[var]) == int:
        updateHbox('type is int') if settings['debug'] else 0
        settings[var] = int(val)
    elif type(settings[var]) == float:
        updateHbox('type is float') if settings['debug'] else 0
        settings[var] = float(val)
    elif type(settings[var]) == bool:
        updateHbox('type is bool') if settings['debug'] else 0
        settings[var] = True if val == 'True' or val == 'true' else False
    else:
        updateHbox('type is str') if settings['debug'] else 0
        settings[var] = val
    
    updateHbox('updated ' + var + ' to ' + val)

def showVar(cmd):
    var = cmd[cmd.find(' ') + 1:]

    if var not in settings:
        updateHbox('variable not found.')
    else:
        updateHbox('current value: ' + str(settings[var]))

def pingServer():
    global chats
    global end_all
    req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?check=0' 
    while (not end_all) and (settings['poll_interval'] != -1) :
        sleep(settings['ping_interval'])
        try:
            new_chats = get(req_string).json()
        except:
            print('Lost connection to server')
            end_all = True
            exit()
        if len(new_chats) != 0:
            reloadChats()
            if current_chat_id in new_chats:
                loadMessages(current_chat_id)
            os.system('notify-send "you got new texts!"') if os.uname()[0] != 'Darwin' else 0

def mainTask():
    global end_all
    while not end_all:
        cmd = getTboxText()
        if cmd[:2] in (':s', ':S') or cmd[:4] == 'send':
            sendTextCmd(cmd)
        elif cmd[:2] in (':c', ':C') or cmd[:4] == 'chat':
            selectChat(cmd)
        elif cmd in (':f', ':F', 'flip'):
            switchSelected()
        elif cmd in (':r', ':R', 'reload'):
            reloadChats()
        elif cmd in (':h', ':H', 'help'):
            displayHelp()
        elif cmd[:2] in (':b', ':B') or cmd[:4] == 'bind':
            setVar(cmd)
        elif cmd[:2] in (':d', ':D') or cmd[:7] == 'display':
            showVar(cmd)
        elif cmd in (':q', 'exit', 'quit'):
            break
        else:
            updateHbox('sorry, this command isn\'t supported .')
    
    updateHbox('exiting...')
    end_all = True
        
def main():
    global end_all
    pool = ThreadPool(processes=2)
    pool.apply_async(pingServer)
    pool.apply_async(mainTask)

    while not end_all:
        sleep(settings['poll_exit'])
    
    pool.terminate()

try:          
    chats = getChats(settings['default_num_chats'])
except:
    print('Could not get chats. Check to make sure your host server is running.')
    exit()

screen = curses.initscr()

curses.noecho()
curses.cbreak()
curses.start_color()
curses.use_default_colors()

# pylint: disable=fixme, no-member
rows = curses.LINES
cols = curses.COLS

curses.init_pair(1, 75, -1)
curses.init_pair(2, curses.COLOR_BLUE, -1)
curses.init_pair(3, 248, -1)
curses.init_pair(4, curses.COLOR_WHITE, -1)
curses.init_pair(5, 219, -1)

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
chats_height = len(chats) * (chat_padding + 1)
print('chats_height: %d' % chats_height) if settings['debug'] else 0
sleep(1) if settings['debug'] else 0
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
# corner = u'\u256d'
# cbox_wrapper.border(0, 0, 0, 0, str(corner[0]), 0, 0, 0)
cbox_wrapper.addstr(0, settings['title_offset'], settings['chats_title'])
# cbox_wrapper.addstr(0, 0, u'\u256d')
# cbox_wrapper.addstr(0, chats_width - 1, u'\u256e')
# cbox_wrapper.addstr(t_y - 1, chats_width - 1, u'\u256f'[0])
# cbox_wrapper.addnstr(t_y - 1, chats_width - 1, '╯', 1)
# cbox_wrapper.addstr(t_y - 1, 0, u'\u2570')

cbox_wrapper.attron(curses.color_pair(4))
cbox_wrapper.refresh()
cbox = curses.newpad(chats_height - 2, chats_width - 2)
cbox.scrollok(True)

mbox_wrapper = curses.newwin(messages_height, messages_width, messages_y, messages_x)
mbox_wrapper.box()
mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
mbox_wrapper.refresh()
mbox = curses.newpad(messages_height - 2, messages_width - 2)
mbox.scrollok(True)

tbox = curses.newwin(t_height, t_width, t_y, t_x)
tbox.box()
tbox.addstr(0, settings['title_offset'], settings['input_title'])
tbox.keypad(1)
tbox.refresh()

hbox = curses.newwin(h_height, h_width, h_y, h_x)

screen.refresh()

updateHbox('type \':h\' to get help!')

loadInChats()

screen.refresh()

main()

curses.echo()
curses.nocbreak()

curses.endwin()
