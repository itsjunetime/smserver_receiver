import os
import curses
import shutil
import json
import requests
import textwrap

ip = '192.168.50.10'
port = '8741'
req = 'requests'

print('Loading ...')

class Message:
    """Message, from either person."""
    from_me = True
    content = ''
    timestamp = 0

    def __init__(self, c = '', ts = 0, fm = True):
        self.from_me = fm
        self.content = c
        self.timestamp = ts

class Chat:
    """A conversation"""
    chat_id = ''
    display_name = ''
    recipients = {} # Would normally just be the chatid of the one recipient. 
    # list_num = 0

    def __init__(self, ci = '', rc = {}, dn = ''):
        self.chat_id = ci
        self.display_name = dn
        self.recipients[ci] = dn
        self.recipients.update(rc)
        # self.list_num = ln

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

def getMessages(id, num = 500, offset = 0):
    req_string = 'http://' + ip + ':' + port + '/' + req + '?p=' + id + '&n=' + str(num)
    new_messages = requests.get(req_string)
    new_json = new_messages.json()
    # new_json = json.load(new_messages.content)
    message_items = new_json['texts']
    return_val = []
    for i in message_items:
        new_m = Message(i['text'], i['date'], i['is_from_me'])
        return_val.append(new_m)
    return return_val

def loadMessages(id, width, num = 500, offset = 0):
    updateHbox('loading messages. please wait...')
    messages = getMessages(id, num, offset)
    bottom_offset = 0
    for n, m in reversed(list(enumerate(messages))):
        text_list = textwrap.wrap(m.content, width)
        if m.from_me == 0:
            try:
                mbox.addstr(messages_height - 2 - bottom_offset, 1, '|/' + '-'*(width - 2))
            except curses.error:
                pass
            bottom_offset += 1
            for n, l in reversed(list(enumerate(text_list))):
                try:    
                    mbox.addstr(messages_height - 2 - bottom_offset, 1, l)
                except curses.error:
                    pass
                bottom_offset += 1
            bottom_offset += 1
        else:
            try:
                mbox.addstr(messages_height - 2 - bottom_offset, messages_width - 2 - width, '-'*(width - 2) + '\|')
            except curses.error:
                pass
            bottom_offset += 1
            for n, l in reversed(list(enumerate(text_list))):
                try:
                    mbox.addstr(messages_height - 2 - bottom_offset, messages_width - 2 - width, l)
                except curses.error:
                    pass
                bottom_offset += 1
            bottom_offset += 1
    updateHbox('loaded Messages!')

def getTboxText():
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    string = str(screen.getstr(t_y + 1, t_x + 1))
    return string[2:len(string) - 1]

def sendText(text, to):
    req_string = 'http://' + ip + ':' + port + '/' + req + '?s=' + text + '&t=' + to
    requests.get(req_string)

def updateHbox(string):
    hbox.clear()
    hbox.addstr(0, 0, string)
    hbox.refresh()

chats = getChats()
messages = []
current_chat_id = ''

screen = curses.initscr()

# curses.noecho()
curses.cbreak()

rows = curses.LINES
cols = curses.COLS

# send_box_height = 3
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
chats_height = t_y
chats_x = t_x
chats_y = 0

messages_width = cols - chats_width
messages_height = chats_height
messages_x = chats_width + chats_x
messages_y = chats_y
single_width = int(messages_width * 0.6)

# Padding for chat_id/display_names
chat_padding = 2
chat_offset = 6

screen.clear()
screen.refresh()

cbox = curses.newwin(chats_height, chats_width, chats_y, chats_x)
cbox.box()
cbox.refresh()

mbox = curses.newwin(messages_height, messages_width, messages_y, messages_x)
mbox.box()
mbox.refresh()

tbox = curses.newwin(t_height, t_width, t_y, t_x)
tbox.box()
tbox.refresh()

hbox = curses.newwin(h_height, h_width, h_y, h_x)
updateHbox('type \':h\' to get help!')

for n, c in enumerate(chats, 0):
    d_name = c.display_name if c.display_name != '' else c.chat_id
    if len(d_name) > chats_width - 2 - chat_offset:
        d_name = d_name[:chats_width - 2 - chat_offset - 3] + '...'
    vert_pad = chat_padding * (n + 1)
    if vert_pad >= chats_height - 1:
        break
    try:
        cbox.addstr(vert_pad, 1, str(n))
        cbox.addstr(vert_pad, chat_offset, d_name)
    except curses.error:
        pass

cbox.refresh()

screen.refresh()

while True:
    cmd = getTboxText()
    # tbox.addstr(1, 1, cmd)
    # curses.noecho() # TESTING
    # screen.getch() # TESTING
    # curses.echo() # TESTING
    if cmd == ':s':
        if current_chat_id == '':
            updateHbox('You have not selected a conversation. Please do so before attempting to send texts')
            continue
        updateHbox('Please enter the content of your text! Note that as soon as you hit enter, the text will be sent :)')
        new_text = getTboxText()
        sendText(new_text, current_chat_id)
    elif ':c' == cmd[:2]:
        # updateHbox(cmd[3:]) # TESTING
        # screen.getch() # TESTING
        try:
            num = int(cmd[3:])
        except:
            updateHbox('you input a string where you should\'ve input an index. please try again.')
            continue
        current_chat_id = chats[num].chat_id
        loadMessages(current_chat_id, single_width)
 
    elif cmd == ':q':
        break
    else:
        updateHbox('sorry, that command isn\'t supported :(')

curses.echo()
curses.nocbreak()

curses.endwin()
