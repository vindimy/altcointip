import ctb_user, ctb_btce

import logging, time

from requests.exceptions import HTTPError
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

lg = logging.getLogger('cointipbot')

def _refresh_exchange_rate(ctb=None):
    """
    Refresh coin/fiat exchange rate values
    """
    lg.debug("> _refresh_exchange_rate()")

    if not bool(ctb):
        raise Exception("_refresh_exchange_rate(): ctb is not set")

    # Return if rate has been checked in the past hour
    seconds = int(1 * 3600)
    if ctb._ticker_last_refresh + seconds > int(time.mktime(time.gmtime())):
        lg.debug("< _refresh_exchange_rate() DONE (skipping)")
        return True

    # Determine pairs to request from BTC-e
    if not bool(ctb._ticker_pairs):
        ctb._ticker_pairs = {'btc_usd': 'True'}
        for c in ctb._coincon:
            ctb._ticker_pairs[c+'_btc'] = 'True'

    # Create instance of CtbBtce
    if not bool(ctb._ticker):
        ctb._ticker = ctb_btce.CtbBtce()

    # Send request and update values
    ticker_val = ctb._ticker.update(ctb._ticker_pairs)
    if bool(ticker_val):
        ctb._ticker_val = ticker_val

    # Update last refresh time
    ctb._ticker_last_refresh = int(time.mktime(time.gmtime()))

    lg.debug("< _refresh_exchange_rate() DONE")
    return True

def _reddit_reply(msg, txt):
    """
    Reply to a comment/message on Reddit
    Retry if Reddit is down
    """
    lg.debug("> _reddit_reply()")

    while True:
        try:
            msg.reply(txt)
            break
        except APIException as e:
            lg.warning("_reddit_reply(): failed (%s)", str(e))
            return False
        except ExceptionList as el:
            for e in el:
                lg.warning("_reddit_reply(): failed (%s)", str(e))
            return False
        except (HTTPError, RateLimitExceeded) as e:
            if str(e) == "403 Client Error: Forbidden":
                lg.warning("_reddit_reply(): banned to reply to %s", msg.permalink)
                return False
            lg.warning("_reddit_reply(): Reddit is down (%s), sleeping...", str(e))
            time.sleep(30)
            pass
        except timeout:
            lg.warning("_reddit_reply(): Reddit is down (timeout), sleeping...")
            time.sleep(30)
            pass
        except Exception as e:
            raise

    lg.debug("< _reddit_reply(%s) DONE", msg.id)
    return True

def _reddit_get_parent_author(_comment, _reddit, _ctb):
    """
    Return author of _comment's parent comment
    """
    lg.debug("> _get_parent_comment_author()")
    while True:
        try:
            parentpermalink = _comment.permalink.replace(_comment.id, _comment.parent_id[3:])
            commentlinkid = _comment.link_id[3:]
            commentid = _comment.id
            parentid = _comment.parent_id[3:]
            authorid = _comment.author.name
            if (commentlinkid==parentid):
                parentcomment = _reddit.get_submission(parentpermalink)
            else:
                parentcomment = _reddit.get_submission(parentpermalink).comments[0]
            lg.debug("< _get_parent_comment_author() -> %s", parentcomment.author.name)
            return parentcomment.author.name
        except HTTPError, e:
            lg.warning("_get_parent_comment_author(): Reddit is down (%s), sleeping...", str(e))
            time.sleep(_ctb._DEFAULT_SLEEP_TIME)
            pass
        except timeout:
            lg.warning("_get_parent_comment_author(): Reddit is down (timeout), sleeping...")
            time.sleep(_ctb._DEFAULT_SLEEP_TIME)
            pass
        except Exception, e:
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
    sql_select = "SELECT username FROM t_users ORDER BY username"
    sql_insert = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"
    try:
        mysqlsel = mysqlcon.execute(sql_select)
        for m in mysqlsel:
            # Generate new coin address for user
            new_addr = coincon[coin].getnewaddress(m['username'].lower())
            # Add new coin address to MySQL
            mysqlins = mysqlcon.execute(sql_insert, (m['username'].lower(), coin, new_addr))
            if mysqlins.rowcount <= 0:
                raise Exception("_add_coin(%s): rowcount <= 0 when executing <%s>", coin, sql_insert % (m['username'].lower(), coin, new_addr))
            time.sleep(5)
    except Exception, e:
        lg.error("_add_coin(%s): error: %s", coin, str(e))
        raise
    lg.debug("< _add_coin(%s) DONE", coin)
    return True

