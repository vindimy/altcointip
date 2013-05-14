import ctb_user, ctb_misc

import logging, re

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

    _COIN=None          # coin for this action (for example, 'ltc')
    _FIAT=None          # fiat for this action (for example, 'usd'), if applicable

    _SUBR=None          # subreddit that originated the action, if applicable

    _MSG=None           # Reddit object pointing to originating message/comment
    _CTB=None           # CointipBot instance

    def __init__(self, atype=None, msg=None, to_user=None, to_amnt=None, to_addr=None, coin=None, fiat=None, subr=None, ctb=None):
        """
        Initialize CtbAction object with given parameters and run basic checks
        """
        self._TYPE = atype

        self._TO_AMNT = float(to_amnt) if bool(to_amnt) else None
        self._COIN = coin.lower() if bool(coin) else None
        self._FIAT = fiat.lower() if bool(fiat) else None
        self._SUBR = subr

        self._MSG = msg
        self._CTB = ctb

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

        if self._TYPE == 'givetip':
            if not bool(self._TO_AMNT):
                raise Exception("CtbAction::__init__(type=givetip): _TO_AMNT must be set")
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
            if not (bool(self._COIN) ^ bool(self._FIAT)):
                raise Exception("CtbAction::__init__(type=givetip): _COIN xor _FIAT must be set")

        lg.debug("CtbAction::__init__(atype=%s, from_user=%s)", self._TYPE, self._FROM_USER._NAME)

    def save(self, state=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save(%s)", state)

        conn = self._CTB._mysqlcon
        sql = "REPLACE INTO t_action (type, state, created_utc, from_user, to_user, to_addr, to_amnt, txid, coin, fiat, subreddit, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(sql,
                    (self._TYPE,
                     state,
                     self._MSG.created_utc,
                     self._FROM_USER._NAME.lower(),
                     self._TO_USER._NAME.lower() if bool(self._TO_USER) else None,
                     self._TO_ADDR,
                     self._TO_AMNT,
                     self._TXID,
                     self._COIN,
                     self._FIAT,
                     self._SUBR,
                     self._MSG.id,
                     self._MSG.permalink if self._TYPE == 'givetip' else None))
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception, e:
            lg.error("CtbAction::save(%s): error executing query <%s>: %s", state, sql % (
                self._TYPE,
                state,
                self._MSG.created_utc,
                self._FROM_USER._NAME.lower(),
                self._TO_USER._NAME.lower() if bool(self._TO_USER) else None,
                self._TO_ADDR,
                self._TO_AMNT,
                self._TXID,
                self._COIN,
                self._FIAT,
                self._SUBR,
                self._MSG.id,
                self._MSG.permalink if self._TYPE == 'givetip' else None), str(e))
            raise

        lg.debug("< CtbAction::save() DONE")
        return True

    def do(self):
        """
        Call appropriate function depending on action type
        """
        lg.debug("> CtbAction::do()")
        if self._TYPE == 'accept':
            return self.accept()
        if self._TYPE == 'decline':
            return self.decline()
        if self._TYPE == 'givetip':
            return self.givetip()
        if self._TYPE == 'history':
            return self._history()
        if self._TYPE == 'info':
            return self.info()
        if self._TYPE == 'register':
            return ( self.register() and self.info() )
        if self._TYPE == 'withdraw':
            return self._withdraw()
        lg.debug("< CtbAction::do() DONE")
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

        # Register as new user
        if not self._FROM_USER.is_registered():
            if not self._FROM_USER.register():
                lg.debug("CtbAction::accept(): self._FROM_USER.register() failed")
                return None

        actions = _get_actions(atype='givetip', to_user=self._FROM_USER._NAME, state='pending', ctb=self._CTB)
        if bool(actions):
            for a in actions:
                a.givetip(is_pending=True)
        else:
            msg = "I'm sorry %s, you don't have any pending tips. Perhaps they've already expired." % self._FROM_USER._NAME
            lg.debug("CtbAction::accept(): %s", msg)
            msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            self._FROM_USER.tell(subj="+accept failed", msg=msg)

        lg.debug("< CtbAction::accept() DONE")
        return None

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

        actions = _get_actions(atype='givetip', to_user=self._FROM_USER._NAME, state='pending', ctb=self._CTB)
        if bool(actions):
            for a in actions:
                # Move coins back into a._FROM_USER account
                try:
                    lg.info("CtbAction::decline(): moving %s %s from %s to %s", str(a._TO_AMNT), a._COIN, _config['reddit']['user'], a._FROM_USER._NAME.lower())
                    m = _coincon[a._COIN].move(_config['reddit']['user'], a._FROM_USER._NAME.lower(), a._TO_AMNT)
                except Exception, e:
                    lg.error("CtbAction::decline(): error: %s", str(e))
                    raise
                # Save transaction as declined
                a.save('declined')
                # Respond to tip comment
                amnt = ('%f' % a._TO_AMNT).rstrip('0').rstrip('.')
                cmnt = "* _Declined by receiver__: /u/%s -> /u/%s, __%s %s__" % (a._FROM_USER._NAME, a._TO_USER._NAME, amnt, a._COIN.upper())
                cmnt += " ^^[[help]](%s)" % (_config['reddit']['help-url'])
                lg.debug("CtbAction::decline(): " + cmnt)
                ctb_misc._reddit_reply(msg=a._MSG, txt=cmnt)

            # Notify self._FROM_USER
            msg = "Hello %s, your pending tips have been declined." % self._FROM_USER._NAME
            msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            lg.debug("CtbAction::decline(): %s")
            self._FROM_USER.tell(subj="+decline processed", msg=msg)
        else:
            msg = "I'm sorry %s, you don't have any pending tips. Perhaps they've already expired." % self._FROM_USER._NAME
            msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
            lg.debug("CtbAction::decline(): %s")
            self._FROM_USER.tell(subj="+decline failed", msg=msg)

        lg.debug("< CtbAction::decline() DONE")
        return None

    def validate(self, ignore_pending=False):
        """
        Validate an action
        """
        lg.debug("> CtbAction::validate()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _config = self._CTB._config
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if self._TYPE == 'givetip':
            # Check if _FROM_USER has registered
            if not self._FROM_USER.is_registered():
                msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._FROM_USER._NAME, self._CTB._config['reddit']['user'])
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                return False

            # Verify that _FROM_USER has coin address
            if not self._FROM_USER.get_addr(coin=self._COIN):
                msg = "I'm sorry %s, you don't seem to have a %s address." % (self._FROM_USER._NAME, self._COIN.upper())
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n *[%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                return False

            # Verify minimum transaction size
            if self._TO_AMNT < _cc[self._COIN]['txmin']:
                msg = "I'm sorry %s, your tip of %f %s is below minimum (%f)." % (self._FROM_USER._NAME, self._TO_AMNT, self._COIN.upper(), _cc[self._COIN]['txmin'])
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n *[%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                return False

            # Verify balance
            if not self._FROM_USER.get_balance(coin=self._COIN, kind='tip') >= self._TO_AMNT:
                msg = "I'm sorry, your balance of %f %s is too small (there's a %f network transaction fee)." % (balance_avail, self._COIN.upper(), _cc[self._COIN]['txfee'])
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n *[%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                return False

            # Check if _TO_USER has any pending tips from _FROM_USER
            if (bool(self._TO_USER)) and not ignore_pending:
                if _check_action(atype='givetip', state='pending', to_user=self._TO_USER._NAME, from_user=self._FROM_USER._NAME, ctb=self._CTB):
                    # Send notice to _FROM_USER
                    msg = "I'm sorry, /u/%s already has a pending tip from you. Please wait until he/she accepts or declines it." % (self._TO_USER._NAME)
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    msg += "\n *[%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
                    return False

            # Check if _TO_USER has registered, if applicable
            if (bool(self._TO_USER)) and not self._TO_USER.is_registered():
                # _TO_USER not registered:
                # - move tip into pending account
                # - save action as 'pending'
                # - notify _TO_USER to accept tip

                # Move money into pending account
                try:
                    lg.info("CtbAction::validate(): moving %s %s from %s to %s", str(self._TO_AMNT), self._COIN, self._FROM_USER._NAME.lower(), _config['reddit']['user'])
                    m = _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), _config['reddit']['user'], self._TO_AMNT)
                except Exception, e:
                    lg.error("CtbAction::validate(): error: %s", str(e))
                    raise

                # Save action as pending
                self.save('pending')

                # Send notice to _FROM_USER
                msg = "Hey %s, /u/%s doesn't have an account with tip bot yet. I'll tell him/her to register and +accept the tip." % (self._FROM_USER._NAME, self._TO_USER._NAME)
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+givetip pending", msg=msg)

                # Send notice to _TO_USER
                msg = "Hey %s, /u/%s sent you a __%f %s__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to=%s&subject=accept&message=%%2Baccept)__ to claim it. "
                msg += "Reply with __[+decline](http://www.reddit.com/message/compose?to=%s&subject=decline&message=%%2Bdecline)__ to decline it."
                msg = msg % (self._TO_USER._NAME, self._FROM_USER._NAME, self._TO_AMNT, self._COIN.upper(), self._CTB._config['reddit']['user'], self._CTB._config['reddit']['user'])
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._TO_USER.tell(subj="+givetip pending", msg=msg)

                # Action saved as 'pending', return false to avoid processing it
                return False

            # Validate _TO_ADDR, if applicable
            if bool(self._TO_ADDR):
                addr_valid = _coincon[self._COIN].validateaddress(self._TO_ADDR)
                if not addr_valid['isvalid']:
                    msg = "I'm sorry, __%s__ address __%s__ appears to be invalid (is there a typo?)." % (self._COIN.upper(), self._TO_ADDR)
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    msg += "\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    self._FROM_USER.tell(subj="+givetip failed", msg=msg)
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

        # Validate action
        if not self.validate(ignore_pending=is_pending):
            # Couldn't validate action, returning
            return False

        # Check if action has been processed
        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, ctb=self._CTB, ignore_pending=is_pending)):
            # Found action in database, returning
            lg.warning("CtbAction::givetip(): duplicate action (msg_id=%s, created_utc=%s)", self._MSG.id, self._MSG.created_utc)
            return False

        if bool(self._TO_USER):
            # Process tip to user

            try:
                if is_pending:
                    lg.debug("CtbAction::givetip(): sending %f %s from %s to %s...", self._TO_AMNT, self._COIN.upper(), _config['reddit']['user'], self._TO_ADDR)
                    self._TXID = _coincon[self._COIN].move(_config['reddit']['user'], self._TO_USER._NAME.lower(), self._TO_AMNT, _cc[self._COIN]['minconf']['tip'])
                else:
                    lg.debug("CtbAction::givetip(): sending %f %s from %s to %s...", self._TO_AMNT, self._COIN.upper(), self._FROM_USER._NAME.lower(), self._TO_ADDR)
                    self._TXID = _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), self._TO_USER._NAME.lower(), self._TO_AMNT, _cc[self._COIN]['minconf']['tip'])
            except Exception, e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%f %s__ to /u/%s has failed to process." % (self._FROM_USER._NAME, self._TO_AMNT, self._COIN.upper(), self._TO_USER._NAME)
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
                msg = "Hey %s, you have received a __%f %s__ tip from /u/%s." % (self._TO_USER._NAME, self._TO_AMNT, self._COIN.upper(), self._FROM_USER._NAME)
                lg.debug("CtbAction::givetip(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._TO_USER.tell(subj="+givetip received", msg=msg)

                # Post verification comment
                amnt = ('%f' % self._TO_AMNT).rstrip('0').rstrip('.')
                cmnt = "* __[Verified]__: /u/%s -> /u/%s, __%s %s__" % (self._FROM_USER._NAME, self._TO_USER._NAME, amnt, self._COIN.upper())
                lg.debug("CtbAction::givetip(): " + cmnt)
                cmnt += " ^^[[help]](%s)" % (_config['reddit']['help-url'])
                ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt)

            except Exception, e:
                # Couldn't post to Reddit
                lg.error("CtbAction::givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::givetip() DONE")
            return True

        elif bool(self._TO_ADDR):
            # Process tip to address

            try:
                lg.debug("CtbAction::givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN, self._TO_ADDR)
                if bool(_cc[self._COIN]['walletpassphrase']):
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 1)
                self._TXID = _coincon[self._COIN].sendfrom(self._FROM_USER._NAME.lower(), self._TO_ADDR, self._TO_AMNT, _cc[self._COIN]['minconf']['withdraw'])

            except Exception, e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of %f %s to %s has failed to process." % (self._FROM_USER._NAME, self._TO_AMNT, self._COIN.upper(), self._TO_ADDR)
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
                amnt = ('%f' % self._TO_AMNT).rstrip('0').rstrip('.')
                cmnt = "* __[Verified](%s)__: /u/%s -> [%s](%s), __%s %s__" % (ex['transaction'] + self._TXID, self._FROM_USER._NAME, self._TO_ADDR, ex['address'] + self._TO_ADDR, amnt, self._COIN.upper())
                lg.debug("CtbAction::givetip(): " + cmnt)
                cmnt += " ^^[[help]](%s)" % (_config['reddit']['help-url'])
                ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt)
            except Exception, e:
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

        # Check if user exists
        if not self._FROM_USER.is_registered():
            msg = "I'm sorry, we've never met. "
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
                coininfo['tbalance'] = _coincon[c].getbalance(self._FROM_USER._NAME.lower(), _cc[c]['minconf']['tip'])
                coininfo['wbalance'] = _coincon[c].getbalance(self._FROM_USER._NAME.lower(), _cc[c]['minconf']['withdraw'])
                coininfo['ubalance'] = _coincon[c].getbalance(self._FROM_USER._NAME.lower(), 0)
                info.append(coininfo)
            except Exception, e:
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
        msg = "Hello %s! Here's your account info.\n\n" % self._FROM_USER._NAME
        msg += "coin|address|balance (tip)|balance (withdraw)|balance (unconfirmed)\n:---|:---|:--:|:--:|:--:\n"
        for i in info:
            tbalance_str = ('%f' % i['tbalance']).rstrip('0').rstrip('.')
            wbalance_str = ('%f' % i['wbalance']).rstrip('0').rstrip('.')
            ubalance_str = ('%f' % (i['ubalance'] - i['tbalance'])).rstrip('0').rstrip('.')
            address_str = '[%s](' + _cc[i['coin']]['explorer']['address'] + '%s)'
            address_str_fmtd = address_str % (i['address'], i['address'])
            address_qr_str = '&nbsp;^^[[qr]](' + _config['misc']['qr-service-url'] + '%s%%3A%s)'
            address_qr_str_fmtd = address_qr_str % (_cc[i['coin']]['name'], i['address'])
            msg += '__' + i['coin'] + '__' + '|' + address_str_fmtd + address_qr_str_fmtd + '|__' + tbalance_str + "__|" + wbalance_str + "|" + ubalance_str + "\n"
        msg += "\nUse addresses above to deposit coins into your account."
        msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])

        # Send info message
        self._FROM_USER.tell(subj="+info", msg=msg)

        lg.debug("< CtbAction::info() DONE")
        return True

    def register(self):
        """
        Register a new user
        """
        lg.debug("> CtbAction::register()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon

        # If user exists, do nothing
        if self._FROM_USER.is_registered():
            lg.debug("CtbAction::register(%s): user already exists; ignoring request", self._FROM_USER._NAME)
            return True

        result = self._FROM_USER.register()

        lg.debug("< CtbAction::register() DONE")
        return result


def _eval_message(_message, _ctb):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    lg.debug("> _eval_message()")

    # rlist is a list of regular expressions to test _message against
    #   'regex': regular expression
    #   'action': action type
    #   'coin': unit of cryptocurrency, if applicable
    #   'rg-amount': group number to retrieve amount, if applicable
    #   'rg-address': group number to retrieve coin address, if applicable
    rlist = [
            {'regex':      '(\\+)(register)',
             'action':     'register',
             'rg-amount':  -1,
             'rg-address': -1,
             'coin':       None},
            {'regex':      '(\\+)(accept)',
             'action':     'accept',
             'rg-amount':  -1,
             'rg-address': -1,
             'coin':       None},
            {'regex':      '(\\+)(decline)',
             'action':     'decline',
             'rg-amount':  -1,
             'rg-address': -1,
             'coin':       None},
            {'regex':      '(\\+)(history)',
             'action':     'history',
             'rg-amount':  -1,
             'rg-address': -1,
             'coin':       None},
            {'regex':      '(\\+)(info)',
             'action':     'info',
             'rg-amount':  -1,
             'rg-address': -1,
             'coin':       None}
            ]

    # Add regex for each configured cryptocoin
    _cc = _ctb._config['cc']
    for c in _cc:
        if _cc[c]['enabled']:
            rlist.append(
                    # +withdraw ADDR 0.25 units
                    {'regex':      '(\\+)' + '(withdraw)' + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':     'withdraw',
                     'coin':       _cc[c]['unit'],
                     'rg-amount':  6,
                     'rg-address': 4})

    # Do the matching
    for r in rlist:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("matching '%s' with '%s'", _message.body, r['regex'])
        m = rg.search(_message.body)

        if bool(m):
            # Match found
            lg.debug("_eval_message(): match found (type %s)", r['action'])

            # Extract matched fields into variables
            _to_addr = m.group(r['rg-address']) if r['rg-address'] > 0 else None
            _to_amnt = m.group(r['rg-amount']) if r['rg-amount'] > 0 else None

            # Return CtbAction instance with given variables
            lg.debug("< _eval_message() DONE")
            return CtbAction(   atype=r['action'],
                                msg=_message,
                                to_user=None,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                coin=r['coin'],
                                fiat=None,
                                ctb=_ctb)

    # No match found
    lg.debug("< _eval_message() DONE (no)")
    return None

def _eval_comment(_comment, _ctb):
    """
    Evaluate comment body and return a CtbAction
    object if successful
    """
    lg.debug("> _eval_comment(%s)", _comment.permalink)

    _cc = _ctb._config['cc']

    # rlist is a list of regular expressions to test _comment against
    #   'regex': regular expression
    #   'action': action type
    #   'rg-to-user': group number to retrieve tip receiver username
    #   'rg-amount': group number to retrieve tip amount
    #   'rg-address': group number to retrieve tip receiver coin address
    #   'coin': unit of cryptocurrency
    rlist = []

    for c in _cc:
        if _cc[c]['enabled']:
            rlist.append(
            # +givetip ADDR 0.25 units
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  -1,
             'rg-amount':   6,
             'rg-address':  4,
             'coin':        _cc[c]['unit'],
             'fiat':        None})
            rlist.append(
            # +givetip 0.25 units
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  -1,
             'rg-amount':   4,
             'rg-address':  -1,
             'coin':        _cc[c]['unit'],
             'fiat':        None})
            rlist.append(
            # +givetip @user 0.25 units
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + '(@\w+)' + '(\\s+)' + _ctb._config['regex']['amount'] + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  4,
             'rg-amount':   6,
             'rg-address':  -1,
             'coin':        _cc[c]['unit'],
             'fiat':        None})

    # Do the matching
    for r in rlist:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("_eval_comment(): matching '%s' using <%s>", _comment.body, r['regex'])
        m = rg.search(_comment.body)

        if bool(m):
            # Match found
            lg.debug("_eval_comment(): match found (type givetip)")

            # Extract matched fields into variables
            _to_user = m.group(r['rg-to-user'])[1:] if r['rg-to-user'] > 0 else None
            _to_addr = m.group(r['rg-address']) if r['rg-address'] > 0 else None
            _to_amnt = m.group(r['rg-amount']) if r['rg-amount'] > 0 else None

            # If no destination mentioned, find parent submission's author
            if not bool(_to_user) and not bool(_to_addr):
                # set _to_user to author of parent comment
                r = ctb_misc._reddit_get_parent_author(_comment, _ctb._redditcon)
                _to_user = r.name
                _to_user_obj = ctb_user.CtbUser(name=r.name, redditobj=r, ctb=_ctb)

            # Check if from_user == to_user
            if _comment.author.name.lower() == _to_user.lower():
                lg.warning("_eval_comment(%s): _comment.author.name == _to_user, ignoring comment", _comment.author.name)
                return None

            # Return CtbAction instance with given variables
            lg.debug("_eval_comment(): creating action givetip: msg.id=%s, to=%s, to=%s, to=%s, coin=%s, fiat=%s" % (_comment.id, _to_user, _to_addr, _to_amnt, r['coin'], r['fiat']))
            lg.debug("< _eval_comment() DONE")
            return CtbAction(   atype='givetip',
                                msg=_comment,
                                to_user=_to_user,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                coin=r['coin'],
                                fiat=r['fiat'],
                                subr=_comment.subreddit,
                                ctb=_ctb)

    # No match found
    lg.debug("< _eval_comment() DONE (no)")
    return None

