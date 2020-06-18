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
	#install_package cowsay

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
	# no-op
	:
fi
