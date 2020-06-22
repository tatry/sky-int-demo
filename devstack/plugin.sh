#!/bin/bash

function install_sky_int_demo
{
	# empty
	:
}

function init_sky_int_demo
{
	# empty
	:
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
		install_package influxdb
		# Grafana
		if ! is_package_installed grafana; then
			wget -q "https://dl.grafana.com/oss/release/grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			install_package ./"grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			rm "./grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			
			sudo /bin/systemctl daemon-reload
			sudo /bin/systemctl enable grafana-server.service
			sudo /bin/systemctl start grafana-server.service
		fi
	fi

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

	sudo /bin/systemctl stop grafana-server.service
fi

if [[ "$1" == "clean" ]]; then
	# Remove state and transient data
	# Remember clean.sh first calls unstack.sh
	sudo apt-get purge grafana influxdb
fi
