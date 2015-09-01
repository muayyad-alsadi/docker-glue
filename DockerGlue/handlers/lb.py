import os, os.path
import logging

from DockerGlue.lb.haproxy import HAProxyConfig
from . import BaseHandler


logger = logging.getLogger(__name__)

class HAProxyHandler(BaseHandler):
    def __init__(self, agent, ini_file, ini):
        BaseHandler.__init__(self, agent, ini_file, ini)
        kw={}
        # TODO: implement the remaining options
        if ini.has_option('params', 'template_dir'): kw['template_dir'] = ini.get('params', 'template_dir')
        logger.debug('loading HAProxyConfig with settings=%r ...', kw)
        self.lb_config=HAProxyConfig(**kw)

        
    def handle(self, event, container_id):
        self.lb_config.once()
