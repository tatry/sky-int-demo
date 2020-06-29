#!/bin/bash

# ovs installation from https://opendev.org/x/networking-ovs-dpdk
# https://opendev.org/x/networking-ovs-dpdk/src/branch/master/devstack/plugin.sh
# https://opendev.org/x/networking-ovs-dpdk/src/branch/master/devstack/libs/ovs-dpdk

function install_sky_int_demo
{
	#if $(dpkg -s openvswitch-switch 2>&1 | grep installed | grep -v -i "not installed"  &> /dev/null ); then
	#	stop_service openvswitch-switch
	#	uninstall_package openvswitch-switch openvswitch-datapath-dkms openvswitch-common
	#fi
	install_package autoconf libtool libfuse-dev screen

	#cd ${OVS_DIR}
	#./boot.sh
	#./configure --with-dbdir=$OVS_DB_CONF_DIR --disable-bpf-verifier CFLAGS='-O3 -march=native -fPIC'
	#make -j $(nproc) CFLAGS='-O3 -march=native -fPIC' $ADDFLAGS
	#sudo make install

	#sudo /usr/local/share/openvswitch/scripts/ovs-ctl start

	#sudo ovs-vsctl --no-wait set Bridge br-tun datapath_type=${OVS_DATAPATH_TYPE}
	#sudo ovs-vsctl --no-wait set Bridge br-int datapath_type=${OVS_DATAPATH_TYPE}
	#sudo ovs-vsctl --no-wait set Bridge br-ex datapath_type=${OVS_DATAPATH_TYPE}
}

function init_sky_int_demo
{
	if is_service_enabled sky-int-demo-grafana; then
		# configure the Influx DB
		influx -execute "CREATE DATABASE ${SKY_INT_DEMO_INFLUX_DATABASE}"
	fi
}

function configure_sky_int_demo
{
	run_process sky-int-demo-collector "$SKY_INT_DEMO_COLLECTOR_DIR/server.py"
}

if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
	# Set up system services
	echo_summary "Configuring system services sky-int-demo"
	install_package python3-influxdb
	if is_service_enabled sky-int-demo-grafana; then
		# InfluxDB
		install_package influxdb influxdb-client
		# Grafana
		if ! is_package_installed grafana; then
			wget -q "https://dl.grafana.com/oss/release/grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			install_package ./"grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			rm "./grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
		fi
			
		sudo /bin/systemctl daemon-reload
		sudo /bin/systemctl enable grafana-server.service
		sudo /bin/systemctl start grafana-server.service
	fi

	# OvS
	sudo apt-get install -y linux-headers-$(uname -r) fdutils libxtst6 libnuma-dev automake libcap-ng-dev libelf-dev
	#git clone ${OVS_GIT_REPO} ${OVS_DIR}
	#cd ${OVS_DIR}
	#git checkout -f ${OVS_GIT_TAG}


elif [[ "$1" == "stack" && "$2" == "install" ]]; then
	# Perform installation of service source
	echo_summary "Installing sky-int-demo"
	install_sky_int_demo

elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
	# Configure after the other layer 1 and 2 services have been configured
	echo_summary "Configuring sky-int-demo"
	configure_sky_int_demo

elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
	# Initialize and start the template service
	echo_summary "Initializing sky-int-demo"
	init_sky_int_demo
fi

if [[ "$1" == "unstack" ]]; then
	# Shut down services
	stop_process sky-int-demo-collector
	# Check if all child collectors (workers) are down, if not kill them all
	if [ "`lsof -ti udp:9500`" != "" ]; then
		lsof -ti udp:9500 | xargs kill 
	fi

	if is_service_enabled sky-int-demo-grafana; then
		influx -execute "DROP DATABASE ${SKY_INT_DEMO_INFLUX_DATABASE}"

		sudo /bin/systemctl stop grafana-server.service
	fi
	#sudo /usr/local/share/openvswitch/scripts/ovs-ctl stop
fi

if [[ "$1" == "clean" ]]; then
	# Remove state and transient data
	# Remember clean.sh first calls unstack.sh
	sudo apt-get purge grafana influxdb

	#cd ${OVS_DIR}
	#sudo make uninstall
fi
