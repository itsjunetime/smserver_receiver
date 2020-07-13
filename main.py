import curses
from requests import get
from textwrap import wrap
from time import sleep
from multiprocessing.pool import ThreadPool
import os
import sys
from datetime import datetime

# TODO:
# [ ] Extensively test text input
# [ ] Set conversation to read on device when you view it on here
# [ ] When scrolling up, position in mbox doesn't remain the same after refresh.
# [ ] Add more nice-looking colorschemes

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
    'colorscheme': 'default',
    'help_inset': 5,
    'ping_interval': 60,
    'poll_exit': 0.5,
    'default_num_messages': 100,
    'default_num_chats': 30,
    'debug': False,
    'has_authenticated': False
}

help_message = ['COMMANDS:',
':h, :H, help - ',
'displays this help message',
'j, J - ',
'scrolls down in the selected window',
'k, K - ',
'scrolls up in the selected window',
':f, h, l - ',
'switches selected window between messages and conversations',
':q, exit, quit - ',
'exits the window, cleaning up. recommended over ctrl+c.',
':s, :S, send - ',
'starts the process for sending a text with the currently selected conversation. after you hit enter on \':s\', You will then be able to input the content of your text, and hit <enter> once you are ready to send it, or hit <esc> to cancel. You can also enter enter your text with a space between it and the \':s\', e.g.: \':s hello!\'',
':c, :C, chat - ',
'this should be immediately followed by a number, specifically the index of the conversation whose texts you want to view. the indices are displayed to the left of each conversation in the leftmost box. eg \':c 25\'',
':a, :A - ',
'this, along with the number of the attachment, will open the selected attachment in your browser. For example, if you see \'Attachment 5: image/jpeg\', type \':a 5\' and the attachment will be opened to be viewed in your browser',
':b, :B, bind - ',
'these allow you to change variables in settings at runtime. all available variables are displayed within lines 11 - 32 in main.py. To change one, you would simply need to do ":b <var> <val>". E.G. ":b ip 192.168.0.127". there is no need to encapsulate strings in quotes, and booleans can be typed as either true/false or True/False. If you change something that is displayed on the screen, such as window titles, the windows will not be automatically reloaded.',
':d, :D, display - ',
'this allows you view the value of any variable in settings at runtime. just type ":d <var>", and it will display its current value. E.G. ":d ping_interval"',
':r, :R, reload - ',
'this reloads the chats, getting current chats from the currently set ip address and port.',
'if characters are not appearing, or the program is acting weird, just type a bunch of random characters and hit enter. No harm will be done for a bad command. For more information, visit: https://github.com/iandwelker/smserver_receiver']

color_schemes = {
    # [0]: Selected box, [1]: My text underline, [2]: their text underline
    # [3]: Unselected box, [4]: Chat indicator color, [5]: Unread indicator color,
    # [6]: Text color, [7]: Hints box color
    "default": [6, 39, 248, -1, 219, 39, 231, 9],
    "outrun": [211, 165, 238, 6, 228, 205, 189, 198],
}

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
    attachments = []
    attachment_types = []

    def __init__(self, c = [], ts = 0, fm = True, att = '', att_t = ''):
        self.from_me = fm
        self.content = c
        self.timestamp = int(int(ts) / 1000000000 + 978307200) # This will auto-convert it to unix timestamp
        pa = att.split(':')
        self.attachments = pa[:len(pa) - 1]
        pa_t = att_t.split(':')
        self.attachment_types = pa_t[:len(pa_t) - 1]

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
displayed_attachments = []
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

def getDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')

