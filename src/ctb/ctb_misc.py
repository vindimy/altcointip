import logging
from urllib2 import HTTPError

lg = logging.getLogger('cointipbot')

def _refresh_exchange_rate(ctb=None):
	return None

def _reddit_say(redditcon, cmnt, to, subj, txt):
    """
    Send a message to user or reply to a comment on Reddit
    Retry if Reddit is down
    """
    lg.debug("> _reddit_say()")
    sleep_for = 10

    while True:
        try:
            if bool(to) and bool(subj) and bool(txt):
                lg.debug("_reddit_say(): sending message to %s", to.name)
                to.send_message(subj, txt)
            elif bool(cmnt) and bool(txt):
                lg.debug("_reddit_say(): sending comment to %s", cmnt.id)
                cmnt.reply(txt)
            break
        except HTTPError, e:
            if (str(e)=="HTTP Error 504: Gateway Time-out" or str(e)=="timed out"):
                lg.warning("_reddit_say(): Reddit is down, sleeping for %d seconds...", sleep_for)
                time.sleep(sleep_for)
                sleep_for *= 2 if sleep_for < 600 else 600
                pass
        except Exception, e:
            raise

    lg.debug("< _reddit_say() DONE")
    return True

def _check_user_exists(_username, _mysqlcon):
    """
    Return true if _username is in t_users
    """
    lg.debug("> _check_user_exists(%s)", _username)
    try:
        sql = "SELECT username FROM t_users WHERE username = '%s'" % (_username)
        mysqlrow = _mysqlcon.execute(sql).fetchone()
        if mysqlrow == None:
            lg.debug("< _check_user_exists(%s) DONE (no)", _username)
            return False
        else:
            lg.debug("< _check_user_exists(%s) DONE (yes)", _username)
            return True
    except Exception, e:
        logger.error("_check_user_exists(%s): error while executing <%s>: %s", _username, sql, str(e))
        raise
    logger.debug("_check_user_exists(%s): returning None (shouldn't happen)")
    return None

def _get_reddit_user(_username, _redditcon):
    """
    Return user object if _username is a valid Reddit user,
    otherwise return None
    """
    lg.debug("> _get_reddit_user(%s)", _username)
    try:
        r = _redditcon.get_redditor(_username)
        lg.debug("< _get_reddit_user(%s) DONE", _username)
        return r
    except Exception, e:
        return None

def _delete_user(_username, _mysqlcon):
    """
    Delete _username from t_users and t_addrs tables
    """
    lg.debug("> _delete_user(%s)", _username)
    try:
        sql_arr = ["DELETE from t_users WHERE username = '%s'" % (_username),
                   "DELETE from t_addrs WHERE username = '%s'" % (_username)]
        for sql in sql_arr:
            mysqlexec = _mysqlcon.execute(sql)
            if mysqlexec.rowcount <= 0:
                lg.warning("_delete_user(%s): rowcount <= 0 while executing <%s>", _username, sql)
    except Exception, e:
        lg.error("_delete_user(%s): error while executing <%s>: %s", _username, sql, str(e))
        raise
    lg.debug("< _delete_user(%s) DONE", _username)
    return True

def _get_parent_comment_author(_comment, _reddit):
    """
    Return author of _comment's parent comment
    """
    lg.debug("> _get_parent_comment_author()")
    parentpermalink = _comment.permalink.replace(_comment.id, _comment.parent_id[3:])
    commentlinkid = _comment.link_id[3:]
    commentid = _comment.id
    parentid = _comment.parent_id[3:]
    authorid = _comment.author.name
    if (commentlinkid==parentid):
        parentcomment = _reddit.get_submission(parentpermalink)
    else:
        parentcomment = _reddit.get_submission(parentpermalink).comments[0]
    lg.debug("< _get_parent_comment_author() -> %s", parentcomment.author)
    return parentcomment.author

def _get_value(conn, param0=None, param1=None):
    """
    Fetch a value from t_values table
    """
    lg.debug("> _get_value()")
    if param0 == None:
        raise Exception("_get_value(): param0 == None")
    value = None
    sql = ""
    if param1 == None:
        sql = "SELECT value0 FROM t_values WHERE param0 = '%s' AND param1 IS NULL" % (param0)
    else:
        sql = "SELECT value0 FROM t_values WHERE param0 = '%s' AND param1 = '%s'" % (param0, param1)
    try:
        mysqlrow = conn.execute(sql).fetchone()
        if mysqlrow == None:
            lg.error("_get_value(): query <%s> didn't return any rows", sql)
            return None
        value = mysqlrow['value0']
    except Exception, e:
       lg.error("_get_value(): error executing query <%s>: %s", sql, str(e))
       raise
    lg.debug("< _get_value() DONE (%s)", str(value))
    return value

def _set_value(conn, param0=None, param1=None, value0=None):
    """
    Set a value in t_values table
    """
    lg.debug("> _set_value(%s, %s, %s)", str(param0), str(param1), str(value0))
    if param0 == None or value0 == None:
        raise Exception("_set_value(): param0 == None or value0 == None")
    sql = ""
    if param1 == None:
        sql = "REPLACE INTO t_values (param0, param1, value0) VALUES ('%s', NULL, '%s')" % (param0, str(value0))
    else:
        sql = "REPLACE INTO t_values (param0, param1, value0) VALUES ('%s', '%s', '%s')" % (param0, param1, str(value0))
    try:
        mysqlexec = conn.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.error("_set_value(): query <%s> didn't affect any rows", sql)
            return False
    except Exception, e:
        lg.error("_set_value: error executing query <%s>: %s", sql, str(e))
        raise
    lg.debug("< _set_value() DONE")
    return True
