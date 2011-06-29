#!/usr/bin/env python
import os,subprocess,re,sys,platform
from util import tmpdir,removeit,remove

SCREEN=os.getenv('SCREENPATH')
if not SCREEN:
    from util import which
    SCREEN=which('screen')[0]

datadir=None
dumpscreen_window_dirs=[]

def cleanup():
    for tdir in dumpscreen_window_dirs:
        removeit(tdir)

def make_dumpscreen_dirs(session):
    global dumpscreen_window_dirs
    global datadir
    tdir=os.path.join(tmpdir,'___dumpscreen-S%s-%d'%(session,os.getpid()))
    if tdir not in dumpscreen_window_dirs:
        dumpscreen_window_dirs.append(tdir)
    datadir=tdir
    #if os.path.exists(tdir):
    #    removeit(tdir)
    if not os.path.exists(tdir):
        os.mkdir(tdir)
    return tdir

def dumpscreen_window(session,full=False):
    from ScreenSaver import ScreenSaver
    #print('dumpscreen_window()')
    tdir = make_dumpscreen_dirs(session)
    ss=ScreenSaver(session)
    if full:
        ss.command_at(False,"at \# dumpscreen window \"%s\" -F"%(tdir))
        f=open(os.path.join(tdir,'full'),'w')
        f.close()
    tfile=os.path.join(tdir,'winlist')
    ss.query_at("at \# dumpscreen window \"%s\""%(tfile))
    return tdir

def dumpscreen_layout_info(ss):
    tdir = make_dumpscreen_dirs(ss.pid)
    tfile=os.path.join(tdir,'layout-info')
    ss.query_at("dumpscreen layout-info \"%s\""%(tfile))
    return tfile

def gen_layout_info(ss, tfile):
    for line in open(tfile,'r'):
        yield line.strip().split(' ',1)

def require_dumpscreen_window(session,full=False):
    global datadir
    tdir=os.path.join(tmpdir,'___dumpscreen-S%s-%d'%(session,os.getpid()))
    try:
        if not os.path.exists(os.path.join(tdir,'winlist')):
            raise Exception
        if full and not os.path.exists(os.path.join(tdir,'full')):
            raise Exception
    except:
        dumpscreen_window(session,full)
    return datadir

class Regions:
    title=None
    number_of_regions=None
    focus_offset=None
    term_size_x=None
    term_size_y=None
    focusminsize_x=None
    focusminsize_y=None
    regions=[]

def get_regions(session):
## old list
#[NUMBER_OF_REGIONS,
# FOCUS_OFFSET,
# ('TERM_SIZE_X', 'TERM_SIZE_Y'),
# ('FOCUSMINSIZE_X', 'FOCUS_MINSIZE_Y'),
# ('WINDOW_ID', 'REGION_SIZE_X', 'REGION_SIZE_Y'),
# ('0', '105', '29'),
# ('1', '105', '29')]

    from ScreenSaver import ScreenSaver
    ss=ScreenSaver(session)
    tfile=os.path.join(tmpdir,'___regions-%d'%os.getpid())
    ss.query_at('dumpscreen layout \"%s\"'%tfile)
    tfiled = None
    while tfiled == None:
        try:
            tfiled = open(tfile,'r')
        except:
            pass
    regions=Regions()
    regions.regions=[]
    regions.title = tfiled.readline().strip()
    regions.term_size_x,regions.term_size_y = tuple(tfiled.readline().strip().split(' '))
    regions.focusminsize_x,regions.focusminsize_y = tuple(tfiled.readline().strip().split(' '))
    i=0
    for i,line in enumerate(tfiled):
        if line[0]=='f':
            line=line.split(' ',1)[1].strip().split(' ')
            regions.focus_offset=i
        else:
            line=line.strip().split(' ')
        regions.regions.append(tuple(line))
    tfiled.close()
    if len(regions[:-1])==1: # remove it later after patching screen
        regions.regions=regions.regions[:-1] 
    regions.number_of_regions=len(regions.regions)
    remove(tfile)
    return regions

