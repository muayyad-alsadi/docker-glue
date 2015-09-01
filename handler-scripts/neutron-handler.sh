#! /bin/bash
# this script add docker containers into neutron network that uses OVS
# you need ovs-vsctl to be installed

# consider using pipework which understand openvswitch < https://github.com/jpetazzo/pipework/blob/master/pipework

cd `dirname $0`

function error() {
    echo "$@"
    exit -1
}

function create_netns_link () {
    mkdir -p /var/run/netns
    if [ ! -e /var/run/netns/"$PID" ]; then
        ln -s /proc/"$PID"/ns/net /var/run/netns/"$PID"
        trap 'delete_netns_link' 0
        for signal in 1 2 3 13 14 15; do
            trap 'delete_netns_link; trap - $signal; kill -$signal $$' $signal
        done
    fi
}

function delete_netns_link () {
    rm -f /var/run/netns/"$PID"
}

function get_port_for_container_interface () {
    CONTAINER="$1"
    INTERFACE="$2"

    PORT=`ovs_vsctl --data=bare --no-heading --columns=name find interface \
             external_ids:container_id="$CONTAINER"  \
             external_ids:container_iface="$INTERFACE"`
    if [ -z "$PORT" ]; then
        echo >&2 "$UTIL: Failed to find any attached port" \
                 "for CONTAINER=$CONTAINER and INTERFACE=$INTERFACE"
    fi
    echo "$PORT"
}


function add_port() {
    # we might need to export OS_TENANT_NAME, OS_USERNAME, OS_PASSWORD, OS_AUTH_URL, OS_TOKEN
    output=`neutron port-create --name="${neutron_port_prefix}${container_name}" $neutron_net`
    port_id=`echo "$output" | grep '^|\s*id\s*|' | cut -d '|' -f 3- | sed -re 's/\s*\|\s*$//;'`
    mac_address=`echo "$output" | grep mac_address | cut -d '|' -f 3- | sed -re 's/\s*\|\s*$//;'`
    json_fixed_ips=`echo "$output" | grep fixed_ips | cut -d '|' -f 3- | sed -re 's/\s*\|\s*$//;'`
    # json looks like this {"subnet_id": "15a09f6c-87a5-4d14-b2cf-03d97cd4b456", "ip_address": "192.168.2.2"}
    which jq &&
      ip_address=`echo "$json_fixed_ips" | jq .ip_address | tr -d '"' || :` || 
      ip_address=`echo "$json_fixed_ips" | sed -re 's/^.*"ip_address"\s*:\s*"([^"]*)".*$/\1/'`
    port_id_short=`expr substr "$port_id" 1 11`
    # we might use port-show later
    # createVIFOnHost(port_id, mac_address)
    # createNSForDockerContainer(container_id)
    # addTapDeviceToNetNS(portName, netns)
    # applyIPAddressToTapDeviceInNetNS(ip_address+config.NetSize, config.BroadcastIPAddress, portName, netns)
    # associate_port_with_host

    backend_specific_code1 && 
    containers_specific_code &&
    backend_specific_code2

# what does clamify do
  # createVIFOnHost() which does attachTapDeviceToOVSBridge() and setTapDeviceMacAddress()
  # attachTapDeviceToOVSBridge():
  # What! it removes what neutron had created
  ovs-vsctl -- \
    --if-exists del-port $port_id_short -- \
    add-port $bridge $port_id_short -- \
    set Interface $port_id_short type=internal -- \
    set Interface $port_id_short external-ids:iface-id=$port_id -- \
    set Interface $port_id_short external-ids:iface-status=active -- \
    set Interface $port_id_short external-ids:attached-mac=$mac_address
  # end of attachTapDeviceToOVSBridge()
  # setTapDeviceMacAddress()
  ip  link  set  $port_id_short  address  $mac_address
  # end of setTapDeviceMacAddress()
  # createNSForDockerContainer()
  # mkdir -p /var/run/netns # and ln -s just like docker-ovs
  # addTapDeviceToNetNS()
  netns=$container_id
  ip  link  set  $port_id_short  netns  $netns
  ip  netns  exec $port_id_short  ip  link  set  $port_id_short  up
  # applyIPAddressToTapDeviceInNetNS()
  # ip  netns  exec  %s  ip  -4  addr  add  %s  brd  %s  scope  global  dev  %s", netns, ipAddressInCIDR, broadcastAddress, portName)
  # associate_port_with_host()
  # curl -g -i -X PUT http://%s:9696/v2.0/ports/%s.json -H "User-Agent: python-neutronclient" -H "Accept: application/json" -H "X-Auth-Token: %s" -d '{"port":{"binding:host_id": "%s"}}'`, neutron_server_ipaddress, port_id, auth_token, compute_node_name)
  # curl -g -i -X PUT http://%s:9696/v2.0/ports/%s.json -H "User-Agent: python-neutronclient" -H "Accept: application/json" -H "X-Auth-Token: %s" -d '{"port":{"device_id": "%s"}}'`, neutron_server_ipaddress, port_id, auth_token, compute_node_name)



# what docker-ovs do
    
    
    # Check if a port is already attached for the given container and interface
    get_port_for_container_interface $container_id eth0
    PORT=`get_port_for_container_interface "$CONTAINER" "$INTERFACE" \
            2>/dev/null`
    if [ -n "$PORT" ]; then
        echo >&2 "$UTIL: Port already attached" \
                 "for CONTAINER=$CONTAINER and INTERFACE=$INTERFACE"
        exit 1
    fi

    if ovs_vsctl br-exists "$BRIDGE" || \
        ovs_vsctl add-br "$BRIDGE"; then :; else
        echo >&2 "$UTIL: Failed to create bridge $BRIDGE"
        exit 1
    fi

    if PID=`docker inspect -f '{{.State.Pid}}' "$CONTAINER"`; then :; else
        echo >&2 "$UTIL: Failed to get the PID of the container"
        exit 1
    fi

    create_netns_link
    # Create a veth pair.
    ID=`uuidgen | sed 's/-//g'`
    PORTNAME="${ID:0:13}"
    ip link add "${PORTNAME}_l" type veth peer name "${PORTNAME}_c"

    # Add one end of veth to OVS bridge.
    if ovs_vsctl --may-exist add-port "$BRIDGE" "${PORTNAME}_l" \
       -- set interface "${PORTNAME}_l" \
       external_ids:container_id="$CONTAINER" \
       external_ids:container_iface="$INTERFACE"; then :; else
        echo >&2 "$UTIL: Failed to add "${PORTNAME}_l" port to bridge $BRIDGE"
        ip link delete "${PORTNAME}_l"
        exit 1
    fi

    ip link set "${PORTNAME}_l" up

    # Move "${PORTNAME}_c" inside the container and changes its name.
    ip link set "${PORTNAME}_c" netns "$PID"
    ip netns exec "$PID" ip link set dev "${PORTNAME}_c" name "$INTERFACE"
    ip netns exec "$PID" ip link set "$INTERFACE" up

    if [ -n "$MTU" ]; then
        ip netns exec "$PID" ip link set dev "$INTERFACE" mtu "$MTU"
    fi

    if [ -n "$ADDRESS" ]; then
        ip netns exec "$PID" ip addr add "$ADDRESS" dev "$INTERFACE"
    fi

    if [ -n "$MACADDRESS" ]; then
        ip netns exec "$PID" ip link set dev "$INTERFACE" address "$MACADDRESS"
    fi

    if [ -n "$GATEWAY" ]; then
        ip netns exec "$PID" ip route add default via "$GATEWAY"
    fi
}

