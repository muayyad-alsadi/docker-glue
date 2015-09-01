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
