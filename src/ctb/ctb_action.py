import ctb_user, ctb_misc

import logging, praw, re, time

from requests.exceptions import HTTPError
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

lg = logging.getLogger('cointipbot')

class CtbAction(object):
    """
    Action class for cointip bot
    """

    _TYPE=None          # 'accept', 'decline', 'history', 'info', 'register', 'givetip', 'withdraw'
    _STATE=None         # 'completed', 'pending', 'failed', 'declined'
    _TXID=None          # cryptocoin transaction id, a 64-char string, if applicable

    _FROM_USER=None     # CtbUser instance
    _TO_USER=None       # CtbUser instance, if applicable

    _TO_AMNT=None       # float specifying value of 'givetip' and 'withdraw' actions
    _TO_ADDR=None       # destination cryptocoin address of 'givetip' and 'withdraw' actions, if applicable

    _USD_VAL=None       # USD value of the 'givetip' action, if applicable

    _COIN=None          # coin for this action (for example, 'ltc')
    _FIAT=None          # fiat for this action (for example, 'usd'), if applicable

    _SUBR=None          # subreddit that originated the action, if applicable

    _MSG=None           # Reddit object pointing to originating message/comment
    _CTB=None           # CointipBot instance

    def __init__(self, atype=None, msg=None, to_user=None, to_amnt=None, to_addr=None, coin=None, fiat=None, subr=None, usd_val=None, ctb=None):
        """
        Initialize CtbAction object with given parameters and run basic checks
        """
        lg.debug("> CtbAction::__init__(atype=%s, from_user=%s)", atype, msg.author.name)

        self._TYPE = atype

        self._COIN = coin.lower() if bool(coin) else 'x'
        self._FIAT = fiat.lower() if bool(fiat) else None
        self._SUBR = subr
        self._USD_VAL = float(usd_val) if bool(usd_val) else float(0)

        self._MSG = msg
        self._CTB = ctb

        self._TO_AMNT = float(to_amnt) if bool(to_amnt) else float(0)
        self._TO_ADDR = to_addr
        self._TO_USER = ctb_user.CtbUser(name=to_user, ctb=ctb) if bool(to_user) else None
        self._FROM_USER = ctb_user.CtbUser(name=msg.author.name, redditobj=msg.author, ctb=ctb) if bool(msg) else None

        # Do some checks
        if not bool(self._TYPE) or self._TYPE not in ['accept', 'decline', 'history', 'info', 'register', 'givetip', 'withdraw']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")

        if not bool(self._CTB):
            raise Exception("CtbAction::__init__(type=%s): no reference to CointipBot", self._TYPE)

        if not bool(self._MSG):
            raise Exception("CtbAction::__init__(type=%s): no reference to Reddit message/comment", self._TYPE)

        if self._TYPE in ['givetip', 'withdraw']:
            if not bool(self._TO_AMNT):
                raise Exception("CtbAction::__init__(type=givetip): _TO_AMNT must be set")
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
            if not (bool(self._COIN) ^ bool(self._FIAT)):
                raise Exception("CtbAction::__init__(type=givetip): _COIN xor _FIAT must be set")

        # Subtract tx fee if it's needed
        if bool(self._TO_ADDR):
            self._TO_AMNT -= self._CTB._config['cc'][self._COIN]['txfee']

        # Determine USD value of 'givetip' action
        if not bool(self._USD_VAL):
            if self._TYPE in ['givetip', 'withdraw']:
                if hasattr(ctb, '_ticker_val'):
                    self._USD_VAL = float(to_amnt) * ctb._ticker_val[coin+'_btc']['avg'] * ctb._ticker_val['btc_usd']['avg']

        lg.debug("< CtbAction::__init__(atype=%s, from_user=%s) DONE", self._TYPE, self._FROM_USER._NAME)

    def save(self, state=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save(%s)", state)

        conn = self._CTB._mysqlcon
        sql = "REPLACE INTO t_action (type, state, created_utc, from_user, to_user, to_addr, to_amnt, usd_value, txid, coin, fiat, subreddit, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(sql,
                    (self._TYPE,
                     state,
                     self._MSG.created_utc,
                     self._FROM_USER._NAME.lower(),
                     self._TO_USER._NAME.lower() if bool(self._TO_USER) else None,
                     self._TO_ADDR,
                     self._TO_AMNT,
                     self._USD_VAL,
                     self._TXID,
                     self._COIN,
                     self._FIAT,
                     self._SUBR,
                     self._MSG.id,
                     self._MSG.permalink if hasattr(self._MSG, 'permalink') else None))
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception as e:
            lg.error("CtbAction::save(%s): error executing query <%s>: %s", state, sql % (
                self._TYPE,
                state,
                self._MSG.created_utc,
                self._FROM_USER._NAME.lower(),
                self._TO_USER._NAME.lower() if bool(self._TO_USER) else None,
                self._TO_ADDR,
                self._TO_AMNT,
                self._USD_VAL,
                self._TXID,
                self._COIN,
                self._FIAT,
                self._SUBR,
                self._MSG.id,
                self._MSG.permalink if hasattr(self._MSG, 'permalink') else None), str(e))
            raise

        lg.debug("< CtbAction::save() DONE")
        return True

    def do(self):
        """
        Call appropriate function depending on action type
        """
        lg.debug("> CtbAction::do()")
        if self._TYPE == 'accept':
            return ( self.accept() and self.info() )
        if self._TYPE == 'decline':
            return self.decline()
        if self._TYPE == 'givetip':
            return self.givetip()
        if self._TYPE == 'history':
            return self.history()
        if self._TYPE == 'info':
            return self.info()
        if self._TYPE == 'register':
            return ( self.register() and self.info() )
        if self._TYPE == 'withdraw':
            return self.givetip()
        lg.debug("< CtbAction::do() DONE")
        return None

    def history(self):
        """
        Provide user with transaction history
        """
        return None

    def accept(self):
        """
        Accept pending tip
        """
        lg.debug("> CtbAction::accept()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB)):
            lg.debug("CtbAction::accept(): duplicate action %s, ignoring", self._MSG.id)
            return False

        # Register as new user
        if not self._FROM_USER.is_registered():
            if not self._FROM_USER.register():
                lg.debug("CtbAction::accept(): self._FROM_USER.register() failed")
                self.save('failed')
                return False

        # Get pending actions
        actions = _get_actions(atype='givetip', to_user=self._FROM_USER._NAME, state='pending', ctb=self._CTB)
        if bool(actions):
            # Accept each action
            for a in actions:
                a.givetip(is_pending=True)
        else:
            # No pending actouns found, reply with error message
            txt = "I'm sorry %s, you don't have any pending tips. Perhaps they've been already confirmed or already expired." % self._FROM_USER._NAME
            lg.debug("CtbAction::accept(): %s", txt)
            txt += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            ctb_misc._reddit_reply(msg=self._MSG, txt=txt)

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::accept() DONE")
        return True

    def decline(self):
        """
        Decline pending tips
        """
        lg.debug("> CtbAction::decline()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB)):
            lg.debug("CtbAction::decline(): duplicate action %s, ignoring", self._MSG.id)
            return False

        actions = _get_actions(atype='givetip', to_user=self._FROM_USER._NAME, state='pending', ctb=self._CTB)
        if bool(actions):
            for a in actions:
                # Move coins back into a._FROM_USER account
                try:
                    lg.info("CtbAction::decline(): moving %s %s from %s to %s", str(a._TO_AMNT), a._COIN, _config['reddit']['user'].lower(), a._FROM_USER._NAME.lower())
                    m = _coincon[a._COIN].move(_config['reddit']['user'].lower(), a._FROM_USER._NAME.lower(), a._TO_AMNT)
                    # Sleep for 0.5 seconds to not overwhelm coin daemon
                    time.sleep(0.5)
                except Exception as e:
                    lg.error("CtbAction::decline(): error: %s", str(e))
                    raise
                # Save transaction as declined
                a.save('declined')
                # Respond to tip comment
                cmnt = "^__[Declined]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (a._FROM_USER._NAME, a._TO_USER._NAME, a._TO_AMNT, _cc[self._COIN]['name'])
                if bool(self._USD_VAL):
                    cmnt += "&nbsp;^__($%.4g)__" % self._USD_VAL
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                lg.debug("CtbAction::decline(): " + cmnt)
                if _config['reddit']['comments']['declined']:
                    if not ctb_misc._reddit_reply(msg=a._MSG, txt=cmnt):
                        a._FROM_USER.tell(subj="+givetip declined", msg=cmnt)
                else:
                    a._FROM_USER.tell(subj="+givetip declined", msg=cmnt)

            # Notify self._FROM_USER
            txt = "Hello %s, your pending tips have been declined." % self._FROM_USER._NAME
            lg.debug("CtbAction::decline(): %s", txt)
            txt += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            ctb_misc._reddit_reply(msg=self._MSG, txt=txt)
        else:
            txt = "I'm sorry %s, you don't have any pending tips. Perhaps they've already expired." % self._FROM_USER._NAME
            lg.debug("CtbAction::decline(): %s", txt)
            txt += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            ctb_misc._reddit_reply(msg=self._MSG, txt=txt)

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::decline() DONE")
        return True

    def expire(self):
        """
        Expire a pending tip
        """
        lg.debug("> CtbAction::expire()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        # Move coins back into self._FROM_USER account
        try:
            lg.info("CtbAction::expire(): moving %s %s from %s to %s", str(self._TO_AMNT), self._COIN, _config['reddit']['user'], self._FROM_USER._NAME.lower())
            m = _coincon[self._COIN].move(_config['reddit']['user'].lower(), self._FROM_USER._NAME.lower(), self._TO_AMNT)
            # Sleep for 0.5 seconds to not overwhelm coin daemon
            time.sleep(0.5)
        except Exception as e:
            lg.error("CtbAction::expire(): error: %s", str(e))
            raise

        # Save transaction as declined
        self.save('declined')

        # Respond to tip comment
        cmnt = "^__[Expired]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._TO_AMNT, _cc[self._COIN]['name'])
        if bool(self._USD_VAL):
            cmnt += "&nbsp;^__($%.4g)__" % self._USD_VAL
        cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
        lg.debug("CtbAction::expire(): " + cmnt)
        if _config['reddit']['comments']['expired']:
            if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                self._FROM_USER.tell(subj="+givetip expired", msg=cmnt)
        else:
            self._FROM_USER.tell(subj="+givetip expired", msg=cmnt)

        lg.debug("< CtbAction::expire() DONE")
        return True

    def validate(self, is_pending=False):
        """
        Validate an action
        """
        lg.debug("> CtbAction::validate()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if self._TYPE in ['givetip', 'withdraw']:
            # Check if _FROM_USER has registered
            if not self._FROM_USER.is_registered():
                msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (re.escape(self._FROM_USER._NAME), self._CTB._config['reddit']['user'])
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                self.save('failed')
                return False

            # Verify that _FROM_USER has coin address
            if not self._FROM_USER.get_addr(coin=self._COIN):
                msg = "I'm sorry %s, you don't seem to have a %s address." % (re.escape(self._FROM_USER._NAME), self._COIN.upper())
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                self.save('failed')
                return False

            # Verify minimum transaction size
            txkind = 'givetip' if bool(self._TO_USER) else 'withdraw'
            if self._TO_AMNT < _cc[self._COIN]['txmin'][txkind]:
                msg = "I'm sorry %s, your tip/withdraw of __%.6g %s__ is below minimum of __%.6g__." % (re.escape(self._FROM_USER._NAME), self._TO_AMNT, self._COIN.upper(), _cc[self._COIN]['txmin'][txkind])
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                self.save('failed')
                return False

            # Verify balance (unless it's a pending transaction being processed, in which case coins have been already moved to pending acct)
            if bool(self._TO_USER) and not is_pending:
                # Tip to user (requires less confirmations)
                balance_avail = self._FROM_USER.get_balance(coin=self._COIN, kind='givetip')
                if not ( balance_avail > self._TO_AMNT or abs(balance_avail - self._TO_AMNT) < 0.000001 ):
                    msg = "I'm sorry %s, your confirmed _tip_ balance of __%.6g %s__ is insufficient for this tip." % (re.escape(self._FROM_USER._NAME), balance_avail, self._COIN.upper())
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                    self.save('failed')
                    return False
            elif bool(self._TO_ADDR):
                # Tip/withdrawal to address (requires more confirmations)
                balance_avail = self._FROM_USER.get_balance(coin=self._COIN, kind='withdraw')
                if not ( balance_avail > self._TO_AMNT or abs(balance_avail - self._TO_AMNT) < 0.000001 ):
                    msg = "I'm sorry %s, your confirmed _withdraw_ balance of __%.6g %s__ is insufficient for this action." % (re.escape(self._FROM_USER._NAME), balance_avail, self._COIN.upper())
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                    self.save('failed')
                    return False

            # Check if _TO_USER has any pending _COIN tips from _FROM_USER
            if (bool(self._TO_USER)) and not is_pending:
                if _check_action(atype='givetip', state='pending', to_user=self._TO_USER._NAME, from_user=self._FROM_USER._NAME, coin=self._COIN, ctb=self._CTB):
                    # Send notice to _FROM_USER
                    msg = "I'm sorry %s, /u/%s already has a pending %s tip from you. Please wait until he/she accepts or declines it." % (re.escape(self._FROM_USER._NAME), re.escape(self._TO_USER._NAME), self._COIN.upper())
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += " Pending tips expire in %.1g days." % ( float(_config['misc']['expire-pending-hours']) / float(24) )
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                    self.save('failed')
                    return False

            # Check if _TO_USER has registered, if applicable
            if (bool(self._TO_USER)) and not self._TO_USER.is_registered():
                # _TO_USER not registered:
                # - move tip into pending account
                # - save action as 'pending'
                # - notify _TO_USER to accept tip

                # Move coins into pending account
                try:
                    lg.info("CtbAction::validate(): moving %s %s from %s to %s", str(self._TO_AMNT), self._COIN, self._FROM_USER._NAME.lower(), _config['reddit']['user'])
                    m = _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), _config['reddit']['user'].lower(), self._TO_AMNT)
                    # Sleep for 0.5 seconds to not overwhelm coin daemon
                    time.sleep(0.5)
                except Exception as e:
                    lg.error("CtbAction::validate(): error: %s", str(e))
                    raise

                # Save action as pending
                self.save('pending')

                # Respond to tip comment
                cmnt = "^(__[Verified]__:) ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._TO_AMNT, _cc[self._COIN]['name'])
                if bool(self._USD_VAL):
                    cmnt += "&nbsp;^__($%.4g)__" % self._USD_VAL
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                lg.debug("CtbAction::validate(): " + cmnt)
                if _config['reddit']['comments']['verify']:
                    if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                        self._FROM_USER.tell(subj="+givetip pending +accept", msg=cmnt)
                else:
                    self._FROM_USER.tell(subj="+givetip pending +accept", msg=cmnt)

                # Send notice to _TO_USER
                msg = "Hey %s, /u/%s sent you a __%.6g %s(s) ($%.4g)__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to=%s&subject=accept&message=%%2Baccept)__ to claim it. "
                msg += "Reply with __[+decline](http://www.reddit.com/message/compose?to=%s&subject=decline&message=%%2Bdecline)__ to decline it."
                msg = msg % (re.escape(self._TO_USER._NAME), re.escape(self._FROM_USER._NAME), self._TO_AMNT, _cc[self._COIN]['name'], self._USD_VAL, self._CTB._config['reddit']['user'], self._CTB._config['reddit']['user'])
                msg += " Pending tips expire in %.1g days." % ( float(_config['misc']['expire-pending-hours']) / float(24) )
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._TO_USER.tell(subj="+givetip pending", msg=msg)

                # Action saved as 'pending', return false to avoid processing it
                return False

            # Validate _TO_ADDR, if applicable
            if bool(self._TO_ADDR):
                addr_valid = _coincon[self._COIN].validateaddress(self._TO_ADDR)
                if not addr_valid['isvalid']:
                    msg = "I'm sorry %s, __%s__ address __%s__ appears to be invalid (is there a typo?)." % (re.escape(self._FROM_USER._NAME), self._COIN.upper(), self._TO_ADDR)
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                    self.save('failed')
                    return False

        # Action is valid
        lg.debug("< CtbAction::validate() DONE")
        return True

    def givetip(self, is_pending=False):
        """
        Initiate tip
        """
        lg.debug("> CtbAction::givetip()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        # Check if action has been processed
        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB, is_pending=is_pending)):
            # Found action in database, returning
            lg.warning("CtbAction::givetip(): duplicate action (msg_id=%s, created_utc=%s)", self._MSG.id, self._MSG.created_utc)
            return False

        # Validate action
        if not self.validate(is_pending=is_pending):
            # Couldn't validate action, returning
            return False

        if bool(self._TO_USER):
            # Process tip to user

            try:
                if is_pending:
                    lg.debug("CtbAction::givetip(): sending %f %s from %s to %s...", self._TO_AMNT, self._COIN.upper(), _config['reddit']['user'].lower(), self._TO_USER._NAME.lower())
                    self._TXID = _coincon[self._COIN].move(_config['reddit']['user'].lower(), self._TO_USER._NAME.lower(), self._TO_AMNT, _cc[self._COIN]['minconf'][self._TYPE])
                else:
                    lg.debug("CtbAction::givetip(): sending %f %s from %s to %s...", self._TO_AMNT, self._COIN.upper(), self._FROM_USER._NAME.lower(), self._TO_USER._NAME.lower())
                    self._TXID = _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), self._TO_USER._NAME.lower(), self._TO_AMNT, _cc[self._COIN]['minconf'][self._TYPE])
                # Sleep for 0.5 seconds to not overwhelm coin daemon
                time.sleep(0.5)
            except Exception as e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%.6g %s(s)__ to /u/%s has failed to process." % (re.escape(self._FROM_USER._NAME), self._TO_AMNT, _cc[self._COIN]['name'], re.escape(self._TO_USER._NAME))
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)

                # Log error
                lg.error("CtbAction::givetip(): move of %s %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN, (self._FROM_USER._NAME if is_pending else _config['reddit']['user']), self._TO_USER._NAME, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Send confirmation to _TO_USER
                msg = "Hey %s, you have received a __%.6g %s(s) ($%.4g)__ tip from /u/%s." % (re.escape(self._TO_USER._NAME), self._TO_AMNT, _cc[self._COIN]['name'], self._USD_VAL, re.escape(self._FROM_USER._NAME))
                lg.debug("CtbAction::givetip(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+givetip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._TO_USER.tell(subj="+givetip received", msg=msg)

                if not is_pending:
                    # This is not an +accept, so post verification comment
                    cmnt = "^__[Verified]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._TO_AMNT, _cc[self._COIN]['name'])
                    if bool(self._USD_VAL):
                        cmnt += "&nbsp;^__($%.4g)__" % self._USD_VAL
                    lg.debug("CtbAction::givetip(): " + cmnt)
                    cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                    if _config['reddit']['comments']['verify']:
                        if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                            self._FROM_USER.tell(subj="+givetip succeeded", msg=cmnt)
                    else:
                        self._FROM_USER.tell(subj="+givetip succeeded", msg=cmnt)

            except Exception as e:
                # Couldn't post to Reddit
                lg.error("CtbAction::givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::givetip() DONE")
            return True

        elif bool(self._TO_ADDR):
            # Process tip to address

            try:
                lg.debug("CtbAction::givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN, self._TO_ADDR)
                if _cc[self._COIN].has_key('walletpassphrase'):
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 3)
                self._TXID = _coincon[self._COIN].sendfrom(self._FROM_USER._NAME.lower(), self._TO_ADDR, self._TO_AMNT, _cc[self._COIN]['minconf'][self._TYPE])
                # Sleep for 2 seconds to not overwhelm coin daemon
                time.sleep(2)

            except Exception as e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%.6g %s(s)__ to __%s__ has failed to process." % (re.escape(self._FROM_USER._NAME), self._TO_AMNT, _cc[self._COIN]['name'], self._TO_ADDR)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                lg.error("CtbAction::givetip(): tx of %f %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN, self._FROM_USER._NAME, self._TO_ADDR, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Post verification comment
                ex = _cc[self._COIN]['explorer']
                cmnt = "^__[[Verified](%s)]__: ^/u/%s ^-> ^[%s](%s), __^%.6g ^%s(s)__" % (ex['transaction'] + self._TXID, self._FROM_USER._NAME, self._TO_ADDR, ex['address'] + self._TO_ADDR, self._TO_AMNT, _cc[self._COIN]['name'])
                if bool(self._USD_VAL):
                    cmnt += "&nbsp;^__($%.4g)__" % self._USD_VAL
                lg.debug("CtbAction::givetip(): " + cmnt)
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                if _config['reddit']['comments']['verify']:
                    if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                        self._FROM_USER.tell(subj="+givetip succeeded", msg=cmnt)
                else:
                    self._FROM_USER.tell(subj="+givetip succeeded", msg=cmnt)
            except Exception as e:
                # Couldn't post to Reddit
                lg.error("CtbAction::givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::givetip() DONE")
            return True

        lg.debug("< CtbAction::givetip() DONE")
        return None

    def info(self):
        """
        Send user info about account
        """
        lg.debug("> CtbAction::info()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB)):
            lg.debug("CtbAction::info(): duplicate action %s, ignoring", self._MSG.id)
            return False

        # Check if user exists
        if not self._FROM_USER.is_registered():
            msg = "I'm sorry %s, we've never met. " % (re.escape(self._FROM_USER._NAME))
            msg += "Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._CTB._config['reddit']['user'])
            msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            self._FROM_USER.tell(subj="+info failed", msg=msg)
            return False

        # Gather data for info message
        info = []
        for c in _coincon:
            coininfo = {}
            coininfo['coin'] = c
            try:
                coininfo['tbalance'] = float(_coincon[c].getbalance(self._FROM_USER._NAME.lower(), _cc[c]['minconf']['givetip']))
                time.sleep(0.5)
                coininfo['wbalance'] = float(_coincon[c].getbalance(self._FROM_USER._NAME.lower(), _cc[c]['minconf']['withdraw']))
                time.sleep(0.5)
                # wbalance can be negative since tips require less confirmations, so set it to 0 if negative
                if coininfo['wbalance'] < 0:
                    coininfo['wbalance'] = 0
                info.append(coininfo)
            except Exception as e:
                lg.error("CtbAction::info(%s): error retrieving %s coininfo: %s", self._FROM_USER._NAME, c, str(e))
                raise

        # Get coin addresses from MySQL
        for i in info:
            sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER._NAME.lower(), i['coin'])
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                raise Exception("CtbAction::info(%s): no result from <%s>" % (self._FROM_USER._NAME, sql))
            i['address'] = mysqlrow['address']

        # Format info message
        tbalance_usd_total = float(0)
        wbalance_usd_total = float(0)
        txt = "Hello %s! Here's your account info.\n\n" % self._FROM_USER._NAME
        txt += "coin|deposit address|tip balance|withdraw balance\n:---|:---|:---|:---\n"
        for i in info:
            addr_ex_str = '[[ex]](' + _cc[i['coin']]['explorer']['address'] + '%s)'
            addr_ex_str = addr_ex_str % (i['address'])
            addr_qr_str = '[[qr]](' + _config['misc']['qr-service-url'] + '%s%%3A%s)'
            addr_qr_str = addr_qr_str % (_cc[i['coin']]['name'].lower(), i['address'])
            tbalance_usd = float(0)
            wbalance_usd = float(0)
            if hasattr(self._CTB, '_ticker_val'): # and hasattr(self._CTB._ticker_val, i['coin']+'_btc') and hasattr(self._CTB._ticker_val, 'btc_usd'):
                tbalance_usd = self._CTB._ticker_val[i['coin']+'_btc']['avg'] * self._CTB._ticker_val['btc_usd']['avg'] * float(i['tbalance'])
                wbalance_usd = self._CTB._ticker_val[i['coin']+'_btc']['avg'] * self._CTB._ticker_val['btc_usd']['avg'] * float(i['wbalance'])
                tbalance_usd_total += tbalance_usd
                wbalance_usd_total += wbalance_usd
            txt += "__%s (%s)__|%s&nbsp;^%s&nbsp;%s|__%.6f&nbsp;^$%.4g__|%.6f&nbsp;^$%.4g\n" % (_cc[i['coin']]['name'], i['coin'].upper(), i['address'], addr_ex_str, addr_qr_str, i['tbalance'], tbalance_usd, i['wbalance'], wbalance_usd)
        txt += "&nbsp;|&nbsp;|&nbsp;|&nbsp;\n"
        txt += "__TOTAL $__|&nbsp;|__$%.4g__|$%.4g\n" % (tbalance_usd_total, wbalance_usd_total)
        txt += "\n\nUse addresses above to deposit coins into your account. Tip and withdraw balances differ while newly deposited coins are confirmed."
        txt += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])

        # Send info message
        ctb_misc._reddit_reply(msg=self._MSG, txt=txt)

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::info() DONE")
        return True

    def register(self):
        """
        Register a new user
        """
        lg.debug("> CtbAction::register()")

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB)):
            lg.debug("CtbAction::register(): duplicate action %s, ignoring", self._MSG.id)
            return False

        # If user exists, do nothing
        if self._FROM_USER.is_registered():
            lg.debug("CtbAction::register(%s): user already exists; ignoring request", self._FROM_USER._NAME)
            self.save('completed')
            return True

        result = self._FROM_USER.register()

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::register() DONE")
        return result