[ $# -ne 3 ] && error "Usage `basename $0` config.ini status container_id"
ini="$1"
status="$2"
container_id="$3"
container_name=`docker inspect -f '{{.Name}}' $container_id | tr -d "/"`

neutron_port_prefix=$( crudini --inplace --get $ini params neutron-port-prefix 2>/dev/null || : )
ini_neutron_net=$( crudini --inplace --get $ini params neutron-net 2>/dev/null || : )

neutron_port_prefix=${neutron_port_prefix:-docker_}

neutron_net=`docker inspect -f '{{.Config.Labels.neutron_net}}' $container_id || :`
neutron_net=${neutron_net:-$ini_neutron_net}

# TODO: read some options from docker inspect labels
# you need this utility https://github.com/openvswitch/ovs/blob/master/utilities/ovs-docker
# and this one https://github.com/iqbalmohomed/clampify/blob/master/clampify.go

# clampify insert $net $container_id
# clampify delete $container_id

[ $status == "create" ] && {
ovs-docker add-port $ovs_bridge $ovs_port $container_id $ovs_options || :
}
[ $status == "destroy" ] && {
ovs-docker del-ports $ovs_bridge $container_id
}

# as in ovs-docker's create_netns_link and add-port


# ovs-vsctl -- --if-exists del-port %[1]s -- add-port %[4]s %[1]s -- set Interface %[1]s  type=internal -- set Interface %[1]s  external-ids:iface-id=%[2]s -- set  Interface %[1]s external-ids:iface-status=active -- set Interface %[1]s external-ids:attached-mac='%[3]s

clampify.go insert demo-net 7bfbd1af154d246fd3e5405eb7893e3a06682944148b15af4d11192b97d2d393

