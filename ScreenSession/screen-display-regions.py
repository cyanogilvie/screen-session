#!/usr/bin/env python
# file: screen-display-regions.py
# author: Artur Skonecki
# website http://adb.cba.pl
# description: script for GNU Screen reassembling functionality of tmux display-panes + swap regions + rotate regions

import sys,os,subprocess,time,signal,tempfile,pwd,copy
import GNUScreen as sc
from ScreenSaver import ScreenSaver

logfile="__scs-regions-log"
inputfile="__scs-regions-input-%d"%(os.getpid())
subprogram='screen-session-primer -nh'

def local_copysign(x, y):
    "Return x with the sign of y. Backported from Python 2.6."
    if y >= 0:
        return x * (1 - 2 * int(x < 0))
    else:
        return x * (1 - 2 * int(x >= 0))

def rotate_list(l, offset):
    """
    Rotate a list by (offset) elements. Elements which fall off
    one side are provided again on the other side.
    Returns a rotated copy of the list. If (offset) is 0,
    returns a copy of (l).
    
    Examples:
        >>> rotate_list([1, 2, 3, 4, 5, 6], 2)
        [3, 4, 5, 6, 1, 2]
        >>> rotate_list([1, 2, 3, 4, 5, 6], -2)
        [5, 6, 1, 2, 3, 4]
    """
    if len(l) == 0:
        raise ValueError("Must provide a list with 1 or more elements")
    if offset == 0:
        rv = copy.copy(l)
    else:
        real_offset = offset % int(local_copysign(len(l), offset))
        rv = (l[real_offset:] + l[:real_offset])
    return rv


def handler(signum,frame):
    global win_history
    bSelect=False
    mode=-1
    f=open(inputfile,'r')
    ch=f.readline().strip()
    f.close()
    try:
        number=int(ch[1:])
    except:
        number=0

    os.remove(inputfile)
    if ch[0]=='s':
        mode=1
    elif ch[0]=="'" or ch[0]=='g':
        mode=0
        bSelect=True
    elif ch[0]=="l":
        mode=2
        number=-1*number
    elif ch[0]=="r":
        mode=2
    else:
        mode=0

    
    if number!=-1 and mode==1:
        tmp=win_history[0]
        win_history[0]=win_history[number]
        win_history[number]=tmp
    elif mode==2:
        win_history=rotate_list(win_history,number)

    cleanup()

    if number!=-1 and bSelect:
        select_region(number) 

    sys.exit(0)

def cleanup():
    order_windows()
    kill_screen_windows(scs,wins)
    scs.focusminsize(focusminsize)
    try:
        os.remove(inputfile)
    except:
        pass

def kill_screen_windows(scs,wins):
    for w in wins:
        scs.kill(w)

def order_windows():
    #select previous windows
    print('restoring windows '+str(win_history))
    for w in win_history:
        try:
            int(w)
        except:
            break
        scs.select(w)
        scs.focus()

def select_region(number):
    #select region
    if(number!=0 and number<regions_c):
        command='screen -S %s -X eval'%session
        for i in range(0,number):
            command+=' "focus"'
        os.system(command)

def prepare_windows(scs):
    this_win_history=[]
    new_windows=[]
    i=0
    win=scs.number()
    while True:
        this_win_history.append(win)
        scs.screen('-t scs-regions-helper %s %s %d'%(subprogram,inputfile,i))
        i+=1
        new_windows.append(scs.number())
        scs.focus()
        win=scs.number()
        if win==new_windows[0]:
            break
        
    return this_win_history,new_windows,len(this_win_history)


if __name__=='__main__':
    tmpdir=os.path.join(tempfile.gettempdir(),'screen-sessions-'+pwd.getpwuid(os.geteuid())[0] )
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)
    logfile=os.path.join(tmpdir,logfile)
    inputfile=os.path.join(tmpdir,inputfile)
    file=os.path.join(tmpdir,logfile)
    sys.stdout=open(logfile,'w')
    sys.stderr=sys.stdout
    session=sys.argv[1]
    scs=ScreenSaver(session)
    scs.command_at('msgminwait 0')
    focusminsize=scs.focusminsize()
    scs.focusminsize('0 0')

    ident=subprogram+" "+inputfile
    win_history,wins,regions_c=prepare_windows(scs)
    print('helper windows '+str(wins))

    signal.signal(signal.SIGUSR1,handler)
    time.sleep(4)

    cleanup()


