# Simple script to back up ALTcointip database

import sys, os, datetime
from distutils.spawn import find_executable
import cointipbot

if not len(sys.argv) in [2, 3] or not os.access(sys.argv[1], os.W_OK):
	print "Usage: %s DIRECTORY [RSYNC-TO]" % sys.argv[0]
	print "(DIRECTORY must be writeable, RSYNC-TO is optional location to RSYNC the file to)"
	sys.exit(1)

ctb = cointipbot.CointipBot(self_checks=False, init_reddit=False, init_coins=False, init_db=True, init_logging=False)

if not find_executable('gzip'):
        print "gzip executable not found, please install gzip"
        sys.exit(1)

if hasattr(ctb.conf.misc.backup, 'encryptionpassphrase') and not find_executable('gpg'):
        print "encryptionpassphrase is specified but gpg executable not found, please install gpg"
        sys.exit(1)

filename = "%s/%s_%s.sql.gz" % (sys.argv[1], ctb.conf.db.auth.dbname, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

print "Backing up to %s..." % filename
os.popen("mysqldump -u %s -p%s -h %s -e --opt -c %s | gzip --best -c >%s" % (ctb.conf.db.auth.user, ctb.conf.db.auth.password, ctb.conf.db.auth.host, ctb.conf.db.auth.dbname, filename))

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
