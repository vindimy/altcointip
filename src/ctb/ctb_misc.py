"""
    This file is part of ALTcointip.

    ALTcointip is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ALTcointip is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with ALTcointip.  If not, see <http://www.gnu.org/licenses/>.
"""

import ctb_user, ctb_btce, pyvircurex

import logging, time

from requests.exceptions import HTTPError
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

lg = logging.getLogger('cointipbot')

def refresh_exchange_rate(ctb=None, exchange='vircurex'):
    """
    Refresh coin/fiat exchange rate values
    """
    lg.debug("> refresh_exchange_rate()")

    if not bool(ctb):
        raise Exception("refresh_exchange_rate(): ctb is not set")

    if exchange == 'btce':
        refresh_exchange_rate_btce(ctb=ctb)
    elif exchange == 'vircurex':
        refresh_exchange_rate_vircurex(ctb=ctb)
    else:
        raise Exception("refresh_exchange_rate(): invalid value '%s'" % exchange)

    lg.debug("< refresh_exchange_rate() DONE")
    return True

def refresh_exchange_rate_btce(ctb=None):
    """
    Refresh coin/fiat exchange rate values using BTC-e
    """
    lg.debug("> refresh_exchange_rate_btce()")

    # Return if rate has been checked in the past hour
    seconds = int(1 * 3600)
    if ctb.ticker_last_refresh + seconds > int(time.mktime(time.gmtime())):
        lg.debug("< refresh_exchange_rate_btce() DONE (skipping)")
        return True

    # Determine pairs to request from BTC-e
    if not bool(ctb.ticker_pairs):
        # Always request btc_usd pair
        ctb.ticker_pairs = {'btc_usd': 'True'}
        # Request other btc_FIAT pairs
        for f in vars(ctb.conf.fiat):
            if ctb.conf.fiat[f].enabled and not ctb.conf.fiat[f].unit == 'usd':
                ctb.ticker_pairs['btc_'+ctb.conf.fiat[f].unit] = 'True'
        # Request each COIN_btc pair
        for c in ctb.coins:
            ctb.ticker_pairs[c+'_btc'] = 'True'

    # Create instance of CtbBtce
    if not bool(ctb._ticker):
        ctb._ticker = ctb_btce.CtbBtce()

    # Send request and update values
    ticker_val = ctb._ticker.update(ctb.ticker_pairs)
    if bool(ticker_val) and ('btc_usd' in ticker_val):
        ctb.ticker_val = ticker_val
    else:
        lg.warning("refresh_exchange_rate_btce(): pair btc_usc not found in ticker_val (bad response?), stopping")
        return False

    # Set btc_btc ticker value to 1.0
    ctb.ticker_val['btc_btc']['avg'] = 1.0

    # Update last refresh time
    ctb.ticker_last_refresh = int(time.mktime(time.gmtime()))

    lg.debug("< refresh_exchange_rate_btce() DONE")
    return True

def refresh_exchange_rate_vircurex(ctb=None):
    """
    Refresh coin/fiat exchange rate values using Vircurex
    """
    lg.debug("> refresh_exchange_rate_vircurex()")

    # Return if rate has been checked in the past hour
    seconds = int(1 * 3600)
    if ctb.ticker_last_refresh + seconds > int(time.mktime(time.gmtime())):
        lg.debug("< refresh_exchange_rate_vircurex() DONE (skipping)")
        return True

    # Determine pairs to request from Vircurex
    if not bool(ctb.ticker_pairs):
        # Always request btc_usd pair
        ctb.ticker_pairs = {'btc_usd': 'True'}
        # Request other btc_FIAT pairs
        for f in vars(ctb.conf.fiat):
            if ctb.conf.fiat[f].enabled and not ctb.conf.fiat[f].unit == 'usd':
                ctb.ticker_pairs['btc_'+ctb.conf.fiat[f].unit] = 'True'
        # Request each COIN_btc pair
        for c in ctb.coins:
            if not c == 'btc':
                ctb.ticker_pairs[c+'_btc'] = 'True'

    try:
        # Update values
        for p in ctb.ticker_pairs:
            lg.debug("refresh_exchange_rate_vircurex(): getting pair %s", p)
            pair = pyvircurex.Pair(p)
            ctb.ticker_val[p] = {}
            ctb.ticker_val[p]['avg'] = (float(pair.lowest_ask) + float(pair.highest_bid)) / 2.0
    except Exception, e:
        lg.warning("refresh_exchange_rate_vircurex(): caught Exception: %s", e)
        return False

    # Set btc_btc ticker value to 1.0
    ctb.ticker_val['btc_btc'] = {}
    ctb.ticker_val['btc_btc']['avg'] = 1.0

    # Update last refresh time
    ctb.ticker_last_refresh = int(time.mktime(time.gmtime()))

    lg.debug("< refresh_exchange_rate_vircurex() DONE")
    return True

