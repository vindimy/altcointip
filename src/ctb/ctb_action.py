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

import ctb_user, ctb_misc, ctb_stats

import logging, praw, re, time
from random import randint

lg = logging.getLogger('cointipbot')

class CtbActionExc(Exception):
    pass

class CtbAction(object):
    """
    Action class for cointip bot
    """

    type=None           # 'accept', 'decline', 'history', 'info', 'register', 'givetip', 'withdraw', 'redeem', 'rates'
    state=None          # 'completed', 'pending', 'failed', 'declined'
    txid=None           # cryptocoin transaction id, a 64-char string, if applicable

    u_from=None         # CtbUser instance
    u_to=None           # CtbUser instance, if applicable
    addr_to=None        # destination cryptocoin address of 'givetip' and 'withdraw' actions, if applicable

    coin=None           # coin for this action (for example, 'ltc')
    fiat=None           # fiat for this action (for example, 'usd'), if applicable
    coinval=None        # coin value of 'givetip' and 'withdraw' actions
    fiatval=None        # fiat value of the 'givetip' or 'withdraw' action
    keyword=None        # keyword that's used instead of coinval/fiatval

    subreddit=None      # subreddit that originated the action, if applicable

    msg=None            # Reddit object pointing to originating message/comment
    msg_id=None         #
    ctb=None            # CointipBot instance


    def __init__(self, atype=None, msg=None, msg_id=None, from_user=None, to_user=None, to_addr=None, coin=None, fiat=None, coin_val=None, fiat_val=None, keyword=None, subr=None, ctb=None):
        """
        Initialize CtbAction object with given parameters and run basic checks
        """
        lg.debug("> CtbAction::__init__(%s)", vars())

        self.type = atype

        self.coin = coin.lower() if coin else None
        self.fiat = fiat.lower() if fiat else None
        self.coinval = coin_val
        self.fiatval = fiat_val
        self.keyword = keyword.lower() if keyword else None

        self.msg = msg
        self.ctb = ctb

        self.msg_id = self.msg.id if self.msg else msg_id

        self.addr_to = to_addr
        self.u_to = ctb_user.CtbUser(name=to_user, ctb=ctb) if to_user else None
        self.u_from = ctb_user.CtbUser(name=msg.author.name, redditobj=msg.author, ctb=ctb) if (msg and hasattr(msg, 'author') and msg.author) else ctb_user.CtbUser(name=from_user, ctb=ctb)
        self.subreddit = subr

        # Do some checks
        if not self.type:
            raise Exception("CtbAction::__init__(type=?): type not set")
        if not self.ctb:
            raise Exception("CtbAction::__init__(type=%s): no reference to CointipBot", self.type)
        #if not self.msg:
        #    raise Exception("CtbAction::__init__(type=%s): no reference to Reddit message/comment", self.type)
        if self.type in ['givetip', 'withdraw']:
            if not (bool(self.u_to) ^ bool(self.addr_to)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): u_to xor addr_to must be set" % (self.type, self.u_from.name))
            if not (bool(self.coin) or bool(self.fiat) or bool(self.keyword)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): coin or fiat or keyword must be set" % (self.type, self.u_from.name))
            if not (bool(self.coinval) or bool(self.fiatval) or bool(self.keyword)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): coinval or fiatval or keyword must be set" % (self.type, self.u_from.name))
            if (not self.coinval or not float(self.coinval) > 0.0) and (not self.fiatval or not float(self.fiatval) > 0.0) and (not self.keyword):
                raise CtbActionExc("CtbAction::__init__(type=%s, from_user=%s, to_user=%s): no (coinval or fiatval or keyword) given" % (self.type, self.u_from, self.u_to))

        # Convert coinval and fiat to float, if necesary
        if self.coinval and type(self.coinval) == unicode and self.coinval.replace('.', '').isnumeric():
            self.coinval = float(self.coinval)
        if self.fiatval and type(self.fiatval) == unicode and self.fiatval.replace('.', '').isnumeric():
            self.fiatval = float(self.fiatval)

        lg.debug("CtbAction::__init__(): %s", self)

        # Determine coinval or fiatval, if keyword is given instead of numeric value
        if self.type in ['givetip', 'withdraw']:

            if self.keyword:
                if not self.ctb.conf.keywords[self.keyword].for_coin and not self.fiat:
                    # If fiat-only, set fiat to 'usd' if missing
                    self.fiat = 'usd'
                if not self.ctb.conf.keywords[self.keyword].for_coin and not self.fiatval:
                    # If fiat-only, set fiatval as coinval, and clear coinval
                    self.fiatval = self.coinval
                    self.coinval = None
                if not self.coin and not self.fiat:
                    # If both coin and fiat missing, set fiat to 'usd'
                    self.fiat = 'usd'

            if self.keyword and self.fiat and not self.coin and not self.ctb.conf.keywords[self.keyword].for_fiat:
                # If keyword is coin-only but only fiat is set, give up
                raise CtbActionExc("CtbAction::__init__(type=%s): keyword is coin-only, but only fiat is set")

            if self.keyword and self.fiat and not ( type(self.fiatval) in [float, int] and self.fiatval > 0.0 ):
                # Determine fiat value
                lg.debug("CtbAction::__init__(): determining fiat value given '%s'", self.keyword)
                val = self.ctb.conf.keywords[self.keyword].value
                if type(val) == float:
                    self.fiatval = val
                elif type(val) == str:
                    lg.debug("CtbAction::__init__(): evaluating '%s'", val)
                    self.fiatval = eval(val)
                    if not type(self.fiatval) == float:
                        raise CtbActionExc("CtbAction::__init__(atype=%s, from_user=%s): couldn't determine fiatval from keyword '%s' (not float)" % (self.type, self.u_from.name, self.keyword))
                else:
                    raise CtbActionExc("CtbAction::__init__(atype=%s, from_user=%s): couldn't determine fiatval from keyword '%s' (not float or str)" % (self.type, self.u_from.name, self.keyword))

            elif self.keyword and self.coin and not ( type(self.coinval) in [float, int] and self.coinval > 0.0 ):
                # Determine coin value
                lg.debug("CtbAction::__init__(): determining coin value given '%s'", self.keyword)
                val = self.ctb.conf.keywords[self.keyword].value
                if type(val) == float:
                    self.coinval = val
                elif type(val) == str:
                    lg.debug("CtbAction::__init__(): evaluating '%s'", val)
                    self.coinval = eval(val)
                    if not type(self.coinval) == float:
                        raise CtbActionExc("CtbAction::__init__(atype=%s, from_user=%s): couldn't determine coinval from keyword '%s' (not float)" % (self.type, self.u_from.name, self.keyword))
                else:
                    raise CtbActionExc("CtbAction::__init__(atype=%s, from_user=%s): couldn't determine coinval from keyword '%s' (not float or str)" % (self.type, self.u_from.name, self.keyword))

            # By this point we should have a proper coinval or fiatval
            if not type(self.coinval) in [float, int] and not type(self.fiatval) in [float, int]:
                raise CtbActionExc("CtbAction::__init__(atype=%s, from_user=%s): coinval or fiatval isn't determined" % (self.type, self.u_from.name))

        # Determine coin, if given only fiat, using exchange rates
        if self.type in ['givetip']:
            if self.fiat and not self.coin:
                lg.debug("CtbAction::__init__(atype=%s, from_user=%s): determining coin..." % (self.type, self.u_from.name))
                if not self.u_from.is_registered():
                    # Can't proceed, abort
                    raise CtbActionExc("CtbAction::__init__(): can't determine coin for un-registered user %s", self.u_from.name)
                # Choose a coin based on from_user's available balance (pick first one that can satisfy the amount)
                cc = self.ctb.conf.coins
                for c in sorted(self.ctb.coins):
                    lg.debug("CtbAction::__init__(atype=%s, from_user=%s): considering %s" % (self.type, self.u_from.name, c))
                    # First, check if we have a ticker value for this coin and fiat
                    if not self.ctb.coin_value(cc[c].unit, self.fiat) > 0.0:
                        continue
                    # Compare available and needed coin balances
                    coin_balance_avail = self.u_from.get_balance(coin=cc[c].unit, kind='givetip')
                    coin_balance_need = self.fiatval / self.ctb.coin_value(cc[c].unit, self.fiat)
                    if coin_balance_avail > coin_balance_need or abs(coin_balance_avail - coin_balance_need) < 0.000001:
                        # Found coin with enough balance
                        self.coin = cc[c].unit
                        break
            if not self.coin:
                # Couldn't deteremine coin, abort
                raise CtbActionExc("CtbAction::__init__(): can't determine coin for user %s" % self.u_from.name)

        # Calculate fiat or coin value with exchange rates
        if self.type in ['givetip', 'withdraw']:
            if not self.fiat:
                # Set fiat to 'usd' if not specified
                self.fiat = 'usd'
            if not self.fiatval:
                # Determine fiat value
                self.fiatval = self.coinval * self.ctb.coin_value(self.ctb.conf.coins[self.coin].unit, self.fiat)
            elif not self.coinval:
                # Determine coin value
                self.coinval = self.fiatval / self.ctb.coin_value(self.ctb.conf.coins[self.coin].unit, self.fiat)

        # Final check to make sure coin value is determined
        if self.type in ['givetip', 'withdraw']:
            if not self.coinval or not type(self.coinval) in [float, int]:
                raise CtbActionExc("CtbAction::__init__(): couldn't determine coin value, giving up. CtbAction: <%s>", self)

        lg.debug("< CtbAction::__init__(atype=%s, from_user=%s) DONE", self.type, self.u_from.name)

    def __str__(self):
        """""
        Return string representation of self
        """
        me = "<CtbAction: type=%s, msg.body=%s, from_user=%s, to_user=%s, to_addr=%s, coin=%s, fiat=%s, coin_val=%s, fiat_val=%s, subreddit=%s>"
        me = me % (self.type, self.msg.body if self.msg else '', self.u_from, self.u_to, self.addr_to, self.coin, self.fiat, self.coinval, self.fiatval, self.subreddit)
        return me

    def update(self, state=None):
        """
        Update action state in database
        """
        lg.debug("> CtbAction::update(%s)", state)

        if not state:
            raise Exception("CtbAction::update(): state is null")
        if not self.type or not self.msg_id:
            raise Exception("CtbAction::update(): type or msg_id missing")

        conn = self.ctb.db
        sql = "UPDATE t_action SET state=%s WHERE type=%s AND msg_id=%s"

        try:
            mysqlexec = conn.execute(sql, (state, self.type, self.msg_id))
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception as e:
            lg.error("CtbAction::update(%s): error executing query <%s>: %s", state, sql % (state, self.type, self.msg_id))
            raise

        lg.debug("< CtbAction::update() DONE")
        return True

    def save(self, state=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save(%s)", state)

        # Make sure no negative values exist
        if self.coinval < 0.0:
            self.coinval = 0.0
        if self.fiatval < 0.0:
            self.fiatval = 0.0

        conn = self.ctb.db
        sql = "INSERT INTO t_action (type, state, created_utc, from_user, to_user, to_addr, coin_val, fiat_val, txid, coin, fiat, subreddit, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(sql,
                    (self.type,
                     state,
                     self.msg.created_utc,
                     self.u_from.name.lower(),
                     self.u_to.name.lower() if self.u_to else None,
                     self.addr_to,
                     self.coinval,
                     self.fiatval,
                     self.txid,
                     self.coin,
                     self.fiat,
                     self.subreddit,
                     self.msg.id,
                     self.msg.permalink if hasattr(self.msg, 'permalink') else None))
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception as e:
            lg.error("CtbAction::save(%s): error executing query <%s>: %s", state, sql % (
                self.type,
                state,
                self.msg.created_utc,
                self.u_from.name.lower(),
                self.u_to.name.lower() if self.u_to else None,
                self.addr_to,
                self.coinval,
                self.fiatval,
                self.txid,
                self.coin,
                self.fiat,
                self.subreddit,
                self.msg.id,
                self.msg.permalink if hasattr(self.msg, 'permalink') else None), e)
            raise

        lg.debug("< CtbAction::save() DONE")
        return True

    def do(self):
        """
        Call appropriate function depending on action type
        """
        lg.debug("> CtbAction::do()")

        if not self.ctb.conf.regex.actions[self.type].enabled:
	        msg = self.ctb.jenv.get_template('command-disabled.tpl').render(a=self, ctb=self.ctb)
	        lg.info("CtbAction::do(): action %s is disabled", self.type)
	        ctb_misc.praw_call(self.msg.reply, msg)
	        return False

        if self.type == 'accept':
            return self.accept()

        if self.type == 'decline':
            return self.decline()

        if self.type == 'givetip':
            result = self.givetip()
            ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_from.name)
            if self.u_to:
                ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_to.name)
            return result

        if self.type == 'history':
            return self.history()

        if self.type == 'info':
            return self.info()

        if self.type == 'register':
            return self.register()

        if self.type == 'withdraw':
            return self.givetip()

        if self.type == 'redeem':
            return self.redeem()

        if self.type == 'rates':
            return self.rates()

        lg.debug("< CtbAction::do() DONE")
        return None

    def history(self):
        """
        Provide user with transaction history
        """
        lg.debug("> CtbAction::history()")

        # Generate history array
        history = []
        sql_history = self.ctb.conf.db.sql.userhistory.sql
        limit = int(self.ctb.conf.db.sql.userhistory.limit)

        mysqlexec = self.ctb.db.execute(sql_history, (self.u_from.name.lower(), self.u_from.name.lower(), limit))
        for m in mysqlexec:
            history_entry = []
            for k in mysqlexec.keys():
                history_entry.append(ctb_stats.format_value(m, k, self.u_from.name.lower(), self.ctb, compact=True))
            history.append(history_entry)

        # Send message to user
        msg = self.ctb.jenv.get_template('history.tpl').render(history=history, keys=mysqlexec.keys(), limit=limit, a=self, ctb=self.ctb)
        lg.debug("CtbAction::history(): %s", msg)
        ctb_misc.praw_call(self.msg.reply, msg)

        # Save as completed
        self.save('completed')

        lg.debug("< CtbAction::history() DONE")
        return True

    def accept(self):
        """
        Accept pending tip
        """
        lg.debug("> CtbAction::accept()")

        # Register as new user if necessary
        if not self.u_from.is_registered():
            if not self.u_from.register():
                lg.warning("CtbAction::accept(): self.u_from.register() failed")
                self.save('failed')
                return False

        # Get pending actions
        actions = get_actions(atype='givetip', to_user=self.u_from.name, state='pending', ctb=self.ctb)
        if actions:

            # Accept each action
            for a in actions:
                a.givetip(is_pending=True)
                # Update u_from (tip action) stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_from.name)
            # Update u_from (accept action) stats
            ctb_stats.update_user_stats(ctb=a.ctb, username=self.u_from.name)
            # Save this action
            self.save('completed')

        else:

            # No pending actions found, reply with error message
            msg = self.ctb.jenv.get_template('no-pending-tips.tpl').render(user_from=self.u_from.name, a=self, ctb=self.ctb)
            lg.debug("CtbAction::accept(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            # Save this action
            self.save('failed')

        lg.debug("< CtbAction::accept() DONE")
        return True

    def decline(self):
        """
        Decline pending tips
        """
        lg.debug("> CtbAction::decline()")

        actions = get_actions(atype='givetip', to_user=self.u_from.name, state='pending', ctb=self.ctb)
        if actions:
            for a in actions:
                # Move coins back into a.u_from account
                lg.info("CtbAction::decline(): moving %.9f %s from %s to %s", a.coinval, a.coin.upper(), self.ctb.conf.reddit.auth.user, a.u_from.name)
                if not self.ctb.coins[a.coin].sendtouser(_userfrom=self.ctb.conf.reddit.auth.user, _userto=a.u_from.name, _amount=a.coinval):
                    raise Exception("CtbAction::decline(): failed to sendtouser()")

                # Update transaction as declined
                a.update('declined')

                # Update u_from (tip action) stats
                ctb_stats.update_user_stats(ctb=a.ctb, username=a.u_from.name)

                # Respond to tip comment
                msg = self.ctb.jenv.get_template('confirmation.tpl').render(title='Declined', a=a, ctb=a.ctb, source_link=a.msg.permalink if a.msg else None)
                lg.debug("CtbAction::decline(): " + msg)
                if self.ctb.conf.reddit.messages.declined:
                    if not ctb_misc.praw_call(a.msg.reply, msg):
                        a.u_from.tell(subj="+tip declined", msg=msg)
                else:
                    a.u_from.tell(subj="+tip declined", msg=msg)

            # Update u_from (decline action) stats
            ctb_stats.update_user_stats(ctb=a.ctb, username=self.u_from.name)

            # Notify self.u_from
            msg = self.ctb.jenv.get_template('pending-tips-declined.tpl').render(user_from=self.u_from.name, ctb=self.ctb)
            lg.debug("CtbAction::decline(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)

            # Save action to database
            self.save('completed')

        else:

            msg = self.ctb.jenv.get_template('no-pending-tips.tpl').render(user_from=self.u_from.name, ctb=self.ctb)
            lg.debug("CtbAction::decline(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)

            # Save action to database
            self.save('failed')

        lg.debug("< CtbAction::decline() DONE")
        return True

    def expire(self):
        """
        Expire a pending tip
        """
        lg.debug("> CtbAction::expire()")

        # Move coins back into self.u_from account
        lg.info("CtbAction::expire(): moving %.9f %s from %s to %s", self.coinval, self.coin.upper(), self.ctb.conf.reddit.auth.user, self.u_from.name)
        if not self.ctb.coins[self.coin].sendtouser(_userfrom=self.ctb.conf.reddit.auth.user, _userto=self.u_from.name, _amount=self.coinval):
            raise Exception("CtbAction::expire(): sendtouser() failed")

        # Update transaction as expired
        self.update('expired')

        # Update user stats
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_from.name)
        ctb_stats.update_user_stats(ctb=self.ctb, username=self.u_to.name)

        # Respond to tip comment
        msg = self.ctb.jenv.get_template('confirmation.tpl').render(title='Expired', a=self, ctb=self.ctb, source_link=self.msg.permalink if self.msg else None)
        lg.debug("CtbAction::expire(): " + msg)
        if self.ctb.conf.reddit.messages.expired:
            if not ctb_misc.praw_call(self.msg.reply, msg):
                self.u_from.tell(subj="+tip expired", msg=msg)
        else:
            self.u_from.tell(subj="+tip expired", msg=msg)

        lg.debug("< CtbAction::expire() DONE")
        return True

    def validate(self, is_pending=False):
        """
        Validate an action
        """
        lg.debug("> CtbAction::validate()")

        if self.type in ['givetip', 'withdraw']:
            # Check if u_from has registered
            if not self.u_from.is_registered():
                msg = self.ctb.jenv.get_template('not-registered.tpl').render(a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save('failed') if not is_pending else self.update('failed')
                return False

            if self.u_to and not self.u_to.is_on_reddit():
                msg = self.ctb.jenv.get_template('not-on-reddit.tpl').render(a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save('failed') if not is_pending else self.update('failed')
                return False

            # Verify that coin type is set
            if not self.coin:
                msg = self.ctb.jenv.get_template('no-coin-balances.tpl').render(a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): %s", msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save('failed') if not is_pending else self.update('failed')
                return False

            # Verify that u_from has coin address
            if not self.u_from.get_addr(coin=self.coin):
                lg.error("CtbAction::validate(): user %s doesn't have %s address", self.u_from.name, self.coin.upper())
                self.save('failed') if not is_pending else self.update('failed')
                raise Exception

            # Verify minimum transaction size
            txkind = 'givetip' if self.u_to else 'withdraw'
            if self.coinval < self.ctb.conf.coins[self.coin].txmin[txkind]:
                msg = self.ctb.jenv.get_template('tip-below-minimum.tpl').render(min_value=self.ctb.conf.coins[self.coin].txmin[txkind], a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): " + msg)
                self.u_from.tell(subj="+tip failed", msg=msg)
                self.save('failed') if not is_pending else self.update('failed')
                return False

            # Verify balance (unless it's a pending transaction being processed, in which case coins have been already moved to pending acct)
            if self.u_to and not is_pending:
                # Tip to user (requires less confirmations)
                balance_avail = self.u_from.get_balance(coin=self.coin, kind='givetip')
                if not ( balance_avail > self.coinval or abs(balance_avail - self.coinval) < 0.000001 ):
                    msg = self.ctb.jenv.get_template('tip-low-balance.tpl').render(balance=balance_avail, action_name='tip', a=self, ctb=self.ctb)
                    lg.debug("CtbAction::validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save('failed') if not is_pending else self.update('failed')
                    return False
            elif self.addr_to:
                # Tip/withdrawal to address (requires more confirmations)
                balance_avail = self.u_from.get_balance(coin=self.coin, kind='withdraw')
                balance_need = self.coinval
                # Add mandatory network transaction fee
                balance_need += self.ctb.conf.coins[self.coin].txfee
                if not ( balance_avail > balance_need or abs(balance_avail - balance_need) < 0.000001 ):
                    msg = self.ctb.jenv.get_template('tip-low-balance.tpl').render(balance=balance_avail, action_name='withdraw', a=self, ctb=self.ctb)
                    lg.debug("CtbAction::validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save('failed') if not is_pending else self.update('failed')
                    return False

            # Check if u_to has any pending coin tips from u_from
            if self.u_to and not is_pending:
                if check_action(atype='givetip', state='pending', to_user=self.u_to.name, from_user=self.u_from.name, coin=self.coin, ctb=self.ctb):
                    # Send notice to u_from
                    msg = self.ctb.jenv.get_template('tip-already-pending.tpl').render(a=self, ctb=self.ctb)
                    lg.debug("CtbAction::validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save('failed') if not is_pending else self.update('failed')
                    return False

            # Check if u_to has registered, if applicable
            if self.u_to and not self.u_to.is_registered():
                # u_to not registered:
                # - move tip into pending account
                # - save action as 'pending'
                # - notify u_to to accept tip

                # Move coins into pending account
                minconf = self.ctb.coins[self.coin].conf.minconf.givetip
                lg.info("CtbAction::validate(): moving %.9f %s from %s to %s (minconf=%s)...", self.coinval, self.coin.upper(), self.u_from.name, self.ctb.conf.reddit.auth.user, minconf)
                if not self.ctb.coins[self.coin].sendtouser(_userfrom=self.u_from.name, _userto=self.ctb.conf.reddit.auth.user, _amount=self.coinval, _minconf=minconf):
                    raise Exception("CtbAction::validate(): sendtouser() failed")

                # Save action as pending
                self.save('pending')

                # Respond to tip comment
                msg = self.ctb.jenv.get_template('confirmation.tpl').render(title='Verified', a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): " + msg)
                if self.ctb.conf.reddit.messages.verified:
                    if not ctb_misc.praw_call(self.msg.reply, msg):
                        self.u_from.tell(subj="+tip pending +accept", msg=msg)
                else:
                    self.u_from.tell(subj="+tip pending +accept", msg=msg)

                # Send notice to u_to
                msg = self.ctb.jenv.get_template('tip-incoming.tpl').render(a=self, ctb=self.ctb)
                lg.debug("CtbAction::validate(): %s", msg)
                self.u_to.tell(subj="+tip pending", msg=msg)

                # Action saved as 'pending', return false to avoid processing it further
                return False

            # Validate addr_to, if applicable
            if self.addr_to:
                if not self.ctb.coins[self.coin].validateaddr(_addr=self.addr_to):
                    msg = self.ctb.jenv.get_template('address-invalid.tpl').render(a=self, ctb=self.ctb)
                    lg.debug("CtbAction::validate(): " + msg)
                    self.u_from.tell(subj="+tip failed", msg=msg)
                    self.save('failed') if not is_pending else self.update('failed')
                    return False

        # Action is valid
        lg.debug("< CtbAction::validate() DONE")
        return True

    def givetip(self, is_pending=False):
        """
        Initiate tip
        """
        lg.debug("> CtbAction::givetip()")

        # Check if action has been processed
        if check_action(atype=self.type, msg_id=self.msg_id, ctb=self.ctb, is_pending=is_pending):
            # Found action in database, returning
            lg.warning("CtbAction::givetipt(): duplicate action %s (msg.id %s), ignoring", self.type, self.msg.id)
            return False

        # Validate action
        if not self.validate(is_pending=is_pending):
            # Couldn't validate action, returning
            return False

        if self.u_to:
            # Process tip to user

            res = False
            if is_pending:
                # This is accept() of pending transaction, so move coins from pending account to receiver
                lg.info("CtbAction::givetip(): moving %.9f %s from %s to %s...", self.coinval, self.coin.upper(), self.ctb.conf.reddit.auth.user, self.u_to.name)
                res = self.ctb.coins[self.coin].sendtouser(_userfrom=self.ctb.conf.reddit.auth.user, _userto=self.u_to.name, _amount=self.coinval)
            else:
                # This is not accept() of pending transaction, so move coins from tipper to receiver
                lg.info("CtbAction::givetip(): moving %.9f %s from %s to %s...", self.coinval, self.coin.upper(), self.u_from.name, self.u_to.name)
                res = self.ctb.coins[self.coin].sendtouser(_userfrom=self.u_from.name, _userto=self.u_to.name, _amount=self.coinval)

            if not res:
                # Tx failed
                # Save/update action as failed
                self.save('failed') if not is_pending else self.update('failed')

                # Send notice to u_from
                msg = self.ctb.jenv.get_template('tip-went-wrong.tpl').render(a=self, ctb=self.ctb)
                self.u_from.tell(subj="+tip failed", msg=msg)

                raise Exception("CtbAction::givetip(): sendtouser() failed")

            # Transaction succeeded
            self.save('completed') if not is_pending else self.update('completed')

            # Send confirmation to u_to
            msg = self.ctb.jenv.get_template('tip-received.tpl').render(a=self, ctb=self.ctb)
            lg.debug("CtbAction::givetip(): " + msg)
            self.u_to.tell(subj="+tip received", msg=msg)

            # This is not accept() of pending transaction, so post verification comment
            if not is_pending:
                msg = self.ctb.jenv.get_template('confirmation.tpl').render(title='Verified', a=self, ctb=self.ctb)
                lg.debug("CtbAction::givetip(): " + msg)
                if self.ctb.conf.reddit.messages.verified:
                    if not ctb_misc.praw_call(self.msg.reply, msg):
                        self.u_from.tell(subj="+tip succeeded", msg=msg)
                else:
                    self.u_from.tell(subj="+tip succeeded", msg=msg)

            lg.debug("< CtbAction::givetip() DONE")
            return True

        elif self.addr_to:
            # Process tip to address
            try:
                lg.info("CtbAction::givetip(): sending %.9f %s to %s...", self.coinval, self.coin, self.addr_to)
                self.txid = self.ctb.coins[self.coin].sendtoaddr(_userfrom=self.u_from.name, _addrto=self.addr_to, _amount=self.coinval)

            except Exception as e:

                # Transaction failed
                self.save('failed') if not is_pending else self.update('failed')
                lg.error("CtbAction::givetip(): sendtoaddr() failed")

                # Send notice to u_from
                msg = self.ctb.jenv.get_template('tip-went-wrong.tpl').render(a=self, ctb=self.ctb)
                self.u_from.tell(subj="+tip failed", msg=msg)

                raise

            # Transaction succeeded
            self.save('completed') if not is_pending else self.update('completed')

            # Post verification comment
            msg = self.ctb.jenv.get_template('confirmation.tpl').render(title='Verified', a=self, ctb=self.ctb)
            lg.debug("CtbAction::givetip(): " + msg)
            if self.ctb.conf.reddit.messages.verified:
                if not ctb_misc.praw_call(self.msg.reply, msg):
                    self.u_from.tell(subj="+tip succeeded", msg=msg)
            else:
                self.u_from.tell(subj="+tip succeeded", msg=msg)

            lg.debug("< CtbAction::givetip() DONE")
            return True

        lg.debug("< CtbAction::givetip() DONE")
        return None

    def info(self):
        """
        Send user info about account
        """
        lg.debug("> CtbAction::info()")

        # Check if user exists
        if not self.u_from.is_registered():
            msg = self.ctb.jenv.get_template('not-registered.tpl').render(a=self, ctb=self.ctb)
            self.u_from.tell(subj="+info failed", msg=msg)
            return False

        # Info array to pass to template
        info = []

        # Get coin balances
        for c in sorted(self.ctb.coins):
            coininfo = ctb_misc.DotDict({})
            coininfo.coin = c
            try:
                # Get tip balance
                coininfo.balance = self.ctb.coins[c].getbalance(_user=self.u_from.name, _minconf=self.ctb.conf.coins[c].minconf.givetip)
                info.append(coininfo)
            except Exception as e:
                lg.error("CtbAction::info(%s): error retrieving %s coininfo: %s", self.u_from.name, c, e)
                raise

        # Get fiat balances
        fiat_total = 0.0
        for i in info:
            i.fiat_symbol = self.ctb.conf.fiat.usd.symbol
            if self.ctb.coin_value(self.ctb.conf.coins[i.coin].unit, 'usd') > 0.0:
                i.fiat_balance = i.balance * self.ctb.coin_value(self.ctb.conf.coins[i.coin].unit, 'usd')
                fiat_total += i.fiat_balance

        # Get coin addresses from MySQL
        for i in info:
            sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (self.u_from.name.lower(), i.coin)
            mysqlrow = self.ctb.db.execute(sql).fetchone()
            if not mysqlrow:
                raise Exception("CtbAction::info(%s): no result from <%s>" % (self.u_from.name, sql))
            i.address = mysqlrow['address']

        # Format and send message
        msg = self.ctb.jenv.get_template('info.tpl').render(info=info, fiat_symbol=self.ctb.conf.fiat.usd.symbol, fiat_total=fiat_total, a=self, ctb=self.ctb)
        ctb_misc.praw_call(self.msg.reply, msg)

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::info() DONE")
        return True

    def register(self):
        """
        Register a new user
        """
        lg.debug("> CtbAction::register()")

        # If user exists, do nothing
        if self.u_from.is_registered():
            lg.debug("CtbAction::register(%s): user already exists", self.u_from.name)
            msg = self.ctb.jenv.get_template('already-registered.tpl').render(a=self, ctb=self.ctb)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        result = self.u_from.register()

        # Save action to database
        if result:
            self.save('completed')
        else:
            self.save('failed')

        # Send welcome message to user
        if result:
            msg = self.ctb.jenv.get_template('welcome.tpl').render(a=self, ctb=self.ctb)
            ctb_misc.praw_call(self.msg.reply, msg)

        lg.debug("< CtbAction::register() DONE")
        return result

    def redeem(self):
        """
        Redeem karma for coins
        """
        lg.debug("> CtbAction::redeem()")

        # Check if user is registered
        if not self.u_from.is_registered():
            msg = self.ctb.jenv.get_template('not-registered.tpl').render(a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        # Check if this user has redeemed karma in the past
        has_redeemed = False
        if self.ctb.conf.reddit.redeem.multicoin:
            # Check if self.coin has been redeemed
            has_redeemed = check_action(atype='redeem', from_user=self.u_from.name, state='completed', coin=self.coin, ctb=self.ctb)
        else:
            # Check if any coin has been redeemed
            has_redeemed = check_action(atype='redeem', from_user=self.u_from.name, state='completed', ctb=self.ctb)
        if has_redeemed:
            msg = self.ctb.jenv.get_template('redeem-already-done.tpl').render(coin=self.ctb.conf.coins[self.coin].name if self.ctb.conf.reddit.redeem.multicoin else None, a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        # Check if this user has > minimum karma
        user_karma = int(self.u_from.prawobj.link_karma) + int(self.u_from.prawobj.comment_karma)
        if user_karma < self.ctb.conf.reddit.redeem.min_karma:
            msg = self.ctb.jenv.get_template('redeem-low-karma.tpl').render(user_karma=user_karma, a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        # Determine amount
        self.fiat = self.ctb.conf.reddit.redeem.unit
        self.coinval, self.fiatval = self.u_from.get_redeem_amount(coin=self.coin, fiat=self.fiat)

        # Check if coinval and fiatval are valid
        if not self.coinval or not self.fiatval or not self.coinval > 0.0 or not self.fiatval > 0.0:
            msg = self.ctb.jenv.get_template('redeem-cant-compute.tpl').render(a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        # Check if redeem account has enough balance
        funds = self.ctb.coins[self.coin].getbalance(_user=self.ctb.conf.reddit.redeem.account, _minconf=1)
        if self.coinval > funds or abs(self.coinval - funds) < 0.000001:
            # Reply with 'not enough funds' message
            msg = self.ctb.jenv.get_template('redeem-low-funds.tpl').render(a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('failed')
            return False

        # Transfer coins
        if self.ctb.coins[self.coin].sendtouser(_userfrom=self.ctb.conf.reddit.redeem.account, _userto=self.u_from.name, _amount=self.coinval, _minconf=1):
            # Success, send confirmation
            msg = self.ctb.jenv.get_template('redeem-confirmation.tpl').render(a=self, ctb=self.ctb)
            lg.debug("CtbAction::redeem(): %s", msg)
            ctb_misc.praw_call(self.msg.reply, msg)
            self.save('completed')
            return True
        else:
            raise Exception("CtbAction::redeem(): sendtouser failed")

    def rates(self, fiat='usd'):
        """
        Send info on coin exchange rates
        """
        lg.debug("> CtbAction::rates()")

        coins = []
        exchanges = []
        rates = {}

        # Get exchange rates
        for coin in self.ctb.coins:
            coins.append(coin)
            rates[coin] = {'average': {}}
            rates[coin]['average']['btc'] = self.ctb.runtime['ev'][coin]['btc']
            rates[coin]['average'][fiat] = self.ctb.runtime['ev'][coin]['btc'] * self.ctb.runtime['ev']['btc'][fiat]
            for exchange in self.ctb.exchanges:
                try:
                    rates[coin][exchange] = {}
                    if self.ctb.exchanges[exchange].supports_pair(_name1=coin, _name2='btc'):
                        rates[coin][exchange]['btc'] = self.ctb.exchanges[exchange].get_ticker_value(_name1=coin, _name2='btc')
                        if coin == 'btc' and self.ctb.exchanges[exchange].supports_pair(_name1='btc', _name2=fiat):
                            # Use exchange value to calculate btc's fiat value
                            rates[coin][exchange][fiat] = rates[coin][exchange]['btc'] * self.ctb.exchanges[exchange].get_ticker_value(_name1='btc', _name2=fiat)
                        else:
                            # Use average value to calculate coin's fiat value
                            rates[coin][exchange][fiat] = rates[coin][exchange]['btc'] * self.ctb.runtime['ev']['btc'][fiat]
                    else:
                        rates[coin][exchange]['btc'] = None
                        rates[coin][exchange][fiat] = None
                except TypeError as e:
                    msg = self.ctb.jenv.get_template('rates-error.tpl').render(exchange=exchange, a=self, ctb=self.ctb)
                    lg.debug("CtbAction::rates(): %s", msg)
                    ctb_misc.praw_call(self.msg.reply, msg)
                    self.save('failed')
                    return False

        for exchange in self.ctb.exchanges:
            exchanges.append(exchange)

        lg.debug("CtbAction::rates(): %s", rates)

        # Send message
        msg = self.ctb.jenv.get_template('rates.tpl').render(coins=sorted(coins), exchanges=sorted(exchanges), rates=rates, fiat=fiat, a=self, ctb=self.ctb)
        lg.debug("CtbAction::rates(): %s", msg)
        ctb_misc.praw_call(self.msg.reply, msg)
        self.save('completed')
        return True

def init_regex(ctb):
    """
    Initialize regular expressions used to match messages and comments
    """
    lg.debug("> init_regex()")

    cc = ctb.conf.coins
    fiat = ctb.conf.fiat
    actions = ctb.conf.regex.actions
    ctb.runtime['regex'] = []

    for a in vars(actions):
        if actions[a].simple:

            # Add simple message actions (info, register, accept, decline, history, rates)

            entry = ctb_misc.DotDict(
                {'regex':       actions[a].regex,
                 'action':      a,
                 'rg_amount':   0,
                 'rg_keyword':  0,
                 'rg_address':  0,
                 'rg_to_user':  0,
                 'coin':        None,
                 'fiat':        None,
                 'keyword':     None
                })
            lg.debug("init_regex(): ADDED %s: %s", entry.action, entry.regex)
            ctb.runtime['regex'].append(entry)

        else:

            # Add non-simple actions (givetip, redeem, withdraw)

            for r in sorted(vars(actions[a].regex)):
                lg.debug("init_regex(): processing regex %s", actions[a].regex[r].value)
                rval1 = actions[a].regex[r].value
                rval1 = rval1.replace('{REGEX_TIP_INIT}', ctb.conf.regex.values.tip_init.regex)
                rval1 = rval1.replace('{REGEX_USER}', ctb.conf.regex.values.username.regex)
                rval1 = rval1.replace('{REGEX_AMOUNT}', ctb.conf.regex.values.amount.regex)
                rval1 = rval1.replace('{REGEX_KEYWORD}', ctb.conf.regex.values.keywords.regex)

                if actions[a].regex[r].rg_coin > 0:

                    for c in sorted(vars(cc)):

                        if not cc[c].enabled:
                            continue
                        # lg.debug("init_regex(): processing coin %s", c)

                        rval2 = rval1.replace('{REGEX_COIN}', cc[c].regex.units)
                        rval2 = rval2.replace('{REGEX_ADDRESS}', cc[c].regex.address)

                        if actions[a].regex[r].rg_fiat > 0:

                            for f in sorted(vars(fiat)):

                                if not fiat[f].enabled:
                                    continue
                                # lg.debug("init_regex(): processing fiat %s", f)

                                rval3 = rval2.replace('{REGEX_FIAT}', fiat[f].regex.units)
                                entry = ctb_misc.DotDict(
                                    {'regex':           rval3,
                                     'action':          a,
                                     'rg_amount':       actions[a].regex[r].rg_amount,
                                     'rg_keyword':      actions[a].regex[r].rg_keyword,
                                     'rg_address':      actions[a].regex[r].rg_address,
                                     'rg_to_user':      actions[a].regex[r].rg_to_user,
                                     'coin':            cc[c].unit,
                                     'fiat':            fiat[f].unit
                                    })
                                lg.debug("init_regex(): ADDED %s: %s", entry.action, entry.regex)
                                ctb.runtime['regex'].append(entry)

                        else:

                            entry = ctb_misc.DotDict(
                                {'regex':           rval2,
                                 'action':          a,
                                 'rg_amount':       actions[a].regex[r].rg_amount,
                                 'rg_keyword':      actions[a].regex[r].rg_keyword,
                                 'rg_address':      actions[a].regex[r].rg_address,
                                 'rg_to_user':      actions[a].regex[r].rg_to_user,
                                 'coin':            cc[c].unit,
                                 'fiat':            None
                                })
                            lg.debug("init_regex(): ADDED %s: %s", entry.action, entry.regex)
                            ctb.runtime['regex'].append(entry)

                elif actions[a].regex[r].rg_fiat > 0:

                    for f in sorted(vars(fiat)):

                        if not fiat[f].enabled:
                            continue
                        # lg.debug("init_regex(): processing fiat %s", f)

                        rval2 = rval1.replace('{REGEX_FIAT}', fiat[f].regex.units)
                        entry = ctb_misc.DotDict(
                            {'regex':           rval2,
                             'action':          a,
                             'rg_amount':       actions[a].regex[r].rg_amount,
                             'rg_keyword':      actions[a].regex[r].rg_keyword,
                             'rg_address':      actions[a].regex[r].rg_address,
                             'rg_to_user':      actions[a].regex[r].rg_to_user,
                             'coin':            None,
                             'fiat':            fiat[f].unit
                            })
                        lg.debug("init_regex(): ADDED %s: %s", entry.action, entry.regex)
                        ctb.runtime['regex'].append(entry)

                elif actions[a].regex[r].rg_keyword > 0:

                    entry = ctb_misc.DotDict(
                        {'regex':           rval1,
                         'action':          a,
                         'rg_amount':       actions[a].regex[r].rg_amount,
                         'rg_keyword':      actions[a].regex[r].rg_keyword,
                         'rg_address':      actions[a].regex[r].rg_address,
                         'rg_to_user':      actions[a].regex[r].rg_to_user,
                         'coin':            None,
                         'fiat':            None
                        })
                    lg.debug("init_regex(): ADDED %s: %s", entry.action, entry.regex)
                    ctb.runtime['regex'].append(entry)

    lg.info("< init_regex() DONE (%s expressions)", len(ctb.runtime['regex']))
    return None

def eval_message(msg, ctb):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    lg.debug("> eval_message()")

    body = msg.body
    for r in ctb.runtime['regex']:

        # Attempt a match
        rg = re.compile(r.regex, re.IGNORECASE|re.DOTALL)
        #lg.debug("matching '%s' with '%s'", msg.body, r.regex)
        m = rg.search(body)

        if m:
            # Match found
            lg.debug("eval_message(): match found")

            # Extract matched fields into variables
            u_from = msg.author
            u_to = m.group(r.rg_to_user)[1:] if r.rg_to_user > 0 else None
            to_addr = m.group(r.rg_address) if r.rg_address > 0 else None
            amount = m.group(r.rg_amount) if r.rg_amount > 0 else None
            keyword = m.group(r.rg_keyword) if r.rg_keyword > 0 else None

            # Ignore 'givetip' without u_to and without to_addr
            if r.action == 'givetip' and not u_to and not to_addr:
                lg.warning("eval_message(): givetip: no to_user and no to_addr specified, ignoring")
                return None

            # Return CtbAction instance with given variables
            lg.debug("eval_message(): creating action %s: from_user=%s, to_addr=%s, amount=%s, coin=%s, fiat=%s" % (r.action, u_from, to_addr, amount, r.coin, r.fiat))
            try:
                action = CtbAction(
                    atype=r.action,
                    msg=msg,
                    from_user=u_from,
                    to_user=u_to,
                    to_addr=to_addr,
                    coin=r.coin,
                    coin_val=amount if not r.fiat else None,
                    fiat=r.fiat,
                    fiat_val=amount if r.fiat else None,
                    keyword=keyword,
                    ctb=ctb)
                return action
            except CtbActionExc as e:
                lg.warning("eval_message(): " + str(e))
                return None

    # No match found
    lg.debug("eval_message(): no match found")
    return None

def eval_comment(comment, ctb):
    """
    Evaluate comment body and return a CtbAction object if successful
    """
    lg.debug("> eval_comment()")

    body = comment.body
    for r in ctb.runtime['regex']:

        # Skip non-public actions
        if not ctb.conf.regex.actions[r.action].public:
            continue

        # Attempt a match
        rg = re.compile(r.regex, re.IGNORECASE|re.DOTALL)
        #lg.debug("eval_comment(): matching '%s' with <%s>", comment.body, r.regex)
        m = rg.search(body)

        if m:
            # Match found
            lg.debug("eval_comment(): match found")

            # Extract matched fields into variables
            u_to = m.group(r.rg_to_user)[1:] if r.rg_to_user > 0 else None
            to_addr = m.group(r.rg_address) if r.rg_address > 0 else None
            amount = m.group(r.rg_amount) if r.rg_amount > 0 else None
            keyword = m.group(r.rg_keyword) if r.rg_keyword > 0 else None

            # If no destination mentioned, find parent submission's author
            if not u_to and not to_addr:
                # set u_to to author of parent comment
                u_to = ctb_misc.reddit_get_parent_author(comment, ctb.reddit, ctb)
                if not u_to:
                    # couldn't determine u_to, giving up
                    lg.warning("eval_comment(): couldn't determine u_to, giving up")
                    return None

            # Check if from_user == to_user
            if u_to and comment.author.name.lower() == u_to.lower():
                lg.warning("eval_comment(): comment.author.name == u_to, ignoring comment", comment.author.name)
                return None

            # Return CtbAction instance with given variables
            lg.debug("eval_comment(): creating action %s: to_user=%s, to_addr=%s, amount=%s, coin=%s, fiat=%s" % (r.action, u_to, to_addr, amount, r.coin, r.fiat))
            try:
                action = CtbAction(
                    atype=r.action,
                    msg=comment,
                    to_user=u_to,
                    to_addr=to_addr,
                    coin=r.coin,
                    coin_val=amount if not r.fiat else None,
                    fiat=r.fiat,
                    fiat_val=amount if r.fiat else None,
                    keyword=keyword,
                    subr=comment.subreddit,
                    ctb=ctb)
                return action
            except CtbActionExc as e:
                lg.warning("eval_comment(): " + str(e))
                return None

    # No match found
    lg.debug("< eval_comment() DONE (no match)")
    return None

def check_action(atype=None, state=None, coin=None, msg_id=None, created_utc=None, from_user=None, to_user=None, subr=None, ctb=None, is_pending=False):
    """
    Return True if action with given attributes exists in database
    """
    lg.debug("> check_action(%s)", atype)

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if atype or state or coin or msg_id or created_utc or from_user or to_user or subr or is_pending:
        sql += " WHERE "
        if atype:
            sql_terms.append("type = '%s'" % atype)
        if state:
            sql_terms.append("state = '%s'" % state)
        if coin:
            sql_terms.append("coin = '%s'" % coin)
        if msg_id:
            sql_terms.append("msg_id = '%s'" % msg_id)
        if created_utc:
            sql_terms.append("created_utc = %s" % created_utc)
        if from_user:
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if to_user:
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if subr:
            sql_terms.append("subreddit = '%s'" % subr)
        if is_pending:
            sql_terms.append("state <> 'pending'")
        sql += ' AND '.join(sql_terms)

    try:
        lg.debug("check_action(): <%s>", sql)
        mysqlexec = ctb.db.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.debug("< check_action() DONE (no)")
            return False
        else:
            lg.debug("< check_action() DONE (yes)")
            return True
    except Exception as e:
        lg.error("check_action(): error executing <%s>: %s", sql, e)
        raise

    lg.warning("< check_action() DONE (should not get here)")
    return None

def get_actions(atype=None, state=None, coin=None, msg_id=None, created_utc=None, from_user=None, to_user=None, subr=None, ctb=None):
    """
    Return an array of CtbAction objects from database with given attributes
    """
    lg.debug("> get_actions(%s)", atype)

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if atype or state or coin or msg_id or created_utc or from_user or to_user or subr:
        sql += " WHERE "
        if atype:
            sql_terms.append("type = '%s'" % atype)
        if state:
            sql_terms.append("state = '%s'" % state)
        if coin:
            sql_terms.append("coin = '%s'" % coin)
        if msg_id:
            sql_terms.append("msg_id = '%s'" % msg_id)
        if created_utc:
            sql_terms.append("created_utc %s" % created_utc)
        if from_user:
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if to_user:
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if subr:
            sql_terms.append("subreddit = '%s'" % subr)
        sql += ' AND '.join(sql_terms)

    while True:
        try:
            r = []
            lg.debug("get_actions(): <%s>", sql)
            mysqlexec = ctb.db.execute(sql)

            if mysqlexec.rowcount <= 0:
                lg.debug("< get_actions() DONE (no)")
                return r

            for m in mysqlexec:
                lg.debug("get_actions(): found %s / %s", m['msg_link'], m['msg_id'])

                # Get PRAW message/comment pointer (msg)
                msg = None
                if m['msg_link']:
                    submission = ctb_misc.praw_call(ctb.reddit.get_submission, m['msg_link'])
                    if not len(submission.comments) > 0:
                        lg.warning("get_actions(): could not fetch msg (deleted?) from msg_link %s", m['msg_link'])
                    else:
                        # msg points to comment that initiated the action
                        msg = submission.comments[0]
                        # check if msg.author is present
                        if not msg.author:
                            lg.warning("get_actions(): could not fetch msg.author (deleted?) from msg_link %s", m['msg_link'])
                #elif m['msg_id']:
                #    msg = praw.objects.Message(ctb.reddit, {'id': m['msg_id']})

                r.append( CtbAction( atype=atype,
                                     msg=msg,
                                     from_user=m['from_user'],
                                     to_user=m['to_user'],
                                     to_addr=m['to_addr'] if not m['to_user'] else None,
                                     coin=m['coin'],
                                     fiat=m['fiat'],
                                     coin_val=float(m['coin_val']) if m['coin_val'] else None,
                                     fiat_val=float(m['fiat_val']) if m['fiat_val'] else None,
                                     subr=m['subreddit'],
                                     ctb=ctb,
                                     msg_id=m['msg_id']))

            lg.debug("< get_actions() DONE (yes)")
            return r

        except Exception as e:
            lg.error("get_actions(): error executing <%s>: %s", sql, e)
            raise

    lg.warning("< get_actions() DONE (should not get here)")
    return None
