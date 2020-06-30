# Receiver app for SMServer

Unnamed as of yet. Maybe I'll just keep it like this, idk. If you have a good name, let me know, 'cause I need one. 

### Requires:
 - python3
 - curses
 - textwrap
 - requests
 
The variables in lines 15 through 40 are the ones that would need to be changed for each inidividual's needs. The only one that you should need to set is 'ip', and the rest should be able to be left as they are preset, and allow everything to work perfectly. Look at the comment above each variable to see what it does, and whether or not you should bother changing it. 

To use this, you have to host a server with either my Mac or iPhone hosting app; those should be publicly available whenever this is. 

## To run

1. First, get a copy of either the [Mac Version](https://github.com/iandwelker/mac_smserver) or [iOS Version](https://github.com/iandwelker/smserver) and start that running. 
2. Set your host device's private ip address in main.py 
3. Navigate to the folder where main.py resides, and run 'python3 ./main.py', 

If you have issues with that, check to make sure that you've installed all of the above listed dependencies (just install them with pip, e.g. 'pip install curses'). If you're still having issues, continue to 'debugging' down below.

### Current features:
 - Sending texts
 - Viewing available conversations
 - View messages from any conversation
 - Easy viewing of image attachments outside of terminal
 - Nearly instantaneous dynamic loading of messages
 - Notifications when a new text is received
 - Extensive customization to run well on any system

### Planned future features:
 - Send attachments
 - Easy colorscheme customization
 - Date and text decoration closer to stock apple
 - Displaying images with jp2a

## Debugging
- To debug, set 'debug' to True on line 38 of main.py. 
- Run the program again, and check what was the last thing to flash on the screen before the program either crashed or froze.
- Cross-reference the printed text with the code (find where in the code that command is printed), and try to fix it from there if you know python/curses. 
- If you don't want to mess with anything, submit an issue report on github with the last message that was printed, and what your settings array looks like. 

### Acknowledged Issues
- When scrolling up and loading more messages, the screen doesn't always remain at the same spot after refresh.
- Messages with an attachment and no text have an extra blank line underneath them

## Settings variables:
- ip: This contains the private IP of your host device, as a string. Should start with '192.168' or '10.10'. 
- port: This should default to 8741, and should be the port over which your host device communicates.
- pass: This contains the password to your server. It may need to be changed if you change the password to your main server.
- req: This should not be changed, unless you've messed with the source code of the smserver app. It's just the subdirectory of the main server where the requests will go.
- chats_scroll_factor: this is how many lines the chats box (on the far left) will scroll when you scroll up or down
- messages_scroll_factor: This is how many lines the messages box (on the right) will scroll when you scroll up or down.
- current_chat_indicator: The character that will sit by the side of the currently selected conversation.
- my_chat_end: The characters that will reside on the end of the underline of text messages from you. The length can be changed, but I wouldn't recommend making it too long, since it may look weird on short texts
- their_chat_end: Same as my_chat_end, but for texts to you.
- chat_underline: the character that will underline each text. Should only be one character, or things will be messed up. 
- chat_vertical_offset: This will the top inside padding for the chats box (the one on the far left)
- title_offset: The left padding of each of the box titles
- x_title: The title for $x box
- help_inset: How much each help command description will be left-padded
- ping_interval: How frequently (in seconds) the program will ping the server to see if there are any new messages
- poll_exit: How frequently (in seconds) the program will check to see if you're trying to exit.
- default_num_messages: How many messages you want to load when you first select each conversation
- default_num_chats: How many conversations you want to load for the left chat box when you first launch the program
- buggy_mode: Even though it's called buggy_mode, I think setting it to True is actually less buggy than setting it to False. It just pertains to how text input is parsed.
- debug: Makes everything really slow and flashes countless debug messages basically any time you do anything. Don't set to True unless you're actually debugging.
- has_authenticated: Sets to true once you authenticate with the server, so you don't authenticate every time you make a request.