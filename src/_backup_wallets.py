# Simple script to back up active coin wallets

import sys, os, datetime, logging
from distutils.spawn import find_executable
import cointipbot

logging.basicConfig()
lg = logging.getLogger('cointipbot')
lg.setLevel(logging.DEBUG)

if not len(sys.argv) in [2, 3] or not os.access(sys.argv[1], os.W_OK):
	print "Usage: %s DIRECTORY [RSYNC-TO]" % sys.argv[0]
	print "(DIRECTORY must be writeable, RSYNC-TO is optional location to RSYNC the file to)"
	sys.exit(1)

ctb = cointipbot.CointipBot(self_checks=False, init_reddit=False, init_coins=True, init_db=False, init_logging=False)

if not find_executable('gzip'):
	print "gzip executable not found, please install gzip"
	sys.exit(1)

if hasattr(ctb.conf.misc.backup, 'encryptionpassphrase') and not find_executable('gpg'):
	print "encryptionpassphrase is specified but gpg executable not found, please install gpg"
	sys.exit(1)

for c in ctb.coins:
	filename = "%s/wallet_%s_%s.dat" % (sys.argv[1], ctb.conf.coins[c].unit, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

	print "Backing up %s wallet to %s..." % (ctb.conf.coins[c].name, filename)
	ctb.coins[c].conn.backupwallet(filename)

	print "Compressing..."
        os.popen("gzip --best %s" % filename)
	filename += '.gz'

	try:
		print "Encrypting..."
		os.popen("gpg --batch --passphrase '%s' -c %s" % (ctb.conf.misc.backup.encryptionpassphrase, filename))
		os.popen("rm -f %s" % filename)
		filename += '.gpg'
	except AttributeError:
		print "Not encrypting"

	if len(sys.argv) == 3:
		print "Calling rsync..."
		os.popen("rsync -urltv %s %s" % (filename, sys.argv[2]))
