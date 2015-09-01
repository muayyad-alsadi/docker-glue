#! /bin/bash
# this script add docker containers into openstack neutron network that uses OVS
# you need clampify from https://github.com/iqbalmohomed/clampify/blob/master/clampify.go

cd `dirname $0`

function error() {
    echo "$@"
    exit -1
}

[ $# -ne 3 ] && error "Usage `basename $0` config.ini status container_id"
ini="$1"
status="$2"
container_id="$3"
ini_neutron_net=$( crudini --inplace --get $ini params neutron-net 2>/dev/null || : )

neutron_net=`docker inspect -f '{{.Config.Labels.neutron_net}}' $container_id || :`
neutron_net=${neutron_net:-$ini_neutron_net}

[ $status == "create" ] && {
    cotainer_net=`docker inspect -f '{{.HostConfig.NetworkMode}}' "$container_id" || :`
    [ $cotainer_net == "none" ] && {
        clampify insert $neutron_net $container_id || :
    }
}

[ $status == "destroy" ] && {
    # FIXME: this is not right, it accepts $port_id $neutron_net
    clampify delete $container_id
}

# TODO: in what docker event we should do "clampify reinset"