def gen_all_windows_fast(session, datadir):
    from ScreenSaver import ScreenSaver
    ss=ScreenSaver(session)
    tfile=os.path.join(datadir,'winlist')
    for line in open(tfile,'r'):
        try:
            cwin,cgroupid,ctty,ctitle = line.strip().split(' ',3)
        except:
            cwin,cgroupid,ctty= line.strip().split(' ')
            ctitle=None
        if ctty[0]=='z':
            ctypeid=-1
        elif ctty[0]=='g':
            ctypeid=1
        elif ctty[0]=='t':
            ctypeid=2
        else:
            ctypeid=0
        yield cwin,cgroupid,ctypeid,ctty,ctitle

def gen_all_windows_full(session,datadir,reverse=False,sort=False):
    from ScreenSaver import ScreenSaver
    import string
    ss=ScreenSaver(session)
    tfile=os.path.join(datadir,'winlist')
    if sort:
        linesource = list(open(tfile,'r').readlines())
        if reverse:
            linesource.sort(lambda b,a: cmp(int(a.split(' ',1)[0]),int(b.split(' ',1)[0])))
        else:
            linesource.sort(lambda a,b: cmp(int(a.split(' ',1)[0]),int(b.split(' ',1)[0])))
    elif reverse:
        linesource = reversed(open(tfile,'r').readlines())
    else:
        linesource = open(tfile,'r')

    for line in linesource:
        try:
            cwin,cgroupid,ctty,ctitle = line.strip().split(' ',3)
        except:
            cwin,cgroupid,ctty= line.strip().split(' ')
            ctitle=None
        cwin,ctime,cgroup,ctype,ctitle,cfilter,cscroll,cmdargs=map(string.strip,open(os.path.join(datadir,'win_'+cwin),'r').readlines())
        if ctty[0]=='z':    # zombie
            ctypeid=-1
        elif ctype[0]=='g': # group
            ctypeid=1
        elif ctype[0]=='t': # telnet
            ctypeid=2
        else:               # basic
            ctypeid=0
        try:
            cgroupid,cgroup = cgroup.split(' ')
        except:
            cgroup=ss.none_group
        yield cwin,cgroupid,cgroup,ctty,ctypeid,ctype,ctitle,cfilter,cscroll,ctime,cmdargs

def _get_pid_info_sun(pid):
    procdir="/proc"
    piddir=os.path.join(procdir,str(pid))
    cwd=os.readlink(os.path.join(piddir,"path","cwd"))
    exe=os.readlink(os.path.join(piddir,"path","a.out"))
    p=os.popen('pargs %s'%pid)
    p.readline()
    args=[]
    for line in p:
        args.append(line.split(': ')[1].rstrip('\n'))
    cmdline="\0".join(["%s"%v for v in args])
    cmdline+="\0"
    return (cwd,exe,cmdline)

def _get_pid_info_bsd(pid):
    procdir="/proc"
    piddir=os.path.join(procdir,str(pid))
    p=os.popen('procstat -f %s'%pid)
    p.readline()
    cwd='/'+p.readline().strip().split('/',1)[1]
    #cwd=os.popen('pwdx '+pid).readline().split(':',1)[1].strip()
    exe=os.readlink(os.path.join(piddir,"file"))
    f=open(os.path.join(piddir,"cmdline"),"r")
    cmdline=f.read()
    if not cmdline.endswith('\0'):
        cmdline+='\0'
    f.close()
    return (cwd,exe,cmdline)

def _get_pid_info_linux(pid):
    procdir="/proc"
    piddir=os.path.join(procdir,str(pid))
    cwd=os.readlink(os.path.join(piddir,"cwd"))
    exe=os.readlink(os.path.join(piddir,"exe"))
    f=open(os.path.join(piddir,"cmdline"),"r")
    cmdline=f.read()
    if not cmdline.endswith('\0'):
        cmdline+='\0'
    f.close()
    
    return (cwd,exe,cmdline)