def _eval_message(_message, _ctb):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    #lg.debug("> _eval_message()")

    if not bool(_ctb._rlist_message):
        # rlist is a list of regular expressions to test _message against
        #   'regex': regular expression
        #   'action': action type
        #   'coin': unit of cryptocurrency, if applicable
        #   'rg-amount': group number to retrieve amount, if applicable
        #   'rg-address': group number to retrieve coin address, if applicable
        _ctb._rlist_message = [
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['register'],
                 'action':     'register',
                 'rg-amount':  -1,
                 'rg-address': -1,
                 'coin':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['accept'],
                 'action':     'accept',
                 'rg-amount':  -1,
                 'rg-address': -1,
                 'coin':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['decline'],
                 'action':     'decline',
                 'rg-amount':  -1,
                 'rg-address': -1,
                 'coin':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['history'],
                 'action':     'history',
                 'rg-amount':  -1,
                 'rg-address': -1,
                 'coin':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['info'],
                 'action':     'info',
                 'rg-amount':  -1,
                 'rg-address': -1,
                 'coin':       None}
                ]
        # Add regex for each configured cryptocoin
        _cc = _ctb._config['cc']
        for c in _cc:
            if _cc[c]['enabled']:
                _ctb._rlist_message.append(
                   # +withdraw ADDR 0.25 COIN
                   {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['withdraw'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
                    'action':     'withdraw',
                    'coin':       _cc[c]['unit'],
                    'rg-amount':  6,
                    'rg-address': 4})

    # Do the matching
    body = _message.body
    for r in _ctb._rlist_message:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("matching '%s' with '%s'", _message.body, r['regex'])
        m = rg.search(body)

        if bool(m):
            # Match found

            # Extract matched fields into variables
            _to_addr = m.group(r['rg-address']) if r['rg-address'] > 0 else None
            _to_amnt = m.group(r['rg-amount']) if r['rg-amount'] > 0 else None

            # Return CtbAction instance with given variables
            return CtbAction(   atype=r['action'],
                                msg=_message,
                                to_user=None,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                coin=r['coin'],
                                fiat=None,
                                ctb=_ctb)

    # No match found
    return None

def _eval_comment(_comment, _ctb):
    """
    Evaluate comment body and return a CtbAction
    object if successful
    """
    #lg.debug("> _eval_comment()")

    _cc = _ctb._config['cc']

    if not bool(_ctb._rlist_comment):
        # rlist is a list of regular expressions to test _comment against
        #   'regex': regular expression
        #   'action': action type
        #   'rg-to-user': group number to retrieve tip receiver username
        #   'rg-amount': group number to retrieve tip amount
        #   'rg-address': group number to retrieve tip receiver coin address
        #   'coin': unit of cryptocurrency
        for c in _cc:
            if _cc[c]['enabled']:
                _ctb._rlist_comment.append(
                    # +givetip ADDR 0.25 units
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  -1,
                     'rg-amount':   6,
                     'rg-address':  4,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip 0.25 units
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  -1,
                     'rg-amount':   4,
                     'rg-address':  -1,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip @user 0.25 units
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  4,
                     'rg-amount':   6,
                     'rg-address':  -1,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})

    # Do the matching
    body = _comment.body
    for r in _ctb._rlist_comment:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("_eval_comment(): matching '%s' using <%s>", _comment.body, r['regex'])
        m = rg.search(body)

        if bool(m):
            # Match found

            # Extract matched fields into variables
            _to_user = m.group(r['rg-to-user'])[1:] if r['rg-to-user'] > 0 else None
            _to_addr = m.group(r['rg-address']) if r['rg-address'] > 0 else None
            _to_amnt = m.group(r['rg-amount']) if r['rg-amount'] > 0 else None

            # If no destination mentioned, find parent submission's author
            if not bool(_to_user) and not bool(_to_addr):
                # set _to_user to author of parent comment
                _to_user = ctb_misc._reddit_get_parent_author(_comment, _ctb._redditcon, _ctb=_ctb)

            # Check if from_user == to_user
            if bool(_to_user) and _comment.author.name.lower() == _to_user.lower():
                lg.warning("_eval_comment(%s): _comment.author.name == _to_user, ignoring comment", _comment.author.name)
                return None

            # Return CtbAction instance with given variables
            lg.debug("_eval_comment(): creating action %s: to_user=%s, to_addr=%s, to_amnt=%s, coin=%s, fiat=%s" % (r['action'], _to_user, _to_addr, _to_amnt, r['coin'], r['fiat']))
            #lg.debug("< _eval_comment() DONE (yes)")
            return CtbAction(   atype=r['action'],
                                msg=_comment,
                                to_user=_to_user,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                coin=r['coin'],
                                fiat=r['fiat'],
                                subr=_comment.subreddit,
                                ctb=_ctb)

    # No match found
    #lg.debug("< _eval_comment() DONE (no)")
    return None

