import curses
import requests
import textwrap

ip = '192.168.50.10'
port = '8741'
req = 'requests'
chats_scroll_factor = 2
messages_scroll_factor = 5
current_chat_indicator = '>'
my_chat_end = '╲▏'
their_chat_end = '▕╱'
chat_underline = '▔'
chat_vertical_offset = 1
title_offset = 5
chats_title = '| chats |'
messages_title = '| messages |'
input_title = '| input here :) |'
help_title = '| help |'
help_message = ['COMMANDS:',
':h - displays this help message',
':s - starts the process for sending a text with the currently selected conversation.',
'    after you hit enter on \':s\', You will then be able to input the content of your text, and hit <enter> once you are ready to send it.',
':c - this should be immediately followed by a number, specifically the index of the conversation whose texts you want to view.',
'     the indices are displayed to the left of each conversation in the leftmost box. eg \':c 25\'',
'j -  scrolls down in the selected window',
'k -  scrolls up in the selected window',
':f, h, l - switches selected window',
':q, exit, quit - exits the window, cleaning up. recommended over ctrl+c.']

print('Loading ...')

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

def getChats(num = 30):
    req_string = 'http://' + ip + ':' + port + '/' + req + '?c'
    new_chats = requests.get(req_string)
    new_json = new_chats.json()
    chat_items = new_json['chats']
    return_val = []
    for i in chat_items:
        # I need to start returning recipients to this request so I can initialize chats with them
        new_chat = Chat(i['chat_identifier'], {}, i['display_name'])
        return_val.append(new_chat)
    return return_val

def loadInChats():
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
    chats = getChats()
    loadInChats()
    screen.refresh()
    updateHbox('reloaded chats!')

def selectChat(cmd):
    global current_chat_index
    global current_chat_id
    try:
        num = int(cmd[3:])
    except:
        updateHbox('you input a string where you should\'ve input an index. please try again.')
        return
    cbox.addstr((current_chat_index * 2) + chat_vertical_offset, chat_offset - 2, ' ')
    cbox.addstr((num * 2) + chat_vertical_offset, chat_offset - 2, current_chat_indicator, curses.color_pair(5))
    refreshCBox(cbox_offset)
    current_chat_id = chats[num].chat_id
    current_chat_index = num
    loadMessages(current_chat_id, single_width)

def getMessages(id, num = 500, offset = 0):
    global single_width
    req_string = 'http://' + ip + ':' + port + '/' + req + '?p=' + id + '&n=' + str(num)
    new_messages = requests.get(req_string)
    new_json = new_messages.json()
    message_items = new_json['texts']
    return_val = []
    for i in message_items:
        new_m = Message(textwrap.wrap(i['text'], single_width), i['date'], True if i['is_from_me'] == '1' else False)
        return_val.append(new_m)
    return return_val

def loadMessages(id, num = 500, offset = 0):
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
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    while True:
        ch = tbox.getch(1, 1 + len(whole_string))
        # KEY_UP and KEY_DOWN still don't work
        if chr(ch) in ('j', 'J', '^[B') or ch in (279166, curses.KEY_DOWN):
            scrollDown()
        elif chr(ch) in ('k', 'K', '^[A') or ch in (279165, curses.KEY_UP):
            scrollUp()
        elif chr(ch) in ('l', 'L', 'h', 'H') and len(whole_string) == 0:
            switchSelected()
        elif ch in (10, curses.KEY_ENTER):
            break
        elif ch in (127, curses.KEY_BACKSPACE):
            whole_string = whole_string[:len(whole_string) - 1]
            tbox.addstr(1, 1 + len(whole_string), ' ')
        else: 
            tbox.addstr(1, 1 + len(whole_string), chr(ch))
            whole_string += chr(ch)

    return whole_string

def sendTextCmd():
    global current_chat_id
    if current_chat_id == '':
        updateHbox('you have not selected a conversation. please do so before attempting to send texts')
        return
    updateHbox('please enter the content of your text! note that as soon as you hit enter, the text will be sent :)')
    new_text = getTboxText()
    req_string = 'http://' + ip + ':' + port + '/' + req + '?s=' + new_text + '&t=' + current_chat_id
    requests.get(req_string)
    updateHbox('text sent!')

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
        mbox_offset += messages_scroll_factor if mbox_offset < messages_height - 4 else 0
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
    updateHbox('displaying help')

    curses.noecho()

    help_height = int(rows * 0.6)
    help_width = int(cols * 0.6)
    help_x = int((cols - help_width) / 2)
    help_y = int((rows - help_height) / 2)
    help_offset = 0

    text_rows = sum(len(textwrap.wrap(l, help_width - 2)) for l in help_message)

    hbox_wrapper = curses.newwin(help_height, help_width, help_y, help_x)
    hbox_wrapper.attron(curses.color_pair(1))
    hbox_wrapper.box()
    hbox_wrapper.addstr(0, title_offset, help_title)
    hbox_wrapper.attron(curses.color_pair(4))
    hbox_wrapper.refresh()

    help_box = curses.newpad(text_rows + 0, help_width - 2)
    top_offset = 0
    for l in help_message:
        aval_rows = textwrap.wrap(l, help_width - 2)
        for r in aval_rows:
            try:
                help_box.addstr(top_offset, 0, r)
            except:
                pass
            top_offset += 1

    help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)

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

    switchSelected()
    switchSelected()
            
chats = getChats()

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
tbox.refresh()

hbox = curses.newwin(h_height, h_width, h_y, h_x)

screen.refresh()

updateHbox('type \':h\' to get help!')

loadInChats()

screen.refresh()

while True:
    cmd = getTboxText()
    if cmd == ':s' or cmd == 'send':
        sendTextCmd()
    elif ':c' == cmd[:2]:
        selectChat(cmd)
    elif cmd == ':f' or cmd == 'flip':
        switchSelected()
    elif cmd == ':r' or cmd == 'reload':
        reloadChats()
    elif cmd == ':q' or cmd == 'exit' or cmd == 'quit':
        break
    elif cmd in (':h', ':H'):
        displayHelp()
    else:
        updateHbox('sorry, that command isn\'t supported :(')

curses.echo()
curses.nocbreak()

curses.endwin()
