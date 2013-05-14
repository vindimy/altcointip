import ctb_user

import logging

lg = logging.getLogger('cointipbot')

def _refresh_exchange_rate(ctb=None):
	return None

def _reddit_reply(msg, txt):
    """
    Reply to a comment on Reddit
    Retry if Reddit is down
    """
    lg.debug("> _reddit_reply(%s)", msg.id)

    sleep_for = 10
    while True:
        try:
            msg.reply(txt)
            break
        except praw.HTTPError, e:
            if e.code in [500, 502, 503, 504]:
                lg.warning("_reddit_reply(): Reddit is down, sleeping for %s seconds...", sleep_for)
                time.sleep(sleep_for)
                sleep_for *= 2 if sleep_for < 600 else 600
                pass
            else:
                raise
        except Exception, e:
            raise

    lg.debug("< _reddit_reply(%s) DONE", msg.id)
    return True

def _reddit_get_parent_author(_comment, _reddit):
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
    return CtbUser(name=parentcomment.author.name, redditobj=parentcomment.author)

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
