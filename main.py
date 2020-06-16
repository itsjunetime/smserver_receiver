import curses
from requests import get
from textwrap import wrap
from time import sleep
from multiprocessing.pool import ThreadPool
from os import system

# The private IP of your host device
ip = '192.168.50.10'
# The port on which your server is running 
port = '8741'
# Don't change this unless you actually know what you're doing and what this is used for.
req = 'requests'
# How many lines you'll scroll down/up in chats/messages boxes, respectively
chats_scroll_factor = 2
messages_scroll_factor = 5
# Character to indicate what conversation you currently have selected. Should only be one or two characters.
current_chat_indicator = '>'
# Strings to define underline of messages
my_chat_end = '╲▏'
their_chat_end = '▕╱'
chat_underline = '▔'
# Top padding for conversation list in leftmost (conversation) box
chat_vertical_offset = 1
# Left padding for each box's title
title_offset = 5
# Title for each of the boxes
chats_title = '| chats |'
messages_title = '| messages |'
input_title = '| input here :) |'
help_title = '| help |'
# Left padding for help strings
help_inset = 5
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
'If characters are not appearing, or the program is acting weird, just type a bunch of random characters and hit enter.']
# How frequently (in seconds) you want the script to ping the server to see if there are any messages
ping_interval = 60
# How frequently, in seconds, you want the script to check if the sscript has initiated shut down
poll_exit = 0.5
# How many messages you want to load when you first select a chat
default_num_chats = 500
# Buggy mode! Allows more versatile active text editing but sometimes makes things look weird and doesn't work perfectly; I'd recommend not using it but it's up to you. 
buggy_mode = False

print('Loading ...')

if ip == '' or port == '':
    if ip == '':
        print('Please put in your device\'s private ip to communicate with')
    if port == '':
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
        self.timestamp = ts

class Chat:
    """A conversation"""
    chat_id = ''
    display_name = ''
    recipients = {} # Would normally just be the chatid of the one recipient. 

    def __init__(self, ci = '', rc = {}, dn = ''):
        self.chat_id = ci
        self.display_name = dn
        self.recipients[ci] = dn
        self.recipients.update(rc)

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

def getChats(num = 30):
    req_string = 'http://' + ip + ':' + port + '/' + req + '?c'
    new_chats = get(req_string)
    new_json = new_chats.json()
    chat_items = new_json['chats']
    return_val = []
    for i in chat_items:
        # I need to start returning recipients to this request so I can initialize chats with them
        new_chat = Chat(i['chat_identifier'], {}, i['display_name'])
        return_val.append(new_chat)
    return return_val

def loadInChats():
    cbox.clear()
    for n, c in enumerate(chats, 0):
        d_name = c.display_name if c.display_name != '' else c.chat_id
        if len(d_name) > chats_width - 2 - chat_offset:
            d_name = d_name[:chats_width - 2 - chat_offset - 3] + '...'
        vert_pad = (chat_padding * n) + chat_vertical_offset
        if vert_pad >= chats_height - 1:
            break
        try:
            cbox.addstr(vert_pad, 1, str(n))
            cbox.addstr(vert_pad, chat_offset, d_name)
        except curses.error:
            pass

    refreshCBox()

def reloadChats():
    global chats
    updateHbox('reloading chats. hold on...')
    try:
        chats = getChats()
    except:
        print('failed to connect to server. please check your host.')
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

    cbox.addstr((current_chat_index * 2) + chat_vertical_offset, chat_offset - 2, ' ')
    cbox.addstr((num * 2) + chat_vertical_offset, chat_offset - 2, current_chat_indicator, curses.color_pair(5))
    refreshCBox(cbox_offset)
    current_chat_id = chats[num].chat_id
    current_chat_index = num
    loadMessages(current_chat_id, single_width)

