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

import ctb_misc

import logging, time, praw, re

lg = logging.getLogger('cointipbot')

class CtbUser(object):
    """
    User class for cointip bot
    """

    # Basic properties
    name=None
    giftamount=None
    joindate=None
    addr={}
    banned=False

    # Objects
    prawobj=None
    ctb=None

    def __init__(self, name=None, redditobj=None, ctb=None):
        """
        Initialize CtbUser object with given parameters
        """
        lg.debug("> CtbUser::__init__(%s)", name)

        if not bool(name):
            raise Exception("CtbUser::__init__(): name must be set")
        self.name = name

        if not bool(ctb):
            raise Exception("CtbUser::__init__(): ctb must be set")
        self.ctb = ctb

        if bool(redditobj):
            self.prawobj = redditobj

        # Determine if user is banned
        if ctb.conf.reddit.banned_users:
            if ctb.conf.reddit.banned_users.method == 'subreddit':
                for u in ctb.reddit.get_banned(ctb.conf.reddit.banned_users.subreddit):
                    if self.name.lower() == u.name.lower():
                        self.banned = True
            elif ctb.conf.reddit.banned_users.method == 'list':
                for u in ctb.conf.reddit.banned_users.list:
                    if self.name.lower() == u.lower():
                        self.banned = True
            else:
                lg.warning("CtbUser::__init__(): invalid method '%s' in banned_users config" % ctb.conf.reddit.banned_users.method)

        lg.debug("< CtbUser::__init__(%s) DONE", name)

    def __str__(self):
        """
        Return string representation of self
        """
        me = "<CtbUser: name=%s, giftamnt=%s, joindate=%s, addr=%s, redditobj=%s, ctb=%s, banned=%s>"
        me = me % (self.name, self.giftamount, self.joindate, self.addr, self.prawobj, self.ctb, self.banned)
        return me

    def get_balance(self, coin=None, kind=None):
        """
        If coin is specified, return float with coin balance for user. Else, return a dict with balance of each coin for user.
        """
        lg.debug("> CtbUser::balance(%s)", self.name)

        if not bool(coin) or not bool(kind):
            raise Exception("CtbUser::balance(%s): coin or kind not set" % self.name)

        # Ask coin daemon for account balance
        lg.info("CtbUser::balance(%s): getting %s %s balance", self.name, coin, kind)
        balance = self.ctb.coins[coin].getbalance(_user=self.name, _minconf=self.ctb.conf.coins[coin].minconf[kind])

        lg.debug("< CtbUser::balance(%s) DONE", self.name)
        return float(balance)

    def get_addr(self, coin=None):
        """
        Return coin address of user
        """
        lg.debug("> CtbUser::get_addr(%s, %s)", self.name, coin)

        if hasattr(self.addr, coin):
            return self.addr[coin]

        sql = "SELECT address from t_addrs WHERE username = %s AND coin = %s"
        mysqlrow = self.ctb.db.execute(sql, (self.name.lower(), coin.lower())).fetchone()
        if mysqlrow == None:
            lg.debug("< CtbUser::get_addr(%s, %s) DONE (no)", self.name, coin)
            return None
        else:
            self.addr[coin] = mysqlrow['address']
            lg.debug("< CtbUser::get_addr(%s, %s) DONE (%s)", self.name, coin, self.addr[coin])
            return self.addr[coin]

        lg.debug("< CtbUser::get_addr(%s, %s) DONE (should never happen)", self.name, coin)
        return None

    def is_on_reddit(self):
        """
        Return true if username exists Reddit. Also set prawobj pointer while at it.
        """
        lg.debug("> CtbUser::is_on_reddit(%s)", self.name)

        # Return true if prawobj is already set
        if bool(self.prawobj):
            lg.debug("< CtbUser::is_on_reddit(%s) DONE (yes)", self.name)
            return True

        try:
            self.prawobj = ctb_misc.praw_call(self.ctb.reddit.get_redditor, self.name)
            if self.prawobj:
                return True
            else:
                return False

        except Exception as e:
            lg.debug("< CtbUser::is_on_reddit(%s) DONE (no)", self.name)
            return False

        lg.warning("< CtbUser::is_on_reddit(%s): returning None (shouldn't happen)", self.name)
        return None

    def is_registered(self):
        """
        Return true if user is registered with CointipBot
        """
        lg.debug("> CtbUser::is_registered(%s)", self.name)

        try:
            # First, check t_users table
            sql = "SELECT * FROM t_users WHERE username = %s"
            mysqlrow = self.ctb.db.execute(sql, (self.name.lower())).fetchone()

            if mysqlrow == None:
                lg.debug("< CtbUser::is_registered(%s) DONE (no)", self.name)
                return False

            else:
                # Next, check t_addrs table for whether  user has correct number of coin addresses
                sql_coins = "SELECT COUNT(*) AS count FROM t_addrs WHERE username = %s"
                mysqlrow_coins = self.ctb.db.execute(sql_coins, (self.name.lower())).fetchone()

                if int(mysqlrow_coins['count']) != len(self.ctb.coins):
                    if int(mysqlrow_coins['count']) == 0:
                        # Bot probably crashed during user registration process
                        # Delete user
                        lg.warning("CtbUser::is_registered(%s): deleting user, incomplete registration", self.name)
                        sql_delete = "DELETE FROM t_users WHERE username = %s"
                        mysql_res = self.ctb.db.execute(sql_delete, (self.name.lower()))
                        # User is not registered
                        return False
                    else:
                        raise Exception("CtbUser::is_registered(%s): user has %s coins but %s active" % (self.name, mysqlrow_coins['count'], len(self.ctb.coins)))

                # Set some properties
                self.giftamount = mysqlrow['giftamount']

                # Done
                lg.debug("< CtbUser::is_registered(%s) DONE (yes)", self.name)
                return True

        except Exception, e:
            lg.error("CtbUser::is_registered(%s): error while executing <%s>: %s", self.name, sql % self.name.lower(), e)
            raise

        lg.warning("< CtbUser::is_registered(%s): returning None (shouldn't happen)", self.name)
        return None

    def tell(self, subj=None, msg=None, msgobj=None):
        """
        Send a Reddit message to user
        """
        lg.debug("> CtbUser::tell(%s)", self.name)

        if not bool(subj) or not bool(msg):
            raise Exception("CtbUser::tell(%s): subj or msg not set", self.name)

        if not self.is_on_reddit():
            raise Exception("CtbUser::tell(%s): not a Reddit user", self.name)

        if bool(msgobj):
            lg.debug("CtbUser::tell(%s): replying to message", msgobj.id)
            ctb_misc.praw_call(msgobj.reply, msg)
        else:
            lg.debug("CtbUser::tell(%s): sending message", self.name)
            ctb_misc.praw_call(self.prawobj.send_message, subj, msg)

        lg.debug("< CtbUser::tell(%s) DONE", self.name)
        return True

    def register(self):
        """
        Add user to database and generate coin addresses
        """
        lg.debug("> CtbUser::register(%s)", self.name)

        # Add user to database
        try:
            sql_adduser = "INSERT INTO t_users (username) VALUES (%s)"
            mysqlexec = self.ctb.db.execute(sql_adduser, (self.name.lower()))
            if mysqlexec.rowcount <= 0:
                raise Exception("CtbUser::register(%s): rowcount <= 0 while executing <%s>" % ( self.name, sql_adduser % (self.name.lower()) ))
        except Exception, e:
            lg.error("CtbUser::register(%s): exception while executing <%s>: %s", self.name, sql_adduser % (self.name.lower()), e)
            raise

        # Get new coin addresses
        new_addrs = {}
        for c in self.ctb.coins:
            new_addrs[c] = self.ctb.coins[c].getnewaddr(_user=self.name.lower())
            lg.info("CtbUser::register(%s): got %s address %s", self.name, c, new_addrs[c])

        # Add coin addresses to database
        for c in new_addrs:
            try:
                sql_addr = "REPLACE INTO t_addrs (username, coin, address) VALUES (%s, %s, %s)"
                mysqlexec = self.ctb.db.execute(sql_addr, (self.name.lower(), c, new_addrs[c]))
                if mysqlexec.rowcount <= 0:
                    # Undo change to database
                    delete_user(_username=self.name.lower(), _db=self.ctb.db)
                    raise Exception("CtbUser::register(%s): rowcount <= 0 while executing <%s>" % (self.name, sql_addr % (self.name.lower(), c, new_addrs[c])))

            except Exception, e:
                # Undo change to database
                delete_user(_username=self.name.lower(), _db=self.ctb.db)
                raise

        lg.debug("< CtbUser::register(%s) DONE", self.name)
        return True

    def get_redeem_amount(self, coin=None, fiat=None):
        """
        Return karma redeem amount for a given coin
        """
        lg.debug("> CtbUser::get_redeem_amount(%s)", coin)

        if not coin or not self.ctb.coins.has_key(coin):
            raise Exception("CtbUser::get_redeem_amount(%s): invalid coin" % coin)
        if not fiat or not self.ctb.conf.fiat.has_key(fiat):
            raise Exception("CtbUser::get_redeem_amount(%s): invalid fiat" % fiat)

        # Check if we have coin's fiat value
        coin_value = self.ctb.coin_value(coin, fiat)
        if not coin_value or not coin_value > 0.0:
            lg.warning("CtbUser::get_redeem_amount(%s): coin_value not available", coin)
            return (None, None)

        # First, determine fiat value due to link karma
        link_mul = self.ctb.conf.reddit.redeem.multiplier.link
        if type(link_mul) in [str, unicode]:
            link_mul = eval(link_mul)
        if not type(link_mul) == float:
            raise Exception("CtbUser::get_redeem_amount(): type of link_mul is not float")
        link_val = float(self.prawobj.link_karma) * link_mul

        # Second, determine fiat value due to comment karma
        comm_mul = self.ctb.conf.reddit.redeem.multiplier.comment
        if type(comm_mul) in [str, unicode]:
            comm_mul = eval(comm_mul)
        if not type(comm_mul) == float:
            raise Exception("CtbUser::get_redeem_amount(): type of comm_mul is not float")
        comm_val = float(self.prawobj.comment_karma) * comm_mul

        # Third, determine base fiat value from config
        base_val = self.ctb.conf.reddit.redeem.base
        if type(base_val) in [str, unicode]:
            base_val = eval(base_val)
        if not type(base_val) == float:
            raise Exception("CtbUser::get_redeem_amount(): type of base_val is not float")

        # Sum link_val, comm_val, and base_val to get total fiat
        total_fiat = link_val + comm_val + base_val

        # Check if above maximum
        if total_fiat > self.ctb.conf.reddit.redeem.maximum:
            total_fiat = self.ctb.conf.reddit.redeem.maximum

        # Determine total coin value using exchange rate
        total_coin = total_fiat / coin_value

        lg.debug("< CtbUser::get_redeem_amount(%s) DONE", coin)
        return (total_coin, total_fiat)


def delete_user(_username=None, _db=None):
    """
    Delete _username from t_users and t_addrs tables
    """
    lg.debug("> delete_user(%s)", _username)

    try:
        sql_arr = ["DELETE FROM t_users WHERE username = %s",
                   "DELETE FROM t_addrs WHERE username = %s"]
        for sql in sql_arr:
            mysqlexec = _db.execute(sql, _username.lower())
            if mysqlexec.rowcount <= 0:
                lg.warning("delete_user(%s): rowcount <= 0 while executing <%s>", _username, sql % _username.lower())

    except Exception, e:
        lg.error("delete_user(%s): error while executing <%s>: %s", _username, sql % _username.lower(), e)
        return False

    lg.debug("< delete_user(%s) DONE", _username)
    return True