def _check_action(atype=None, state=None, coin=None, msg_id=None, created_utc=None, from_user=None, to_user=None, subr=None, ctb=None, is_pending=False):
    """
    Return True if action with given parameters
    exists in database
    """
    lg.debug("> _check_action(%s)", atype)

    mysqlcon = ctb._mysqlcon
    redditcon = ctb._redditcon

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if bool(atype) or bool(state) or bool(coin) or bool(msg_id) or bool(created_utc) or bool(from_user) or bool(to_user) or bool(subr) or bool(is_pending):
        sql += " WHERE "
        if bool(atype):
            sql_terms.append("type = '%s'" % atype)
        if bool(state):
            sql_terms.append("state = '%s'" % state)
        if bool(coin):
            sql_terms.append("coin = '%s'" % coin)
        if bool(msg_id):
            sql_terms.append("msg_id = '%s'" % msg_id)
        if bool(created_utc):
            sql_terms.append("created_utc = %s" % created_utc)
        if bool(from_user):
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if bool(to_user):
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if bool(subr):
            sql_terms.append("subreddit = '%s'" % subr)
        if bool(is_pending):
            sql_terms.append("state <> 'pending'")
        sql += ' AND '.join(sql_terms)

    try:
        lg.debug("_check_action(): <%s>", sql)
        mysqlexec = mysqlcon.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.debug("< _check_action() DONE (no)")
            return False
        else:
            lg.debug("< _check_action() DONE (yes)")
            return True
    except Exception as e:
        lg.error("_check_action(): error executing <%s>: %s", sql, str(e))
        raise

    lg.warning("< _check_action() DONE (should not get here)")
    return None


