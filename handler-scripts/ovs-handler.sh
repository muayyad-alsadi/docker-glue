#! /bin/bash
# for details see https://github.com/openvswitch/ovs/blob/master/INSTALL.Docker.md
cd `dirname $0`

function error() {
    echo "$@"
    exit -1
}

[ $# -ne 3 ] && error "Usage `basename $0` config.ini status container_id"
ini="$1"
status="$2"
container_id="$3"
ovs_options=$( crudini --inplace --get $ini params ovs-options 2>/dev/null || : )
ovs_bridge=$( crudini --inplace --get $ini params ovs-bridge 2>/dev/null || : )
ovs_interface=$( crudini --inplace --get $ini params ovs-interface 2>/dev/null || : )
ovs_interface=${ovs_interface:-eth0}

# TODO: read some options from labels like this
# ovs_something=`docker inspect -f '{{.Config.Labels.ovs_something}}' $container_id`

# you need this utility https://github.com/openvswitch/ovs/blob/master/utilities/ovs-docker
[ $status == "create" ] && {
    cotainer_net=`docker inspect -f '{{.HostConfig.NetworkMode}}' "$container_id" || :`
    [ $cotainer_net == "none" ] && {
        ovs-docker add-port "$ovs_bridge" "$ovs_interface" "$container_id" $ovs_options || :
    }
}
[ $status == "destroy" ] && {
    ovs-docker del-ports "$ovs_bridge" "$container_id"
}

