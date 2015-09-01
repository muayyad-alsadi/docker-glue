import os, os.path

class BaseHandler(object):
    def __init__(self, agent, ini_file, ini):
        self._agent=agent
        self._base_name=os.path.basename(ini_file)
        self._ini_file=ini_file
        self._ini=ini
        self.klass=ini.get('handler', 'class')
        self.events=map(lambda s: s.strip(), ini.get('handler', 'events').split(','))
        self.enabled=ini.getboolean('handler', 'enabled') if ini.has_option('handler', 'enabled') else True
        self.triggers_none=ini.getboolean('handler', 'triggers-none') if ini.has_option('handler', 'triggers_none') else False
    
    def handle(self, event, container_id):
        raise NotImplementedError