def _check_action(atype=None, state=None, coin=None, msg_id=None, created_utc=None, from_user=None, to_user=None, subr=None, ctb=None, ignore_pending=False):
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
    if bool(atype) or bool(state) or bool(coin) or bool(msg_id) or bool(created_utc) or bool(from_user) or bool(to_user) or bool(subr) or bool(ignore_pending):
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
        if bool(ignore_pending):
            sql_terms.append("state <> 'pending'")
        sql += ' AND '.join(sql_terms)

    try:
        mysqlexec = mysqlcon.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.debug("< _check_action() DONE (no)")
            return False
        else:
            lg.debug("< _check_action() DONE (yes)")
            return True
    except Exception, e:
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

    r = []
    try:
        mysqlexec = mysqlcon.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.debug("< _get_actions() DONE (no)")
            return r
        for m in mysqlexec:
            msg = redditcon.get_submission(m['msg_link']).comments[0]
            r.append( CtbAction(  atype=atype,
                                  msg=msg,
                                  to_user=m['to_user'],
                                  to_addr=m['to_addr'] if not bool(m['to_user']) else None,
                                  to_amnt=m['to_amnt'],
                                  coin=m['coin'],
                                  fiat=m['fiat'],
                                  subr=m['subreddit'],
                                  ctb=ctb))
        lg.debug("< _get_actions() DONE (yes)")
        return r
    except Exception, e:
        lg.error("_get_actions(): error executing <%s>: %s", sql, str(e))
        raise

    lg.debug("< _get_actions() DONE (should not get here)")
    return None