def get_pid_info(pid):
    global get_pid_info
    p=platform.system()
    if p =='Linux':
        get_pid_info=_get_pid_info_linux
    elif p == 'FreeBSD' :
        get_pid_info=_get_pid_info_bsd
    else:
        get_pid_info=_get_pid_info_sun
    return get_pid_info(pid)


def sort_by_ppid(cpids):
    #print (cpids)
    cppids={}
    ncpids=[]
    for i,pid in enumerate(cpids):
        try:
            ppid=subprocess.Popen('ps -p %s -o ppid' % (pid) , shell=True, stdout=subprocess.PIPE).communicate()[0].strip().split('\n')[1].strip()
            cppids[pid]=ppid
            ncpids.append(pid)
        except:
            pass
    cpids=ncpids

    pid_tail=-1
    pid_tail_c=-1
    cpids_sort=[]
    for i,pid in enumerate(cpids):
        if cppids[pid] not in cppids.keys():
            cpids_sort.append(pid)
            pid_tail=pid
            break;
    
    for j in range(len(cpids)):
        for i,pid in enumerate(cpids):
            if pid_tail==cppids[pid]:
                pid_tail=pid
                cpids_sort.append(pid)
                break;
    cpids=cpids_sort
    return cpids

def get_tty_pids(ctty):
    global get_tty_pids
    get_tty_pids=_get_tty_pids_ps_with_cache

    return get_tty_pids(ctty)

def _get_tty_pids_ps_fast(ctty):
    f = os.popen('ps --sort=start_time -o pid -t %s' % ctty)
    pids=f.read().strip()
    f.close()
    npids=[]
    for pid in pids.split('\n')[1:]:
        npids.append(pid.strip())
    return npids

def _get_tty_pids_ps_with_cache(ctty):
    global _get_tty_pids_ps_with_cache
    global get_tty_pids
    global tty_and_pids
    import getpass
    tty_and_pids=_get_tty_pids_ps_with_cache_gen(getpass.getuser())
    get_tty_pids=_get_tty_pids_ps_with_cache_find
    return get_tty_pids(ctty)
def _get_tty_pids_ps_with_cache_gen(user):
    import shlex
    p=os.popen('ps -U %s -o tty,pid,ppid'%user)
    p.readline()
    data={}
    for line in p:
        line=shlex.split(line)
        try:
            line=(int(line[0].strip().split('/')[1]),int(line[1].strip()),int(line[2].strip()))
            try:
                data[line[0]]+=[(line[1],line[2])]
            except:
                data[line[0]]=[(line[1],line[2])]
        except:
            pass
    ndata={}
    for key,val in data.items():
        nval=[]
        parents=[]
        pids=[]
        for pid,parent in val:
            pids.append(pid)
        lastpid=-1
        val_not_set=[]
        for pid,parent in val:
            if parent not in pids:
                nval.append(pid)
                lastpid=pid
            else:
                val_not_set.append((pid,parent))
        lastpid=lastpid
        val_not_set_prev_len=0
        val_not_set_swap=[]
        while len(val_not_set)!=val_not_set_prev_len:
            for pid,parent in val_not_set:
                if parent == lastpid:
                    nval.append(pid)
                    lastpid=pid
                else:
                    val_not_set_swap.append((pid,parent))
            val_not_set_prev_len=len(val_not_set)
            val_not_set = val_not_set_swap
            val_not_set_swap=[]
        ndata[key]=nval
    return ndata
def _get_tty_pids_ps_with_cache_find(ctty):
    global tty_and_pids
    return tty_and_pids[int(ctty.rsplit('/',1)[1])]

def _get_tty_pids_pgrep(_ctty):
    cttys = _ctty.split('/dev/')
    if len(cttys) > 0:
        ctty = cttys[1]
        f = os.popen('pgrep -t %s' % ctty)
        pids=f.read().strip().split('\n')
        f.close()
        pids=sort_by_ppid(pids)
        return pids
    else:
        return []