def getChats(num = settings['default_num_chats'], offset = 0):
    # To authenticate
    global num_requested_chats
    if not settings['has_authenticated']:
        authenticate()

    try:
        req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?chat=0&num_chats=' + str(num) + "&chats_offset=" + str(offset)
    except:
        print('Fault was in req_string')

    num_requested_chats = num if offset == 0 else num_requested_chats + num

    try:
        new_chats = get(req_string)
    except:
        print('Failed to actually download the chats after authenticating.')
    new_json = new_chats.json()
    chat_items = new_json['chats']
    if len(chat_items) == 0:
        authenticate()
        try:
            chat_items = get(req_string).json()['chats']
        except:
            print('Failed to actually download the chats after authenticating.')

    if settings['debug']: print('chats_len: %d' % len(chat_items))
    return_val = []
    for i in chat_items:
        # I need to start returning recipients to this request so I can initialize chats with them
        new_chat = Chat(i['chat_identifier'], {}, i['display_name'], False if i['has_unread'] == "false" else True)
        return_val.append(new_chat)
        print("new chat:") if settings['debug'] else 0
        print(new_chat) if settings['debug'] else 0
        
    return return_val

def authenticate():
    auth_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?password=' + settings['pass']
    try:
        response = get(auth_string)
    except:
        print('Fault was in original authentication, string: %s' % auth_string)
    if response.text != 'true':
        print('Your password is wrong. Please change it and try again.')
        exit()
    settings['has_authenticated'] = True

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
            updateHbox('failed to add chat ' + str(n) + ' to box') if settings['debug'] else 0

    updateHbox('chats loaded in')
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
    loadMessages(current_chat_id, settings['default_num_messages'], 0) # was single_width for offset, idk why

