# Here's how to add a new coin type to CointipBot

import cointipbot, logging
from ctb import ctb_misc

logging.basicConfig()
lg = logging.getLogger('cointipbot')

# Make sure CointipBot instance is NOT running

# First, enable new coin in config.yml

# Then run these two commands
ctb = cointipbot.CointipBot(self_checks=False)
#ctb_misc.add_coin('dvc', ctb.db, ctb.coins)