def get_session_list():
    w=subprocess.Popen('%s -ls' % SCREEN, shell=True, stdout=subprocess.PIPE).communicate()[0]
    if w.startswith('No Sockets'):
        return []
    
    w=w.split('\n')
    w.pop(0)

    wr=[]
    for l in w:
        ent=l.split('\t')
        try:
            if ent[2].startswith('(A'):
                ent[2]=1
            else:
                ent[2]=0
            wr.append((ent[1],ent[2]))
        except:
            break

    return wr

def find_new_session(sessionsp,sessionsn,key=''):
    try:
        session=list(set(sessionsn)-set(sessionsp))[0][0]
        return session
    except:
        return ''




def __convert_to_list(s):
    s=s.strip('[').strip(']')
    l=s.split(',')
    ln=[]
    for e in l:
        ln.append(int(e))
    return ln

def parse_windows(windows):
    winendings=re.escape('$*-&@! ')
    winendingsactive=re.escape('*')

    winregex='\s\s\d+[%s]'%(winendings)
    firstwinregex='^\d+[%s]'%(winendings)
    firstwinactiveregex='^\d+[%s][%s]'%(winendingsactive,winendings)
    winactiveregex='\s\s\d+[%s][%s]'%(winendingsactive,winendings)
    
    winids=re.compile(winregex).findall(windows)
    winfirst=re.compile(firstwinregex).findall(windows)
    winactive=re.compile(winactiveregex).findall(windows)
    winactivefirst=re.compile(firstwinactiveregex).findall(windows)
    
    if len(winfirst)>0:
        winnumbers=[int(re.compile('\d+').findall(winfirst[0])[0])]
    else:
        winnumbers=[]
    for id in winids:
        winnumbers.append(int(re.compile('\d+').findall(id)[0]))
    
    winactivenumbers=-1
    if len(winactivefirst)>0:
        winactivenumbers=int(re.compile('\d+').findall(winactivefirst[0])[0])
    elif len(winactive)>0:
        winactivenumbers=int(re.compile('\d+').findall(winactive[0])[0])

    return winnumbers,winactivenumbers


def get_windows(session=None):
    if session:
        screen=SCREEN+' -S %s '%session
    else:
        screen=SCREEN+" "

    return subprocess.Popen('%s -Q @windows' % screen, shell=True, stdout=subprocess.PIPE).communicate()[0]


def find_new_windows(winids_old,winids_new):
    if winids_old==winids_new:
        return None
    else:
        return list(set(winids_new)-set(winids_old))


def move(windownumber,nextwindownumber,noswitch=False,session=None):
    windownumber=int(windownumber)
    nextwindownumber=int(nextwindownumber)
    if session:
        screen=SCREEN+" -S %s "%session
    else:
        screen=SCREEN+" "
    
    delta=nextwindownumber-windownumber
    
    if(delta<0):
        sign='-'
    else:
        sign='+'

    delta=abs(delta)

    if noswitch:
        command="%s -X at %d number %s%d"%(screen,windownumber,sign,delta)
        os.system(command)
    else:
        command="%s -X select %d"%(screen,windownumber)
        os.system(command)
        command="%s -X number %s%d"%(screen,sign,delta)
        os.system(command)
    

def get_current_window(session=None):
    if session:
        screen=SCREEN+" -S %s "%session
    else:
        screen=SCREEN+" "
    return int(subprocess.Popen('%s -Q @number' % screen, shell=True, stdout=subprocess.PIPE).communicate()[0].split(" ",1)[0])

def order_windows(win_history):
    #order windows in layout by win_history
    for w in win_history:
        try:
            int(w)
        except:
            break
        #print('window: %s'%w)
        os.system(SCREEN+' -S %s -X select %s'%(session,w))
        os.system(SCREEN+' -S %s -X focus' %(session))

def select_window(number,session=None):
    if session:
        screen=SCREEN+" -S %s "%session
    else:
        screen=SCREEN+" "
    #select region
    if(number!=0 and number<regions_c):
        command='%s %s -X eval'%(screen,session)
        for i in range(0,number):
            command+=' "focus"'
        os.system(command)

