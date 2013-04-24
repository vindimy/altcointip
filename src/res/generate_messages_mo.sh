#!/bin/bash

# aptitude install gettext

if [ -z $1 ] ; then
	echo "Usage: $0 FILLENAME"
	echo "Example: $0 messages_jp"
	exit 1
fi

pygettext -o ./$1.po ../cointipbot.py && msgfmt -o ./$1.mo ./$1.po

# messages_en.pot can be given to translators and resulting messages_LANG.mo used here
