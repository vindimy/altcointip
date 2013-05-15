import ctb_misc

import logging, re, praw, urllib2

lg = logging.getLogger('cointipbot')

class CtbUser(object):
    """
    User class for cointip bot
    """

    # Basic properties
    _NAME=None
    _GIFTAMNT=None
    _JOINDATE=None
    _ADDR={}
    _TRANS={}

    # Objects
    _REDDITOBJ=None
    _CTB=None
    _CC=None

    def __init__(self, name=None, redditobj=None, ctb=None):
        """
        Initialize CtbUser object with given parameters
        """
        lg.debug("> CtbUser::__init__(%s)", name)

        if not bool(name):
            raise Exception("CtbUser::__init__(): name must be set")
        self._NAME = name

        if not bool(ctb):
            raise Exception("CtbUser::__init__(): ctb must be set")
        self._CTB = ctb
        self._CC = self._CTB._config['cc']

        if bool(redditobj):
            self._REDDITOBJ = redditobj

        lg.debug("< CtbUser::__init__(%s) DONE", name)

    def get_balance(self, coin=None, kind=None):
        """
        If coin is specified, return float with coin balance for user
        Else, return a dict with balance of each coin for user
        """
        lg.debug("> CtbUser::balance(%s)", self._NAME)

        if not bool(coin) or not bool(kind):
            raise Exception("CtbUser::balance(%s): coin or kind not set" % self._NAME)

        lg.debug("CtbUser::balance(%s): getting %s %s balance", self._NAME, coin, kind)
        balance = self._CTB._coincon[coin].getbalance(self._NAME.lower(), self._CC[coin]['minconf'][kind])

        lg.debug("< CtbUser::balance(%s) DONE", self._NAME)
        return balance

    def get_addr(self, coin=None):
        """
        Return coin address of user
        """
        lg.debug("> CtbUser::get_addr(%s, %s)", self._NAME, coin)

        if hasattr(self._ADDR, coin):
            return self._ADDR[coin]

        sql = "SELECT address from t_addrs WHERE username = %s AND coin = %s"
        mysqlrow = self._CTB._mysqlcon.execute(sql, (self._NAME.lower(), coin.lower())).fetchone()
        if mysqlrow == None:
            lg.debug("< CtbUser::get_addr(%s, %s) DONE (no)", self._NAME, coin)
            return None
        else:
            self._ADDR[coin] = mysqlrow['address']
            lg.debug("< CtbUser::get_addr(%s, %s) DONE (%s)", self._NAME, coin, self._ADDR[coin])
            return self._ADDR[coin]

        lg.debug("< CtbUser::get_addr(%s, %s) DONE (should never happen)", self._NAME, coin)
        return None

    def get_tx_history(self, coin=None):
        """
        Return a dict with user transactions
        """
        return None

    def is_on_reddit(self):
        """
        Return true if user is on Reddit
        Also set _REDDITOBJ pointer while at it
        """
        lg.debug("> CtbUser::is_on_reddit(%s)", self._NAME)

        # Return true if _REDDITOBJ is already set
        if bool(self._REDDITOBJ):
            lg.debug("< CtbUser::is_on_reddit(%s) DONE (yes)", self._NAME)
            return True

        sleep_for = 10
        while True:
            # This loop retries if Reddit is down
            try:
                self._REDDITOBJ = self._CTB._redditcon.get_redditor(self._NAME)
                lg.debug("< CtbUser::is_on_reddit(%s) DONE (yes)", self._NAME)
                return True
            except urllib2.HTTPError, e:
                if e.code in [429, 500, 502, 503, 504]:
                    lg.warning("CtbUser::is_on_reddit(%s): Reddit is down, sleeping for %s seconds...",  self._NAME, str(sleep_for))
                    time.sleep(sleep_for)
                    sleep_for *= 2 if sleep_for < 600 else 600
                    pass
                else:
                    lg.debug("< CtbUser::is_on_reddit(%s) DONE (no)", self._NAME)
                    return False
            except Exception, e:
                lg.debug("< CtbUser::is_on_reddit(%s) DONE (no)", self._NAME)
                return False

        lg.warning("< CtbUser::is_on_reddit(%s): returning None (shouldn't happen)", self._NAME)
        return None

    def is_registered(self):
        """
        Return true if user is registered with CointipBot
        """
        lg.debug("> CtbUser::is_registered(%s)", self._NAME)

        try:
            # First, check t_users table
            sql = "SELECT * FROM t_users WHERE username = %s"
            mysqlrow = self._CTB._mysqlcon.execute(sql, (self._NAME.lower())).fetchone()
            if mysqlrow == None:
                lg.debug("< CtbUser::is_registered(%s) DONE (no)", self._NAME)
                return False
            else:
                # Next, check t_addrs table
                sql_coins = "SELECT COUNT(*) AS count FROM t_addrs WHERE username = %s"
                mysqlrow_coins = self._CTB._mysqlcon.execute(sql_coins, (self._NAME.lower())).fetchone()
                if int(mysqlrow_coins['count']) != len(self._CTB._coincon):
                    raise Exception("CtbUser::is_registered(%s): database returns %s coins but %s active" % (mysqlrow_coins['count'], len(self._CTB._coincon)))
                # Set some properties
                self._GIFTAMNT = mysqlrow['giftamount']
                # Done
                lg.debug("< CtbUser::is_registered(%s) DONE (yes)", self._NAME)
                return True
        except Exception, e:
            lg.error("CtbUser::is_registered(%s): error while executing <%s>: %s", self._NAME, sql % self._NAME.lower(), str(e))
            raise

        lg.warning("< CtbUser::is_registered(%s): returning None (shouldn't happen)", self._NAME)
        return None

    def tell(self, subj=None, msg=None):
        """
        Send a Reddit message to user
        """
        lg.debug("> CtbUser::tell(%s)", self._NAME)

        if not bool(subj) or not bool(msg):
            raise Exception("CtbUser::tell(%s): subj or msg not set", self._NAME)

        if not self.is_on_reddit():
            raise Exception("CtbUser::tell(%s): not a Reddit user", self._NAME)

        sleep_for = 10
        while True:
            # This loop retries sending message if Reddit is down
            try:
                lg.debug("CtbUser::tell(%s): sending message", self._NAME)
                self._REDDITOBJ.send_message(subj, msg)
                break
            except urllib2.HTTPError, e:
                if e.code in [429, 500, 502, 503, 504]:
                    lg.warning("CtbUser::tell(%s): Reddit is down, sleeping for %s seconds...",  self._NAME, str(sleep_for))
                    time.sleep(sleep_for)
                    sleep_for *= 2 if sleep_for < 600 else 600
                    pass
                else:
                    raise
            except Exception, e:
                raise

        lg.debug("< CtbUser::tell(%s) DONE", self._NAME)
        return True

    def register(self):
        """
        Add user to database and generate coin addresses
        """
        lg.debug("> CtbUser::register(%s)", self._NAME)

        # Add user to database
        try:
            sql_adduser = "INSERT INTO t_users (username) VALUES (%s)"
            mysqlexec = self._CTB._mysqlcon.execute(sql_adduser, (self._NAME.lower()))
            if mysqlexec.rowcount <= 0:
                raise Exception("CtbUser::register(%s): rowcount <= 0 while executing <%s>" % ( self._NAME, sql_adduser % (self._NAME.lower())))
        except Exception, e:
            lg.error("CtbUser::register(%s): exception while executing <%s>: %s", self._NAME, sql_adduser % (self._NAME.lower()), str(e))
            raise

        # Get new coin addresses
        new_addrs = {}
        for c in self._CTB._coincon:
            try:
                # Generate new address for user
                new_addrs[c] = self._CTB._coincon[c].getaccountaddress(self._NAME.lower())
                if not bool(new_addrs[c]):
                    new_addrs[c] = _coincon[c].getnewaddress(self._NAME.lower())
                lg.debug("CtbUser::register(%s): got %s address %s", self._NAME, c, new_addrs[c])
            except Exception, e:
                lg.error("CtbUser::register(%s): error getting %s address: %s", self._NAME, c, str(e))
                _delete_user(self._NAME, self._CTB._mysqlcon)
                raise

        # Add coin addresses to database
        for c in new_addrs:
            try:
                sql_addr = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"
                mysqlexec = self._CTB._mysqlcon.execute(sql_addr, (self._NAME.lower(), c, new_addrs[c]))
                if mysqlexec.rowcount <= 0:
                    # Undo change to database
                    _delete_user(self._NAME, self._CTB._mysqlcon)
                    raise Exception("CtbUser::register(%s): rowcount <= 0 while executing <%s>" % (self._NAME, sql_addr % (self._NAME.lower(), c, new_addrs[c])))
            except Exception, e:
                # Undo change to database
                _delete_user(self._NAME, self._CTB._mysqlcon)
                raise

        lg.debug("< CtbUser::register(%s) DONE", self._NAME)
        return True


def _delete_user(_username, _mysqlcon):
    """
    Delete _username from t_users and t_addrs tables
    """
    lg.debug("> _delete_user(%s)", _username)
    try:
        sql_arr = ["DELETE from t_users WHERE username = %s",
                   "DELETE from t_addrs WHERE username = %s"]
        for sql in sql_arr:
            mysqlexec = _mysqlcon.execute(sql, _username.lower())
            if mysqlexec.rowcount <= 0:
                lg.warning("_delete_user(%s): rowcount <= 0 while executing <%s>", _username, sql % _username.lower())
    except Exception, e:
        lg.error("_delete_user(%s): error while executing <%s>: %s", _username, sql % _username.lower(), str(e))
        raise
    lg.debug("< _delete_user(%s) DONE", _username)
    return True