def getMessages(id, num = default_num_chats, offset = 0):
    global single_width
    req_string = 'http://' + ip + ':' + port + '/' + req + '?p=' + id + '&n=' + str(num)
    new_messages = get(req_string)
    new_json = new_messages.json()
    message_items = new_json['texts']
    return_val = []
    for i in message_items:
        new_m = Message(wrap(i['text'], single_width), i['date'], True if i['is_from_me'] == '1' else False)
        return_val.append(new_m)
    return return_val

def loadMessages(id, num = default_num_chats, offset = 0):
    global total_messages_height
    updateHbox('loading messages. please wait...')
    messages = getMessages(id, num, offset)
    total_messages_height = sum(len(i.content) + 2 for i in messages) # Need to add 2 to account for gap  + underline
    top_offset = 1
    mbox.clear()
    mbox_wrapper.clear()
    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, title_offset, messages_title)
    mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.refresh()
    mbox.resize(total_messages_height, messages_width - 2)

    # for n, m in enumerate(messages):
    for m in messages:
        text_width = max(len(i) for i in m.content)
        left_padding = 0
        underline = their_chat_end + chat_underline*(text_width - len(their_chat_end))

        if m.from_me == True:
            left_padding = messages_width - 3 - text_width # I feel like it shouldn't be 3 but ok
            underline = chat_underline*(text_width - len(my_chat_end)) + my_chat_end

        for l in m.content:
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, l)
            top_offset += 1
        
        mbox.addstr(top_offset, left_padding, underline, curses.color_pair(2) if m.from_me else curses.color_pair(3))
        top_offset += 2

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
    
    # This whole section is a nightmare. But it works
    while True:
        ch = tbox.getch(1, 1 + min(len(whole_string) - right_offset, t_width - 2))
        if (chr(ch) in ('j', 'J', '^[B') and len(whole_string) == 0) or ch in (curses.KEY_DOWN,):
            scrollDown()
        elif (chr(ch) in ('k', 'K', '^[A') and len(whole_string) == 0) or ch in (curses.KEY_UP,):
            scrollUp()
        elif (chr(ch) in ('l', 'L', 'h', 'H') and len(whole_string) == 0) or (not buggy_mode and ch in (curses.KEY_LEFT, curses.KEY_RIGHT)):
            switchSelected()
        elif ch in (10, curses.KEY_ENTER):
            break
        elif ch in (127, curses.KEY_BACKSPACE):
            if buggy_mode:
                if right_offset == 0:
                    whole_string = whole_string[:len(whole_string) - 1]
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
                tbox.addstr(1, 1, whole_string + ' '*max((t_width - len(whole_string) - 2), 0))
            else:
                whole_string = whole_string[:len(whole_string) - 1]
                tbox.addstr(1, len(whole_string) + 1, ' ')
        elif ch in (curses.KEY_LEFT,) and buggy_mode:
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,) and buggy_mode:
            right_offset -= 1 if right_offset > 0 else 0
        elif len(chr(ch)) == 1: 
            if buggy_mode:
                if right_offset == 0:
                    whole_string += chr(ch)
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
                if len(whole_string) < t_width - 2:
                    tbox.addstr(1, 1, whole_string)
                else:
                    tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 2:])
            else:
                tbox.addstr(1, len(whole_string) + 1, chr(ch))
                whole_string += chr(ch)

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
    req_string = 'http://' + ip + ':' + port + '/' + req + '?s=' + new_text + '&t=' + current_chat_id
    get(req_string)
    updateHbox('text sent!')