def getMessages(id, num = settings['default_num_messages'], offset = 0):
    global single_width
    id = id.replace('+', '%2B')

    req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?person=' + id + '&num=' + str(num) + '&offset=' + str(offset)
    updateHbox('req: ' + req_string) if settings['debug'] else 0
    new_messages = get(req_string)
    updateHbox('got new_messages') if settings['debug'] else 0
    new_json = new_messages.json()
    updateHbox('parsed json of new messages') if settings['debug'] else 0
    message_items = new_json['texts']
    return_val = []
    for n, i in enumerate(message_items):
        try:
            att = i['attachment_file'] if 'attachment_file' in i.keys() else ''
            att_t = i['attachment_type'] if 'attachment_type' in i.keys() else ''
            new_m = Message(wrap(i['text'], single_width), i['date'], True if i['is_from_me'] == '1' else False, att, att_t)
            return_val.append(new_m)
        except:
            updateHbox('failed to get message from index %d' % n)
            pass
        updateHbox('unpacking item ' + str(n + 1) + '/' + str(len(message_items))) if settings['debug'] else 0

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

    total_messages_height = 0 # I think? It used to be 0 but setting it to offset may make it be cool
    for n, m in enumerate(messages):
        total_messages_height += len(m.content)
        total_messages_height += len(m.attachments) if len(m.attachments) > 0 else 0
        total_messages_height += 2
        total_messages_height += 2 if n == 0 or m.timestamp - messages[n - 1].timestamp >= 3600 else 0

    top_offset = 1
    updateHbox('set top offset') if settings['debug'] else 0

    mbox.clear()
    mbox_wrapper.clear()
    mbox_wrapper.attron(curses.color_pair(1)) if selected_box == 'm' else mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.box()
    mbox_wrapper.addstr(0, settings['title_offset'], settings['messages_title'])
    mbox_wrapper.attron(curses.color_pair(4))
    mbox_wrapper.refresh()

    updateHbox('set mbox_wrapper attributes, tmh is ' + str(total_messages_height)) if settings['debug'] else 0
    mbox.resize(total_messages_height, messages_width - 2)

    for n, m in enumerate(messages):
        updateHbox('entered message enumeration on item ' + str(n + 1)) if settings['debug'] else 0
        longest_att = 0
        for i in m.attachment_types:
            if len('Attachment 00: ' + i) > longest_att:
                longest_att = len('Attachment 00: ' + i)

        text_width = max(len(i) for i in m.content) if len(m.content) > 0 else 0
        text_width = max(text_width, longest_att)
        updateHbox('passed text_width for item ' + str(n + 1)) if settings['debug'] else 0
        left_padding = 0
        underline = settings['their_chat_end'] + settings['chat_underline']*(text_width - len(settings['their_chat_end']) + 1)
        updateHbox('set first section of message ' + str(n + 1)) if settings['debug'] else 0

        if n == 0 or m.timestamp - messages[n - 1].timestamp >= 3600:
            updateHbox('checking timestamps on item ' + str(n + 1)) if settings['debug'] else 0
            time_string = getDate(m.timestamp)
            updateHbox('got string on item ' + str(n + 1) + '. m=' + str(m.timestamp) + ' & n+1=' + str(messages[n-1].timestamp)) if settings['debug'] else 0
            mbox.addstr(top_offset, int((messages_width - 2 - len(time_string)) / 2), time_string, curses.color_pair(7))
            updateHbox('added time string on item ' + str(n)) if settings['debug'] else 0
            top_offset += 2

        if m.from_me == True:
            updateHbox('entered if_from_me for item ' + str(n + 1)) if settings['debug'] else 0
            left_padding = messages_width - 3 - text_width # I feel like it shouldn't be 3 but ok
            underline = settings['chat_underline']*(text_width - len(settings['my_chat_end'])) + settings['my_chat_end']

        for i in range(len(m.attachments)):
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, 'Attachment ' + str(len(displayed_attachments)) + ': ' + m.attachment_types[i], curses.color_pair(7))
            displayed_attachments.append(m.attachments[i])
            top_offset += 1
            # So I feel like I should increment top_offset here but I guess not?

        for j, l in enumerate(m.content):
            mbox.addstr(top_offset, left_padding if m.from_me else left_padding + 1, l, curses.color_pair(7))
            top_offset += 1 if l != ' ' else -1

        updateHbox('settings underline on item %d' % n) if settings['debug'] else 0
        mbox.addstr(top_offset, left_padding, underline, curses.color_pair(2) if m.from_me else curses.color_pair(3)) if text_width > 0 else 0
        top_offset += 2

        updateHbox('added text ' + str(n) + '/' + str(num)) if settings['debug'] else 0

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
    tbox.addstr(1, 1, ' '*(t_width - 2))
    tbox.refresh()
    whole_string = ''
    right_offset = 0
    
    # This whole section is a nightmare. But it seems to work...?
    while True:
        ch = tbox.getch(1, min(1 + len(whole_string) - right_offset, t_width - 2) if len(whole_string) < t_width - 2 else t_width - 2 - right_offset)
        if (chr(ch) in ('j', 'J', '^[B') and len(whole_string) == 0) or ch in (curses.KEY_DOWN,):
            scrollDown()
        elif (chr(ch) in ('k', 'K', '^[A') and len(whole_string) == 0) or ch in (curses.KEY_UP,):
            scrollUp()
        elif (chr(ch) in ('l', 'L', 'h', 'H') and len(whole_string) == 0): # or (not settings['buggy_mode'] and ch in (curses.KEY_LEFT, curses.KEY_RIGHT)):
            switchSelected()
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
        elif len(chr(ch)) == 1: 
            if right_offset != 0:
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
    req_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/' + settings['req'] + '?send=' + new_text + '&to=' + current_chat_id.replace("+", "%2B")
    updateHbox('set req_string') if settings['debug'] else 0
    get(req_string)
    updateHbox('text sent!')
    if current_chat_index != 0:
        reloadChats()
    loadMessages(current_chat_id)

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
            if right_offset == 0:
                whole_string = whole_string[:len(whole_string) - 1]
            else:
                whole_string = whole_string[:len(whole_string) - right_offset - 1] + whole_string[len(whole_string) - right_offset:]
                
            tbox.addstr(1, 1, str(whole_string + ' '*max((t_width - len(whole_string) - 3), 0))[max((len(whole_string) - t_width + 3), 0):])

        elif ch in (curses.KEY_LEFT,):
            right_offset += 1 if right_offset != len(whole_string) else 0
        elif ch in (curses.KEY_RIGHT,):
            right_offset -= 1 if right_offset > 0 else 0
        elif len(chr(ch)) == 1:
            if right_offset != 0:
                whole_string = whole_string[:len(whole_string) - right_offset] + chr(ch) + whole_string[len(whole_string) - right_offset:]
            else:
                whole_string += chr(ch)
            
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
    global total_messages_height
    global messages

    if selected_box == 'm':
        updateHbox('scrolling m box, offset is ' + str(mbox_offset) + ', total height is ' + str(total_messages_height)) if settings['debug'] else 0
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
        updateHbox('scrolling m down, offset is ' + str(mbox_offset)) if settings['debug'] else 0
        mbox_offset -= settings['messages_scroll_factor'] if mbox_offset > 0 else 0
        refreshMBox(mbox_offset)
    else:
        if cbox_offset + settings['chats_scroll_factor'] >= chats_height - cbox_wrapper_height - 2:
            updateHbox('Updating chats...')
            loadInChats()
        else:
            updateHbox('just scrolling') if settings['debug'] else 0
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
        help_messages_wrapped.append(wrap(l, help_width - 2) if n % 2 == 0 and not n == 0 else wrap(l, help_width - 2 - settings['help_inset']))

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
            help_box.addstr(top_offset, 0, r if n % 2 == 0 and not n == 0 else ' '*settings['help_inset'] + r)
            top_offset += 1

    help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)

    displaying_help = True

    while True:
        c = screen.getch()
        if chr(c) in ('j', 'J', '^[B') or c == curses.KEY_DOWN:
            help_offset += 1 if help_offset < text_rows - help_height + 2 else 0 # Feel like it shouldn't be 3 but oh well
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 1)
        elif chr(c) in ('k', 'K', '^[A') or c == curses.KEY_UP:
            help_offset -= 1 if help_offset > 0 else 0
            help_box.refresh(help_offset, 0, help_y + 1, help_x + 1, help_y + help_height - 2, help_x + help_width - 2)
        elif chr(c) in ('q', 'Q'):
            break
        updateHbox('scrolling, rows is ' + str(text_rows) + ', height is ' + str(help_height) + ', offset is ' + str(help_offset)) if settings['debug'] else 0
    
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
    
    if type(oldval) == str:
        val = "'" + val + "'"
        oldval = "'" + oldval + "'"
    elif type(oldval) == bool:
        val = 'True' if val in ('true', 'True') else 'False'
    
    if sys.platform == 'linux':
        sed_string = 'sed -i "s/\'' + var + '\': ' + str(oldval) + ',/\'' + var + '\': ' + str(val) + ',/" ' + os.path.basename(__file__)
        os.system(sed_string)

    updateHbox('updated ' + var + ' to ' + val)

def showVar(cmd):
    var = cmd[cmd.find(' ') + 1:]

    if var not in settings:
        updateHbox('variable not found.')
    else:
        updateHbox('current value: ' + str(settings[var]))

def openAttachment(num):
    global displayed_attachments
    if len(displayed_attachments) <= int(num): return
    http_string = 'http://' + settings['ip'] + ':' + settings['port'] + '/attachments?path=' + str(displayed_attachments[int(num)]).replace(' ', '%20')
    os.system('open ' + http_string) if 'darwin' in sys.platform else os.system('xdg-open ' + http_string + ' &!')

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
        elif cmd[:2] in (':a', ':A'):
            openAttachment(cmd[3:])
        elif cmd in (':q', ':Q', 'exit', 'quit'):
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
    print('Could not authenticate. Check to make sure your host server is running.')
    exit()

screen = curses.initscr()

curses.noecho()
curses.cbreak()
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

main()

curses.echo()
curses.nocbreak()

curses.endwin()
