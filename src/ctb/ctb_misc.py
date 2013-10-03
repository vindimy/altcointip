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

def _refresh_exchange_rate(ctb=None, exchange='vircurex'):
    """
    Refresh coin/fiat exchange rate values
    """
    lg.debug("> _refresh_exchange_rate()")

    if not bool(ctb):
        raise Exception("_refresh_exchange_rate(): ctb is not set")

    if exchange == 'btce':
        _refresh_exchange_rate_btce(ctb=ctb)
    elif exchange == 'vircurex':
        _refresh_exchange_rate_vircurex(ctb=ctb)
    else:
        raise Exception("_refresh_exchange_rate(): invalid value '%s'" % exchange)

    lg.debug("< _refresh_exchange_rate() DONE")
    return True

def _refresh_exchange_rate_btce(ctb=None):
    """
    Refresh coin/fiat exchange rate values using BTC-e
    """
    lg.debug("> _refresh_exchange_rate_btce()")

    # Return if rate has been checked in the past hour
    seconds = int(1 * 3600)
    if ctb._ticker_last_refresh + seconds > int(time.mktime(time.gmtime())):
        lg.debug("< _refresh_exchange_rate_btce() DONE (skipping)")
        return True

    # Determine pairs to request from BTC-e
    if not bool(ctb._ticker_pairs):
        # Always request btc_usd pair
        ctb._ticker_pairs = {'btc_usd': 'True'}
        # Request other btc_FIAT pairs
        for f in ctb._config['fiat']:
            if ctb._config['fiat'][f]['enabled'] and not ctb._config['fiat'][f]['unit'] == 'usd':
                ctb._ticker_pairs['btc_'+ctb._config['fiat'][f]['unit']] = 'True'
        # Request each COIN_btc pair
        for c in ctb._coincon:
            ctb._ticker_pairs[c+'_btc'] = 'True'

    # Create instance of CtbBtce
    if not bool(ctb._ticker):
        ctb._ticker = ctb_btce.CtbBtce()

    # Send request and update values
    ticker_val = ctb._ticker.update(ctb._ticker_pairs)
    if bool(ticker_val) and ('btc_usd' in ticker_val):
        ctb._ticker_val = ticker_val
    else:
        lg.warning("_refresh_exchange_rate_btce(): pair btc_usc not found in ticker_val (bad response?), stopping")
        return False

    # Set btc_btc ticker value to 1.0
    ctb._ticker_val['btc_btc']['avg'] = 1.0

    # Update last refresh time
    ctb._ticker_last_refresh = int(time.mktime(time.gmtime()))

    lg.debug("< _refresh_exchange_rate_btce() DONE")
    return True

def _refresh_exchange_rate_vircurex(ctb=None):
    """
    Refresh coin/fiat exchange rate values using Vircurex
    """
    lg.debug("> _refresh_exchange_rate_vircurex()")

    # Return if rate has been checked in the past hour
    seconds = int(1 * 3600)
    if ctb._ticker_last_refresh + seconds > int(time.mktime(time.gmtime())):
        lg.debug("< _refresh_exchange_rate_vircurex() DONE (skipping)")
        return True

    # Determine pairs to request from Vircurex
    if not bool(ctb._ticker_pairs):
        # Always request btc_usd pair
        ctb._ticker_pairs = {'btc_usd': 'True'}
        # Request other btc_FIAT pairs
        for f in ctb._config['fiat']:
            if ctb._config['fiat'][f]['enabled'] and not ctb._config['fiat'][f]['unit'] == 'usd':
                ctb._ticker_pairs['btc_'+ctb._config['fiat'][f]['unit']] = 'True'
        # Request each COIN_btc pair
        for c in ctb._coincon:
            if not c == 'btc':
                ctb._ticker_pairs[c+'_btc'] = 'True'

    try:
        # Update values
        for p in ctb._ticker_pairs:
            lg.debug("_refresh_exchange_rate_vircurex(): getting pair %s", p)
            pair = pyvircurex.Pair(p)
            ctb._ticker_val[p] = {}
            ctb._ticker_val[p]['avg'] = (float(pair.lowest_ask) + float(pair.highest_bid)) / 2.0
    except Exception, e:
        lg.warning("_refresh_exchange_rate_vircurex(): caught Exception: %s", str(e))
        return False

    # Set btc_btc ticker value to 1.0
    ctb._ticker_val['btc_btc'] = {}
    ctb._ticker_val['btc_btc']['avg'] = 1.0

    # Update last refresh time
    ctb._ticker_last_refresh = int(time.mktime(time.gmtime()))

    lg.debug("< _refresh_exchange_rate_vircurex() DONE")
    return True

