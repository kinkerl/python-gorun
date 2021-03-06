#!/usr/bin/env python
#
# Wrapper on pyinotify for running commands
# (c) 2009 Peter Bengtsson, peter@fry-it.com
# 
# TODO: the lock file mechanism doesn't work! threading?
#

import os

__version__='1.5'
    
# Prepare a lock file
from tempfile import gettempdir
LOCK_FILE = os.path.join(gettempdir(), 'gorunning.lock')

class SettingsClass(object):
    VERBOSE = False
    
settings = SettingsClass()

try:
    from pyinotify import WatchManager, Notifier, ThreadedNotifier, ProcessEvent, EventsCodes
except ImportError:
    print "pyinotify not installed. Try: easy_install pyinotify"
    raise


def _find_command(path):
    # path is a file
    assert os.path.isfile(path)
    # in dictionary lookup have keys as files and directories.
    # if this path exists in there, it's a simple match
    try:
        return lookup[path]
    except KeyError:
        pass
    # is the parent directory in there?
    while path != '/':
        path = os.path.dirname(path)
        try:
            return lookup[path]
        except KeyError:
            pass
        
def _ignore_file(path):
    if path.endswith('.pyc'):
        return True
    if path.endswith('~'):
        return True
    if os.path.basename(path).startswith('.#'):
        return True
    if os.path.splitext(path)[1][1:] in settings.IGNORE_EXTENSIONS:
        return True
    if os.path.split(os.path.dirname(path))[-1] in settings.IGNORE_DIRECTORIES:
        return True

class PTmp(ProcessEvent):
    def process_IN_CREATE(self, event):
        if os.path.basename(event.pathname).startswith('.#'):
            # backup file
            return
        print "Creating:", event.pathname
        command = _find_command(event.pathname)

    #def process_IN_DELETE(self, event):
    #    print "Removing:", event.pathname
    #    command = _find_command(event.pathname)

    def process_IN_MODIFY(self, event):
        if _ignore_file(event.pathname):
            return
            
        if os.path.isfile(LOCK_FILE):
            # command is still running
            return
        
        print "Modifying:", event.pathname
        command = _find_command(event.pathname)
        if command:
            if settings.VERBOSE:
                print "Command: ",
                print command
            open(LOCK_FILE, 'w').write("Running command\n\n%s\n" % command)
            os.system(command)
            if os.path.isfile(LOCK_FILE):
                os.remove(LOCK_FILE)
            print "Waiting for stuff to happen again..."
            
def start(actual_directories):
    
    wm = WatchManager()
    flags = EventsCodes.ALL_FLAGS
    mask = flags['IN_MODIFY'] #| flags['IN_CREATE']
        
    p = PTmp()
    notifier = Notifier(wm, p)
    
    for actual_directory in actual_directories:
        print "ACTUAL_DIRECTORY", actual_directory
        wdd = wm.add_watch(actual_directory, mask, rec=True)
    
    # notifier = Notifier(wm, p, timeout=10)
    try:
        print "Waiting for stuff to happen..."
        notifier.loop()
    except KeyboardInterrupt:
        pass
    
    return 0

lookup = {}

def configure_more(directories):
    actual_directories = set()
    
    #print "directories", directories

    # Tune the configured directories a bit
    for i, (path, cmd) in enumerate(directories):
        if isinstance(path, (list, tuple)):
            actual_directories.update(configure_more(
                            [(x, cmd) for x in path]))
            continue
        if not path.startswith('/'):
            path = os.path.join(os.path.abspath(os.path.dirname('.')), path)
        if not (os.path.isfile(path) or os.path.isdir(path)):
            raise OSError, "%s neither a file or a directory" % path
        path = os.path.normpath(path)
        if os.path.isdir(path):
            if path.endswith('/'):
                # tidy things up
                path = path[:-1]
            if path == '.':
                path = ''
            actual_directories.add(path)
        else:
            # because we can't tell pyinotify to monitor files,
            # when a file is configured, add it's directory
            actual_directories.add(os.path.dirname(path)) 
        
        lookup[path] = cmd
        
    return actual_directories


if __name__=='__main__':
    import sys
    args = sys.argv[1:]
    if not args and os.path.isfile('gorun_settings.py'):
        print >>sys.stderr, "Guessing you want to use gorun_settings.py"
        args = ['gorun_settings.py']
    if not args and os.path.isfile('gorunsettings.py'):
        print >>sys.stderr, "Guessing you want to use gorunsettings.py"
        args = ['gorunsettings.py']
    if not args:
        print >>sys.stderr, "USAGE: %s importable_py_settings_file" %\
          __file__
        sys.exit(1)

    
    settings_file = args[-1]
    if settings_file.endswith('.py'):
        settings_file = settings_file[:-3]
        
    sys.path.append(os.path.abspath(os.curdir))
    x = __import__(settings_file)
    settings.DIRECTORIES = x.DIRECTORIES
    settings.VERBOSE = getattr(x, 'VERBOSE', settings.VERBOSE)
    settings.IGNORE_EXTENSIONS = getattr(x, 'IGNORE_EXTENSIONS', tuple())
    settings.IGNORE_DIRECTORIES = getattr(x, 'IGNORE_DIRECTORIES', tuple())
    actual_directories = configure_more(settings.DIRECTORIES)
    
    sys.exit(start(actual_directories))
