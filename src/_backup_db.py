# Simple script to backup ALTcointip database

import sys, os, datetime
import cointipbot

if not len(sys.argv) in [2, 3] or not os.access(sys.argv[1], os.W_OK):
	print "Usage: %s DIRECTORY [RSYNC-TO]" % sys.argv[0]
	print "(DIRECTORY must be writeable, RSYNC-TO is optional location to RSYNC the file to)"
	sys.exit(1)

cb = cointipbot.CointipBot(self_checks=False, init_reddit=False, init_coins=False, init_db=True, init_logging=False)

_c = cb._config
_filename = "%s/%s_%s.sql.gz" % (sys.argv[1], _c['mysql']['db'], datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

print "Backing up to %s..." % _filename
os.popen("mysqldump -u %s -p%s -h %s -e --opt -c %s | gzip --best -c >%s" % (_c['mysql']['user'], _c['mysql']['pass'], _c['mysql']['host'], _c['mysql']['db'], _filename))

try:
	print "Encrypting..."
	#os.popen("echo %s | gpg --batch --passphrase-fd 0 -c %s" % (_c['misc']['encryptionpassphrase'], _filename))
	os.popen("gpg --batch --passphrase '%s' -c %s" % (_c['misc']['encryptionpassphrase'], _filename))
	os.popen("rm -f %s" % _filename)
	_filename += '.gpg'
except AttributeError:
	print "Not encrypting"

if len(sys.argv) == 3:
	print "Calling rsync..."
	os.popen("rsync -urltv %s %s" % (_filename, sys.argv[2]))
