import sys, os, os.path
import ConfigParser
import glob
import logging
from collections import defaultdict

try: import simplejson as json
except ImportError: import json

from docker import Client
from .utils import factory, relative_to_exec_dirs

here = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

def usage():
    print("pass -w to wait/watch for changes")
    print("pass -1 to run once")

class Agent(object):
    def __init__(self, docker_url='unix:///var/run/docker.sock', handler_paths=None, script_paths=None, once=False, watch=False):
        self.docker = Client(base_url=docker_url)
        exec_prefix = os.path.dirname(sys.argv[0])
        script_paths = relative_to_exec_dirs([
            '../libexec/docker-glue',
            '../../libexec/docker-glue',
            '/usr/libexec/docker-glue',
            './handler-scripts',
        ])
        self.script_paths = script_paths
        handler_paths = relative_to_exec_dirs(['../etc', '../../etc', '/etc', '.'], suffix='/docker-glue.d')
        self.load_handlers(handler_paths)
        if once: self.once('none', '')
        elif watch: self.loop()

    def resolve_script(self, script):
        if os.path.isabs(script): return script
        for path in self.script_paths:
             fn = os.path.realpath(os.path.join(path, script))
             if os.path.exists(fn) and os.access(fn, os.X_OK): return fn
        return None

    def load_handlers(self, paths):
        handlers=[]
        by_event=defaultdict(list)
        done=set()
        for path in paths:
            if path in done: continue
            logger.info("looking for handlers in [%s]", path)
            done.add(path)
            for ini_file in glob.glob(os.path.join(path, '*.ini')):
                logger.info("parsing [%s]",ini_file)
                ini = ConfigParser.RawConfigParser()
                ini.read(ini_file)
                handler=factory(ini.get('handler', 'class'), self, ini_file, ini)
                handlers.append(handler)
                for event in handler.events:
                      by_event[event].append(handler)
        logger.debug("handlers by event: %r",by_event)
        self.handlers = handlers
        self.handlers_by_event = by_event

    def once(self, event, container_id):
        # event can be: create, destroy, die, exec_create, exec_start, export, kill, oom, pause, restart, start, stop, unpause
        triggers_none=False
        handlers=self.handlers_by_event[event]
        if event!='none': handlers+=self.handlers_by_event['all']
        logger.debug('got handlers %r', handlers)
        for handler in handlers:
            logger.debug("passing event=%r container_id=%r to handler=%r", event, container_id, handler)
            if not handler.enabled: continue
            handler.handle(event, container_id)
            triggers_none|=handler.triggers_none
        if event!='none' and triggers_none: self.once('none', '')

    def loop(self):
        logger.info("waiting for docker events")
        self.once('none', '')
        for event in self.docker.events(decode=True):
            # event looks like this {"status":"die","id":"123","from":"foobar/eggs:latest","time":1434047926}
            self.once(event['status'], event['id'])


def main():
    import argparse
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("-1", "--once", help="run once", action="store_true")
    parser.add_argument("-w", "--watch", help="enter a loop waiting/watching for events", action="store_true")
    parser.add_argument("--handler-paths", help="handler paths", default='')
    parser.add_argument("--script-paths", help="scripts path", default='')
    parser.add_argument("--docker-url", help="docker/swarm address", default='unix:///var/run/docker.sock')
    args=vars(parser.parse_args())
    agent=Agent(**args)

if __name__=='__main__':
    main()
