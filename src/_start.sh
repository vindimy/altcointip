#!/bin/bash

user=$1

if [ ! -f ./cointipbot.py ] ; then
	# Output help message and exit
	echo "Usage: $0 [username]"
	echo "if [username] is specified, script will be started as user [username]"
	echo "$0 must be run from 'src' directory of ALTcointip"
	exit 1
fi

if [ -z "$user" ] ; then
	# Run as current user
	python -c 'import cointipbot; cb=cointipbot.CointipBot(); cb.main()'
else
	# Run as $user
	sudo su - $user -c "cd `pwd` && python -c 'import cointipbot; cb=cointipbot.CointipBot(); cb.main()'"
fi
