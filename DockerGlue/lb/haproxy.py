import sys, os, os.path, re, logging

from collections import defaultdict
from jinja2 import Environment, FileSystemLoader

try: from docker import Client
except ImportError: Client=None

from ..utils import relative_to_exec_dirs

here = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

class HAProxyConfig(object):
    _default_template_dir=['/etc/docker-glue/templates/', './templates/']
    _glue_http_re=re.compile(r'glue_http_(\d+)_host')
    def __init__(
                 self,
                 template_dir=None, template_file='haproxy.cfg.j2',
                 config_file='/etc/haproxy/haproxy.cfg',
                 include_env=False, rc=None,
                 once=False, watch=False,
                 docker_url='unix:///var/run/docker.sock',
                 watch_set='die,start',
                 ):
        if not template_dir: template_dir=self._default_template_dir
        elif template_dir.startswith(':'): template_dir=self._default_template_dir+template_dir[1:].split(':')
        elif template_dir.endswith(':'): template_dir=template_dir[:-1].split(':')+self._default_template_dir
        template_dir = relative_to_exec_dirs(template_dir)
        logger.debug("haproxy template dirs %r", template_dir)
        rc=rc or '/etc/sysconfig/haproxy'
        self._rc=rc if os.path.exists(rc) else None
        self._include_env = include_env
        self._counter = os.getpid()
        self._template_env = Environment(loader=FileSystemLoader(template_dir))
        self._template_env.filters['re_escape'] = re.escape

        self._template_file = template_file
        self._config_dir = os.path.dirname(config_file)
        self._config_file = os.path.basename(config_file)
        self._docker_url = docker_url
        self._watch_set=set(watch_set.split(','))
        if once: self.once()
        elif watch: self.loop()
        
    def get_config(self, docker_inspects):
        # http_mapping={port: {host:{prefix:[(ip1,w2,0),(ip2,w2,0),(ip3,w3,0)]}}
        # to be used like this http_mapping['80']['foo.example.com']['/prefix/'].append(('10.0.0.1','0'))
        http_mapping=defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        tcp_mapping=defaultdict(list)
        for cn in docker_inspects:
            c_id=cn['Id']
            is_running=cn[u'State'][u'Running']
            if not is_running: continue
            c_labels = cn[u'Config'].get(u'Labels', {}) or {}
            # NOTE: code if we want to use env.
            if self._include_env:
                c_env={}
                c_env_unparsed = cn[u'Config'].get(u'Env', None) or []
                for env_entry in c_env_unparsed:
                    key,value=env_entry.split('=', 1)
                    c_env[key]=value
                c_labels=c_env.update(c_labels)
            
            # the countiner can have labels like:
            # {glue_http_ports: '80', glue_http_80_host: 'spam.example.com', glue_http_80_prefix: 'dashboard/', glue_http_80_strip_prefix: '0'}
            ip=cn.get(u'NetworkSettings', {}).get(u'IPAddress', '')
            if not ip: continue
            tcp_ports=c_labels.get('glue_tcp_ports', '').split(',')
            if c_labels.has_key('glue_http_ports'):
                http_ports= c_labels.get('glue_http_ports', '').split(',')
            else:
                http_ports= map(lambda m: m.group(1), filter(lambda v: v, 
                     map(lambda k: self._glue_http_re.match(k), c_labels.keys())))
            for http_port in http_ports:
                is_port_exposed=cn[u'NetworkSettings'][u'Ports'].has_key(http_port+u'/tcp')
                if not is_port_exposed: continue
                #http_bind=c_labels.get('glue_http_'+http_port+'_bind', '*')
                #if http_bind in ['0.0.0.0', '0:0:0:0:0:0:0:0', '::']: http_bind='*'
                http_host=c_labels.get('glue_http_'+http_port+'_host', '') 
                http_prefix=c_labels.get('glue_http_'+http_port+'_prefix', '')
                http_weight=c_labels.get('glue_http_'+http_port+'_weight', '100')
                # used to default to strip prefixes, but since the web app should be aware of it, it's not default to '0'
                #http_strip_prefix=c_labels.get('glue_http_'+http_port+'_strip_prefix', '1' if http_prefix else '0')
                http_strip_prefix=c_labels.get('glue_http_'+http_port+'_strip_prefix', '0')
                http_mapping[http_port][http_host][http_prefix].append((ip, http_weight, http_strip_prefix))
            for tcp_port in tcp_ports:
                is_port_exposed=cn[u'NetworkSettings'][u'Ports'].has_key(tcp_port+u'/tcp')
                if not is_port_exposed: continue
                if tcp_port in http_ports: continue
                tcp_weight=c_labels.get('glue_tcp_'+http_port+'_weight', '100')
                tcp_mapping[http_port].append((ip, tcp_weight,))
        # no we got all containers data
        # sorted_config_by_port['80']=[('host1', [prefix1,prefix2,...],),[]]
        sorted_config_by_port={}
        
        for port in http_mapping.keys():
            sorted_config_by_port[port]=[]
            sorted_hosts=sorted(http_mapping[port].keys(), key=lambda s: -len(s))
            for host in sorted_hosts:
                sorted_prefixes=sorted(http_mapping[port][host].keys(), key=lambda s: -len(s))
                sorted_config_by_port[port].append((host,sorted_prefixes,))
        logger.debug("http_mapping=%r", http_mapping)
        logger.debug("sorted_config_by_port=%r", sorted_config_by_port)
        return sorted_config_by_port, http_mapping, tcp_mapping

    def render_config(self, cfg, sorted_config_by_port, http_mapping, tcp_mapping):
        logger.info("generating new config [%r]", cfg)
        with open(cfg, 'w+') as f:
            template = self._template_env.get_template('haproxy.cfg.j2')
            f.truncate()
            f.write(template.render(
               sorted_config_by_port=sorted_config_by_port,
               http_mapping=http_mapping,
               tcp_mapping=tcp_mapping
            ))

    def reconfig(self, docker_inspects):
        sorted_config_by_port, http_mapping, tcp_mapping = self.get_config(docker_inspects)
        target = os.path.join(self._config_dir, self._config_file)
        cfg = os.path.join(self._config_dir, '_glue_'+str(self._counter)+'_'+self._config_file)
        self.render_config(cfg, sorted_config_by_port, http_mapping, tcp_mapping)
        logger.info("testing new config [%r]", cfg)
        if self._rc: cmd="source {0} && haproxy -c -f {1} $OPTIONS ".format(self._rc, cfg)
        else: cmd="haproxy -c -f {0}".format(cfg)
        ret=os.system(cmd)
        if ret: return # TODO: log error
        logger.info("reloading haproxy ...")
        os.rename(cfg, target)
        os.system("systemctl reload haproxy")
        # to replace "/static/" with "/" at the beginning of any request path. use: reqrep ^([^\ :]*)\ /static/(.*)     \1\ /\2

        # c_details[u'Volumes'] # /var/lib/docker/vfs/dir/
        # haproxy -c -f /etc/haproxy/_new_haproxy.cfg $OPTIONS
    
    
    def once(self):
        if not Client: raise ImportError('could not import docker client')
        docker = Client(base_url=self._docker_url)
        docker_inspects=[docker.inspect_container(cn['Id']) for cn in docker.containers()]
        self.reconfig(docker_inspects)
        
    def loop(self):
        if not Client: raise ImportError('could not import docker client')
        docker = Client(base_url=self._docker_url)
        logger.info("waiting for events ...")
        for event in docker.events(decode=True):
            # it looks like this {"status":"die","id":"123","from":"foobar/eggs:latest","time":1434047926}
            if event['status'] in self._watch_set:
                docker_inspects=[docker.inspect_container(cn['Id']) for cn in docker.containers()]
                self.reconfig(docker_inspects)

def main():
    import argparse
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("-1", "--once", help="run once", action="store_true")
    parser.add_argument("-w", "--watch", help="loop waiting for events", action="store_true")
    parser.add_argument("--watch-set", help="set of events to watch", default='die,start')
    parser.add_argument("--template-dir", help="template dir", default='')
    parser.add_argument("--template-file", help="template file", default='haproxy.cfg.j2')
    parser.add_argument("--config-file", help="full path to config file", default='/etc/haproxy/haproxy.cfg')
    parser.add_argument("--rc", help="full path to rc file", default='/etc/sysconfig/haproxy')
    parser.add_argument("--include-env", help="should we consider env as labels", action="store_true")
    parser.add_argument("--docker-url", help="docker/swarm address", default='unix:///var/run/docker.sock')
    args=vars(parser.parse_args())
    haproxy=HAProxyConfig(**args)

if __name__ == '__main__':
    # os.path.join(here, 'templates')
    main()
