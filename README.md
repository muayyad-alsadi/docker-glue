# Docker Glue

Automated unattended pluggable docker management based on docker events.
Can be used to update load-balancers, DNS, service discovery, ...etc. 
Managing docker containers would be as simple as tagging them with some labels

## Use Cases

- Dynamically add/remove containers to/from load-balancer (currently `haproxy` using `jinja2` templates)
- can send traffic of a specific domain to corresponding containers based on Host HTTP header
- can send traffic of a specific path prefix to corresponding containers 
- Replace `docker0` bridge,docker-proxy, ...etc with more advanced `SDN` (like `OVS` or OpenStack Neutron).
- Run a specific handler code (python plugins) or handler script based on docker events
- publish containers inspection to discovery service (like `etcd`)

## Daemons

- `docker-glue` the modular pluggable daemon that can run handlers and scripts
- `docker-balancer` a standalone daemon that just updates `haproxy` (a special case of glue)

You can pass `-1` to run once, and `-w` to wait for events, and `-h` for details. 

## Requirements and Installation

```
yum install haproxy python-docker-py python-jinja2
cp docker-balancer.service /etc/systemd/system/docker-balancer.service
cp docker-glue.service /etc/systemd/system/docker-glue.service
```

## Using Docker Balancer

you can set labels like (replace 80 with any port):

- `glue_http_80_host` the HTTP host to which this container would be attached in the load-balancer
- `glue_http_80_prefix` the prefix (without leading `/`) to attach it to
- `glue_http_80_strip_prefix` pass `1` if the prefix should be stripped before passing to backend
- `glue_http_80_weight` the weight (defaults to 100)

let's assume that you have started `docker-balancer -w` or the `docker-balancer` service

```
docker run -d --name wp1 -l glue_http_80_host='wp1.example.com' mywordpress/wordpress 
docker run -d --name wp2 -l glue_http_80_host='wp2.example.com' mywordpress/wordpress 
docker run -d --name os-ui1 -l glue_http_80_host=openstack.example.com -l glue_http_80_prefix=dashboard/horizon myopenstack/horizon
docker run -d --name os-id1 -l glue_http_80_host=openstack.example.com -l glue_http_80_prefix=identity/keystone myopenstack/keystone
```

## Using Docker Glue

in `docker-glue.d` you have many `.example` files copy the files you need to remove that extension, for example
```
cd docker-glue.d
cp lb.ini.example lb.ini
cp test.ini.example test.ini
cd ..
```

then start `docker-glue` daemon or run `docker-glue -w`

## Handlers INI files

files in `docker-glue.d/*.ini` (we have included examples) looks like this

```
[handler]
class=DockerGlue.handlers.exec.ScriptHandler
events=all
enabled=1
triggers-none=0

[params]
script=test-handler.sh
demo-option=some value
```

`handler` section specifies what and when to run

- `class` the handler plugin, which can be one of 
  - `DockerGlue.handlers.exec.ScriptHandler` executes a shell script
    - `test-handler.sh` a demo script that logs the event to `/tmp/docker-glue-test.log`
    - `ovs-handler.sh` connect the container to `OpenVSwicth`
  - `DockerGlue.handlers.lb.HAProxyHandler` load balancer that uses HAProxy
  - `DockerGlue.handlers.publishers.distconfig.Publisher` publish containers to discovery service like etcd
- `events` the even statuses (comma separated) that triggers this handler, can be `none` (which is dummy event) or `all` (which does not include `none`)
- `enabled`
- `triggers-none` - set it if you want this handler to triggers `none` dummy event

`params` section is custom params to be passed to the handler


## Writing script plugins

scripts in `handler-scripts` will be passed the ini path and docker event and the docker container id for example it might be like this `test-handler.sh test.ini start 123456`

the code of `test-handler.sh` look like this

```bash
#! /bin/bash

cd `dirname $0`

function error() {
    echo "$@"
    exit -1
}

[ $# -ne 3 ] && error "Usage `basename $0` config.ini status container_id"
ini="$1"
status="$2"
container_id="$3"
ini_demo_option=$( crudini --inplace --get $ini params demo-option 2>/dev/null || : )
echo "`date +%F` container_id=[$container_id] status=[$status] ini_demo_option=[$ini_demo_option]" >> /tmp/docker-glue-test.log
```

as you can see you can read options using `crudini` from the passed ini file.

## Writing python plugins

just extend `BaseHandler` and in the `__init__` do what ever you need, and read your custom params from the ini and implement a handle method like this


```python
from . import BaseHandler

logger = logging.getLogger(__name__)

class DemoHandler(BaseHandler):
    def __init__(self, agent, ini_file, ini):
        BaseHandler.__init__(self, agent, ini_file, ini)
        self.custom_param=ini.get('params', 'custom_param') if ini.has_option('params', 'custom_param') else None
        
    def handle(self, event, container_id):
        logger.info('got event=%r on container=%r and custom_param=%r', event, container_id, self.custom_param)

```

## TODO

- implement TCP/UDP load balancing using ipvsadm or keepalived
