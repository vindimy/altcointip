# Here's how to add a new coin type to CointipBot

import cointipbot
from ctb import ctb_misc

# Make sure CointipBot instance is NOT running

# First, enable new coin in config.yml

# Then run these two commands
cb = cointipbot.CointipBot(self_checks=False)
#ctb_misc._add_coin('dvc', cb._mysqlcon, cb._coincon)
