#!/bin/bash

function install_sky_int_demo
{
	# empty
}

function init_sky_int_demo
{
	# empty
}

function configure_sky_int_demo
{
	# empty
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
			wget "https://dl.grafana.com/oss/release/grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			install_package ./"grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
			rm "./grafana_""${SKY_INT_DEMO_GRAFANA_VER}"".deb"
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
	# Shut down template services
	# no-op
	:
fi

if [[ "$1" == "clean" ]]; then
	# Remove state and transient data
	# Remember clean.sh first calls unstack.sh
	sudo apt-get purge grafana influxdb
fi