def _get_actions(atype=None, state=None, coin=None, msg_id=None, created_utc=None, from_user=None, to_user=None, subr=None, ctb=None):
    """
    Return an array of CtbAction objects from database
    with given attributes
    """
    lg.debug("> _get_actions(%s)", atype)

    mysqlcon = ctb._mysqlcon
    redditcon = ctb._redditcon

    # Build SQL query
    sql = "SELECT * FROM t_action"
    sql_terms = []
    if bool(atype) or bool(state) or bool(coin) or bool(msg_id) or bool(created_utc) or bool(from_user) or bool(to_user) or bool(subr):
        sql += " WHERE "
        if bool(atype):
            sql_terms.append("type = '%s'" % atype)
        if bool(state):
            sql_terms.append("state = '%s'" % state)
        if bool(coin):
            sql_terms.append("coin = '%s'" % coin)
        if bool(msg_id):
            sql_terms.append("msg_id = '%s'" % msg_id)
        if bool(created_utc):
            sql_terms.append("created_utc %s" % created_utc)
        if bool(from_user):
            sql_terms.append("from_user = '%s'" % from_user.lower())
        if bool(to_user):
            sql_terms.append("to_user = '%s'" % to_user.lower())
        if bool(subr):
            sql_terms.append("subreddit = '%s'" % subr)
        sql += ' AND '.join(sql_terms)

    while True:
        try:
            r = []
            lg.debug("_get_actions(): <%s>", sql)
            mysqlexec = mysqlcon.execute(sql)

            if mysqlexec.rowcount <= 0:
                lg.debug("< _get_actions() DONE (no)")
                return r

            for m in mysqlexec:
                lg.debug("_get_actions(): found %s", m['msg_link'])

                submission = redditcon.get_submission(m['msg_link'])
                if not len(submission.comments) > 0:
                    lg.warning("_get_actions(): couldn't fetch msg (deleted?) from msg_link %s", m['msg_link'])
                    continue
                msg = submission.comments[0]
                if not bool(msg.author):
                    lg.warning("_get_actions(): couldn't fetch msg.author (deleted?) from msg_link %s", m['msg_link'])
                    continue

                r.append( CtbAction(  atype=atype,
                                      msg=msg,
                                      to_user=m['to_user'],
                                      to_addr=m['to_addr'] if not bool(m['to_user']) else None,
                                      to_amnt=m['to_amnt'],
                                      coin=m['coin'],
                                      fiat=m['fiat'],
                                      subr=m['subreddit'],
                                      usd_val=m['usd_value'],
                                      ctb=ctb))

            lg.debug("< _get_actions() DONE (yes)")
            return r

        except (HTTPError, RateLimitExceeded) as e:
            lg.warning("_get_actions(): Reddit is down (%s), sleeping...", str(e))
            sleep(ctb._DEFAULT_SLEEP_TIME)
            pass
        except timeout:
            lg.warning("_get_actions(): Reddit is down (timeout), sleeping...")
            time.sleep(ctb._DEFAULT_SLEEP_TIME)
            pass
        except Exception as e:
            lg.error("_get_actions(): error executing <%s>: %s", sql, str(e))
            raise

    lg.warning("< _get_actions() DONE (should not get here)")
    return None