def praw_call(prawFunc, *extraArgs, **extraKwArgs):
    """
    Call prawFunc() with extraArgs and extraKwArgs
    Retry if Reddit is down
    """
    while True:
        try:
            res = prawFunc(*extraArgs, **extraKwArgs)
            return res
        except APIException as e:
            lg.warning("praw_call(): failed (%s)", e)
            raise
        except ExceptionList as el:
            for e in el:
                lg.warning("praw_call(): failed (%s)", e)
            raise
        except (HTTPError, RateLimitExceeded) as e:
            if str(e) == "403 Client Error: Forbidden":
                lg.warning("praw_call(): 403 forbidden %s", msg.permalink)
                return False
            lg.warning("praw_call(): Reddit is down (%s), sleeping...", e)
            time.sleep(10)
            pass
        except timeout:
            lg.warning("praw_call(): Reddit is down (timeout), sleeping...")
            time.sleep(10)
            pass
        except Exception as e:
            raise
    return True

def reddit_get_parent_author(comment, reddit, ctb):
    """
    Return author of comment's parent comment
    """
    lg.debug("> reddit_get_parent_author()")

    while True:
        try:
            parentpermalink = comment.permalink.replace(comment.id, comment.parent_id[3:])
            commentlinkid = None
            if hasattr(comment, 'link_id'):
                commentlinkid = comment.link_id[3:]
            else:
                comment2 = reddit.get_submission(comment.permalink).comments[0]
                commentlinkid = comment2.link_id[3:]
            parentid = comment.parent_id[3:]

            if commentlinkid == parentid:
                parentcomment = reddit.get_submission(parentpermalink)
            else:
                parentcomment = reddit.get_submission(parentpermalink).comments[0]

            lg.debug("< reddit_get_parent_author(%s) -> %s", comment.id, parentcomment.author.name)
            return parentcomment.author.name

        except APIException as e:
            lg.error("reddit_get_parent_author(%s): failed (%s)", comment.id, e)
            raise
        except ExceptionList as el:
            for e in el:
                lg.error("reddit_get_parent_author(%s): failed (%s)", comment.id, e)
            raise
        except (HTTPError, RateLimitExceeded) as e:
            lg.warning("reddit_get_parent_author(%s): Reddit is down (%s), sleeping...", comment.id, e)
            time.sleep(ctb.conf.misc.times.sleep_seconds)
            pass
        except timeout:
            lg.warning("reddit_get_parent_author(%s): Reddit is down (timeout), sleeping...", comment.id)
            time.sleep(ctb.conf.misc.times.sleep_seconds)
            pass
        except Exception as e:
            raise

    lg.error("reddit_get_parent_author(): returning None (should not get here)")
    return None

def get_value(conn, param0=None):
    """
    Fetch a value from t_values table
    """
    lg.debug("> get_value()")

    if param0 == None:
        raise Exception("get_value(): param0 == None")

    value = None
    sql = "SELECT value0 FROM t_values WHERE param0 = %s"

    try:
        mysqlrow = conn.execute(sql, (param0)).fetchone()
        if mysqlrow == None:
            lg.error("get_value(): query <%s> didn't return any rows", sql % (param0))
            return None
        value = mysqlrow['value0']

    except Exception, e:
       lg.error("get_value(): error executing query <%s>: %s", sql % (param0), e)
       raise

    lg.debug("< get_value() DONE (%s)", value)
    return value

def set_value(conn, param0=None, value0=None):
    """
    Set a value in t_values table
    """
    lg.debug("> set_value(%s, %s)", param0, value0)

    if param0 == None or value0 == None:
        raise Exception("set_value(): param0 == None or value0 == None")
    sql = "REPLACE INTO t_values (param0, value0) VALUES (%s, %s)"

    try:
        mysqlexec = conn.execute(sql, (param0, value0))
        if mysqlexec.rowcount <= 0:
            lg.error("set_value(): query <%s> didn't affect any rows", sql % (param0, value0))
            return False

    except Exception, e:
        lg.error("set_value: error executing query <%s>: %s", sql % (param0, value0), e)
        raise

    lg.debug("< set_value() DONE")
    return True

def add_coin(coin, db, coins):
    """
    Add new coin address to each user
    """
    lg.debug("> add_coin(%s)", coin)

    sql_select = "SELECT username FROM t_users WHERE username NOT IN (SELECT username FROM t_addrs WHERE coin = %s) ORDER BY username"
    sql_insert = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"

    try:
        mysqlsel = db.execute(sql_select, (coin))
        for m in mysqlsel:
            # Generate new coin address for user
            new_addr = coins[coin].getnewaddr(_user=m['username'])
            lg.info("add_coin(): got new address %s for %s", new_addr, m['username'])
            # Add new coin address to MySQL
            mysqlins = db.execute(sql_insert, (m['username'].lower(), coin, new_addr))
            if mysqlins.rowcount <= 0:
                raise Exception("add_coin(%s): rowcount <= 0 when executing <%s>", coin, sql_insert % (m['username'].lower(), coin, new_addr))
            time.sleep(1)

    except Exception, e:
        lg.error("add_coin(%s): error: %s", coin, e)
        raise

    lg.debug("< add_coin(%s) DONE", coin)
    return True

class DotDict(object):
    def __init__(self, d):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
               setattr(self, a, [DotDict(x) if isinstance(x, dict) else x for x in b])
            else:
               setattr(self, a, DotDict(b) if isinstance(b, dict) else b)
    def __getitem__(self, val):
        return getattr(self, val)
