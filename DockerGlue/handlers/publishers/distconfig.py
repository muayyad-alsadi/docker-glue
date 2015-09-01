from .. import BaseHandler
from ...utils import factory

class Publisher(BaseHandler):
    def __init__(self, agent, ini_file, ini):
        BaseHandler.__init__(self, agent, ini_file, ini)
        
    def handle(self, event, container_id):
        raise NotImplementedError

#        info=docker.info()
#        hash=info[u'Name']+info[u'ID']
#        container_ids=[]
#        details_by_id={}
#        for cn in self.docker.containers():
#            c_id=cn['Id']
#            c_details=docker.inspect_container(c_id)
#            container_ids.append(c_id)
#            details_by_id[c_id]=c_details
#        container_ids.sort()
#        publish(docker, container_ids, details_by_id)