def getTextText():
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    right_offset = 0
    while True:
        ch = tbox.getch(1, 1 + len(whole_string) - right_offset)
        if ch in (10, curses.KEY_ENTER):
            return whole_string
        elif ch in (127, curses.KEY_BACKSPACE):
            if buggy_mode:
                if right_offset == 0:
                    whole_string = whole_string[:len(whole_string) - 1]
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
                tbox.addstr(1, 1, whole_string + ' '*max((t_width - len(whole_string) - 2), 0))
            else:
                whole_string = whole_string[:len(whole_string) - 1]
                tbox.addstr(1, len(whole_string) + 1, ' ')
        elif ch in (curses.KEY_LEFT,) and buggy_mode:
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,) and buggy_mode:
            right_offset -= 1 if right_offset > 0 else 0
        elif ch in (27, curses.KEY_CANCEL):
            return ''
        elif len(chr(ch)) == 1: 
            if buggy_mode:
                if right_offset == 0:
                    whole_string += chr(ch)
                else:
                    whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
                if len(whole_string) < t_width - 2:
                    tbox.addstr(1, 1, whole_string)
                else:
                    tbox.addstr(1, 1, whole_string[len(whole_string) - t_width + 2:])
            else:
                tbox.addstr(1, len(whole_string) + 1, chr(ch))
                whole_string += chr(ch)

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
    mbox_wrapper.addstr(0, title_offset, messages_title)
    mbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'm' else 0
    mbox_wrapper.refresh()
    refreshMBox(mbox_offset)

    cbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'c' else 0
    cbox_wrapper.box()
    cbox_wrapper.addstr(0, title_offset, chats_title)
    cbox_wrapper.attron(curses.color_pair(4)) if selected_box == 'c' else 0
    cbox_wrapper.refresh()
    refreshCBox(cbox_offset)

def scrollUp():
    global selected_box
    global mbox_offset
    global cbox_offset
    if selected_box == 'm':
        mbox_offset += messages_scroll_factor if mbox_offset < total_messages_height else 0
        refreshMBox(mbox_offset)
    else:
        cbox_offset -= chats_scroll_factor if cbox_offset > 0 else 0
        refreshCBox(cbox_offset)

def scrollDown():
    global selected_box
    global mbox_offset
    global cbox_offset
    if selected_box == 'm':
        mbox_offset -= messages_scroll_factor if mbox_offset > 0 else mbox_offset 
        refreshMBox(mbox_offset)
    else:
        cbox_offset += chats_scroll_factor if cbox_offset < chats_height else 0
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
    hbox_wrapper.addstr(0, title_offset, help_title)
    hbox_wrapper.attron(curses.color_pair(4))
    hbox_wrapper.refresh()

    help_box = curses.newpad(text_rows + 0, help_width - 2)
    top_offset = 0
    for n, l in enumerate(help_message):
        aval_rows = wrap(l, help_width - 2 - help_inset)
        for r in aval_rows:
            try:
                help_box.addstr(top_offset, 0, r if n % 2 == 1 or n == 0 else ' '*help_inset + r)
            except:
                pass
            top_offset += 1

    help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)

    displaying_help = True

    while True:
        c = screen.getch()
        if chr(c) in ('j', 'J'):
            help_offset += 1 if help_offset < text_rows - help_height + 2 else 0
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

def pingServer():
    global chats
    global end_all
    req_string = 'http://' + ip + ':' + port + '/' + req + '?x' 
    while not end_all:
        sleep(ping_interval)
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
            system('notify-send "you got new texts!"')

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
        elif cmd in (':q', 'exit', 'quit'):
            break
        else:
            updateHbox('sorry, this command isn\'t supported (%s)' % cmd)
    
    updateHbox('exiting...')
    end_all = True
        
def main():
    global end_all
    pool = ThreadPool(processes=2)
    pool.apply_async(pingServer)
    pool.apply_async(mainTask)

    while not end_all:
        sleep(poll_exit)
    
    pool.terminate()

try:          
    chats = getChats()
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
cbox_wrapper.addstr(0, title_offset, chats_title)
cbox_wrapper.attron(curses.color_pair(4))
cbox_wrapper.refresh()
cbox = curses.newpad(chats_height - 2, chats_width - 2)
cbox.scrollok(True)

mbox_wrapper = curses.newwin(messages_height, messages_width, messages_y, messages_x)
mbox_wrapper.box()
mbox_wrapper.addstr(0, title_offset, messages_title)
mbox_wrapper.refresh()
mbox = curses.newpad(messages_height - 2, messages_width - 2)
mbox.scrollok(True)

tbox = curses.newwin(t_height, t_width, t_y, t_x)
tbox.box()
tbox.addstr(0, title_offset, input_title)
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
