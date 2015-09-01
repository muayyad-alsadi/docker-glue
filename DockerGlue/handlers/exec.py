import os, os.path
import logging

try: from shlex import quote as shell_quote
except ImportError:
    def shell_quote(s): return "'" + s.replace("'", "'\\''") + "'"

from . import BaseHandler

logger = logging.getLogger(__name__)

class ScriptHandler(BaseHandler):
    def __init__(self, agent, ini_file, ini):
        BaseHandler.__init__(self, agent, ini_file, ini)
        self.script = ini.get('params', 'script')
        self.resolved_script = self._agent.resolve_script(self.script)
        logger.debug('script %r resolved to %r', self.script, self.resolved_script)
        if not self.resolved_script:
            logger.warning('script %r not found, the handles %r is disabled', self.script, self._base_name)
            self.enabled = False
        
    def handle(self, event, container_id):
        cmd="%s %s %s %s" % (
            self.resolved_script,
            shell_quote(self._ini_file),
            shell_quote(event),
            shell_quote(container_id),
        )
        logger.debug('running %r', cmd)
        status=os.system(cmd)
        logger.debug('script of %r returned %r', self._base_name, status)
        # TODO: trigger "none" after some scripts, maybe based on status
        # self._agent.once('none', '')