def _praw_call(prawFunc, *extraArgs, **extraKwArgs):
    """
    Call prawFunc() with extraArgs and extraKwArgs
    Retry if Reddit is down
    """
    while True:
        try:
            res = prawFunc(*extraArgs, **extraKwArgs)
            return res
        except APIException as e:
            lg.warning("_praw_call(): failed (%s)", str(e))
            return False
        except ExceptionList as el:
            for e in el:
                lg.warning("_praw_call(): failed (%s)", str(e))
            return False
        except (HTTPError, RateLimitExceeded) as e:
            if str(e) == "403 Client Error: Forbidden":
                lg.warning("_praw_call(): 403 forbidden %s", msg.permalink)
                return False
            lg.warning("_praw_call(): Reddit is down (%s), sleeping...", str(e))
            time.sleep(10)
            pass
        except timeout:
            lg.warning("_praw_call(): Reddit is down (timeout), sleeping...")
            time.sleep(10)
            pass
        except Exception as e:
            raise
    return True

def _reddit_get_parent_author(_comment, _reddit, _ctb):
    """
    Return author of _comment's parent comment
    """
    lg.debug("> _get_parent_comment_author()")

    while True:
        try:
            parentpermalink = _comment.permalink.replace(_comment.id, _comment.parent_id[3:])
            commentlinkid = None
            if hasattr(_comment, 'link_id'):
                commentlinkid = _comment.link_id[3:]
            else:
                _comment2 = _reddit.get_submission(_comment.permalink).comments[0]
                commentlinkid = _comment2.link_id[3:]
            parentid = _comment.parent_id[3:]

            if commentlinkid == parentid:
                parentcomment = _reddit.get_submission(parentpermalink)
            else:
                parentcomment = _reddit.get_submission(parentpermalink).comments[0]

            lg.debug("< _get_parent_comment_author(%s) -> %s", _comment.id, parentcomment.author.name)
            return parentcomment.author.name
        except APIException as e:
            lg.error("_reddit_get_parent_author(%s): failed (%s)", _comment.id, str(e))
            raise
        except ExceptionList as el:
            for e in el:
                lg.error("_reddit_get_parent_author(%s): failed (%s)", _comment.id, str(e))
            raise
        except (HTTPError, RateLimitExceeded) as e:
            lg.warning("_get_parent_comment_author(%s): Reddit is down (%s), sleeping...", _comment.id, str(e))
            time.sleep(_ctb._DEFAULT_SLEEP_TIME)
            pass
        except timeout:
            lg.warning("_get_parent_comment_author(%s): Reddit is down (timeout), sleeping...", _comment.id)
            time.sleep(_ctb._DEFAULT_SLEEP_TIME)
            pass
        except Exception as e:
            raise

    lg.error("_get_parent_comment_author(): returning None (should not get here)")
    return None

def _get_value(conn, param0=None):
    """
    Fetch a value from t_values table
    """
    lg.debug("> _get_value()")
    if param0 == None:
        raise Exception("_get_value(): param0 == None")
    value = None
    sql = "SELECT value0 FROM t_values WHERE param0 = %s"
    try:
        mysqlrow = conn.execute(sql, (param0)).fetchone()
        if mysqlrow == None:
            lg.error("_get_value(): query <%s> didn't return any rows", sql % (param0))
            return None
        value = mysqlrow['value0']
    except Exception, e:
       lg.error("_get_value(): error executing query <%s>: %s", sql % (param0), str(e))
       raise
    lg.debug("< _get_value() DONE (%s)", str(value))
    return value

def _set_value(conn, param0=None, value0=None):
    """
    Set a value in t_values table
    """
    lg.debug("> _set_value(%s, %s)", str(param0), str(value0))
    if param0 == None or value0 == None:
        raise Exception("_set_value(): param0 == None or value0 == None")
    sql = "REPLACE INTO t_values (param0, value0) VALUES (%s, %s)"
    try:
        mysqlexec = conn.execute(sql, (param0, str(value0)))
        if mysqlexec.rowcount <= 0:
            lg.error("_set_value(): query <%s> didn't affect any rows", sql % (param0, str(value0)))
            return False
    except Exception, e:
        lg.error("_set_value: error executing query <%s>: %s", sql % (param0, str(value0)), str(e))
        raise
    lg.debug("< _set_value() DONE")
    return True

def _add_coin(coin, mysqlcon, coincon):
    """
    Add new coin address to each user
    """
    lg.debug("> _add_coin(%s)", coin)
    sql_select = "SELECT username FROM t_users WHERE username NOT IN (SELECT username FROM t_addrs WHERE coin = %s) ORDER BY username"
    sql_insert = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"
    try:
        mysqlsel = mysqlcon.execute(sql_select, (coin))
        for m in mysqlsel:
            # Generate new coin address for user
            new_addr = coincon[coin].getnewaddress(m['username'].lower())
            lg.info("_add_coin(): got new address %s for %s", new_addr, m['username'])
            # Add new coin address to MySQL
            mysqlins = mysqlcon.execute(sql_insert, (m['username'].lower(), coin, new_addr))
            if mysqlins.rowcount <= 0:
                raise Exception("_add_coin(%s): rowcount <= 0 when executing <%s>", coin, sql_insert % (m['username'].lower(), coin, new_addr))
            time.sleep(1)
    except Exception, e:
        lg.error("_add_coin(%s): error: %s", coin, str(e))
        raise
    lg.debug("< _add_coin(%s) DONE", coin)
    return True
