#!/usr/bin/env python2

import curses
import time

mypad_contents = []

def main(scr):
  # Create curses screen
  scr.keypad(True)
  curses.use_default_colors()
  curses.noecho()
  scr.refresh()

  # Get screen width/height
  height,width = scr.getmaxyx()

  # Create a curses pad (pad size is height + 10)
  mypad_height = 32767
  
  mypad = curses.newpad(mypad_height, width);
  mypad.scrollok(True)
  mypad_pos = 0
  mypad_refresh = lambda: mypad.refresh(mypad_pos+2, 0, 0, 0, height-1, width)
  mypad_refresh()

  # Fill the window with text (note that 5 lines are lost forever)
  try:
    for i in range(0, 33):
        mypad.addstr("{0} This is a sample string...\n".format(i))
        if i > height: mypad_pos = min(i - height, mypad_height - height)
        mypad_refresh()
        #time.sleep(0.05)

    # Wait for user to scroll or quit
    running = True
    while running:
        ch = scr.getch()
        if ch == curses.KEY_DOWN and mypad_pos < mypad.getyx()[0] - height - 1:
            mypad_pos += 1
            mypad_refresh()
        elif ch == curses.KEY_UP and mypad_pos > -2:
            mypad_pos -= 1
            mypad_refresh()
        elif ch < 256 and chr(ch) == 'q':
            running = False
        elif ch == curses.KEY_RESIZE:
            height,width = scr.getmaxyx()
            while mypad_pos > mypad.getyx()[0] - height - 1:
              mypad_pos -= 1
            mypad_refresh()
  except KeyboardInterrupt: pass
  # Store the current contents of pad
  for i in range(0, mypad.getyx()[0]):
      mypad_contents.append(mypad.instr(i, 0))

curses.wrapper(main)
# Write the old contents of pad to console
print '\n'.join(mypad_contents)