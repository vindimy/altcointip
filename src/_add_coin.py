# Here's how to add a new coin type to CointipBot

# * Make sure CointipBot instance is NOT running
# * Install and run coin daemon, make sure it's synced with network
# * Configure and nable new coin in config.yml
# * Then run this script, specifying coin (such as "python _add_coin.py btc")
# * After this script has finished, you can reusme the tip bot normally

import cointipbot, logging, sys
from ctb import ctb_coin, ctb_misc

if not len(sys.argv) == 2:
        print "Usage: %s COIN" % sys.argv[0]
        print "(COIN refers to ctb.conf[COIN], a hash location in coins.yml)"
        sys.exit(1)

coin = sys.argv[1]

logging.basicConfig()
lg = logging.getLogger('cointipbot')
lg.setLevel(logging.DEBUG)

ctb = cointipbot.CointipBot(self_checks=False, init_reddit=False, init_coins=False, init_exchanges=False, init_db=True, init_logging=True)
ctb.coins[coin] = ctb_coin.CtbCoin(_conf=ctb.conf.coins[coin])
ctb_misc.add_coin(coin, ctb.db, ctb.coins)
