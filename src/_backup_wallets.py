# Simple script to backup wallets

import sys, os, datetime
import cointipbot

if not len(sys.argv) in [2, 3] or not os.access(sys.argv[1], os.W_OK):
	print "Usgae: %s DIRECTORY [RSYNC-TO]" % sys.argv[0]
	print "(DIRECTORY must be writeable, RSYNC-TO is optional location to RSYNC the file to)"
	sys.exit(1)

cb = cointipbot.CointipBot(self_checks=False, init_reddit=False, init_coins=True, init_db=False)
_c = cb._config

for c in cb._coincon:
	_filename = "%s/wallet_%s_%s.dat" % (sys.argv[1], _c['cc'][c]['unit'], datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

	print "Backing up %s wallet to %s..." % (_c['cc'][c]['name'], _filename)
	cb._coincon[c].backupwallet(_filename)

	print "Compressing..."
        os.popen("gzip --best %s" % _filename)
	_filename += '.gz'

	try:
		print "Encrypting..."
		os.popen("echo %s | gpg --passphrase-fd 0 -c %s" % (_c['misc']['encryptionpassphrase'], _filename))
		os.popen("rm -f %s" % _filename)
		_filename += '.gpg'
	except AttributeError:
		print "Not encrypting"

	if len(sys.argv) == 3:
		print "Calling rsync..."
		os.popen("rsync -urltv %s %s" % (_filename, sys.argv[2]))
