import ctb_misc

import logging, re
from urllib2 import HTTPError

lg = logging.getLogger('cointipbot')

class CtbAction(object):
    """
    Action class for cointip bot
    """

    _TYPE=None
    _STATE=None
    _ERR_MSG=None

    _FROM_USER=None
    _FROM_ADDR=None
    _TO_USER=None
    _TO_AMNT=None
    _TO_ADDR=None
    _TXID=None

    _COIN=None
    _FIAT=None

    _MSG=None
    _CTB=None

    def __init__(self, atype=None, msg=None, to_user=None, to_amnt=None, to_addr=None, coin=None, fiat=None, ctb=None):
        """
        Initialize CtbAction object with given parameters
        and run basic checks
        """
        # Action properties
        self._TYPE=atype
        self._TO_USER=to_user
        self._TO_AMNT=float(to_amnt) if bool(to_amnt) else None
        self._TO_ADDR=to_addr
        self._COIN=coin.lower() if bool(coin) else None
        self._FIAT=fiat
        # Reference to Reddit message/comment
        self._MSG=msg
        # Reference to CointipBot class
        self._CTB=ctb

        # Do some checks
        if not bool(self._TYPE) or self._TYPE not in ['accept', 'decline', 'info', 'register', 'givetip']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")

        if not bool(self._CTB):
            raise Exception("CtbAction::__init__(type=%s): no reference to CointipBot", self._TYPE)

        if not bool(self._MSG):
            raise Exception("CtbAction::__init__(type=%s): no reference to Reddit message/comment", self._TYPE)

        if self._TYPE == 'givetip':
            if not bool(self._MSG) or not bool(self._TO_AMNT):
                raise Exception("CtbAction::__init__(type=givetip): one of required values is missing")
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
            if not (bool(self._COIN) ^ bool(self._FIAT)):
                raise Exception("CtbAction::__init__(type=givetip): _COIN xor _FIAT must be set")

        # Set some helpful properties
        self._FROM_USER = self._MSG.author

    def save(self, state=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save(%s)", state)

        conn = self._CTB._mysqlcon
        sql = "REPLACE INTO t_action (type, state, created_utc, from_user, from_addr, to_user, to_addr, to_amnt, txid, coin, fiat, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(sql,
                    (self._TYPE,
                     state,
                     self._MSG.created_utc,
                     self._FROM_USER.name.lower(),
                     self._FROM_ADDR,
                     self._TO_USER.name.lower() if bool(self._TO_USER) else None,
                     self._TO_ADDR,
                     self._TO_AMNT,
                     self._TXID,
                     self._COIN,
                     self._FIAT,
                     self._MSG.id,
                     self._MSG.permalink if self._TYPE == 'givetip' else None))
            if mysqlexec.rowcount <= 0:
                raise Exception("query didn't affect any rows")
        except Exception, e:
            lg.error("CtbAction::save(%s): error executing query <%s>: %s", state, sql % (
                self._TYPE,
                state,
                self._MSG.created_utc,
                self._FROM_USER.name.lower(),
                self._FROM_ADDR,
                self._TO_USER.name.lower() if bool(self._TO_USER) else None,
                self._TO_ADDR,
                self._TO_AMNT,
                self._TXID,
                self._COIN,
                self._FIAT,
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
            return self._accept()
        if self._TYPE == 'decline':
            return self._decline()
        if self._TYPE == 'givetip':
            return self._givetip()
        if self._TYPE == 'info':
            return self._info()
        if self._TYPE == 'register':
            if self._register():
                return self._info()
        lg.debug("< CtbAction::do() DONE")
        return None

    def _accept(self):
        """
        Accept pending tip
        """
        lg.debug("> CtbAction::_accept()")
        lg.debug("< CtbAction::_accept() DONE")
        return None

    def _decline(self):
        """
        Decline pending tip
        """
        lg.debug("> CtbAction::_decline()")
        lg.debug("< CtbAction::_decline() DONE")
        return None

    def _validate(self):
        """
        Validate an action
        """
        lg.debug("> CtbAction::_validate()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        if self._TYPE == 'givetip':
            # Check if _FROM_USER has registered
            if not ctb_misc._check_user_exists(self._FROM_USER.name, _mysqlcon):
                msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._FROM_USER.name, self._CTB._config['reddit-user'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)
                return False

            # Verify that _FROM_USER has coin address
            sql = "SELECT address from t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER.name.lower(), self._COIN)
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                msg = "I'm sorry %s, you don't seem to have %s address." % (self._FROM_USER.name, self._COIN.upper())
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)
                return False
            else:
                self._FROM_ADDR = mysqlrow['address']

            # Verify minimum transaction size
            if self._TO_AMNT < _cc[self._COIN]['txmin']:
                msg = "I'm sorry %s, your tip of %f %s is below minimum (%f)." % (self._FROM_USER.name, self._TO_AMNT, self._COIN.upper(), _cc[self._COIN]['txmin'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)
                return False

            # Verify balance
            balance_avail = _coincon[self._COIN].getbalance(self._FROM_USER.name.lower(), _cc[self._COIN]['minconf'])
            if not balance_avail >= self._TO_AMNT + _cc[self._COIN]['txfee']:
                msg = "I'm sorry, your balance of %f %s is too small (there's a %f network transaction fee)." % (balance_avail, self._COIN.upper(), _cc[self._COIN]['txfee'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)
                return False

            # Check if _TO_USER has registered
            if (bool(self._TO_USER)):
                if not ctb_misc._check_user_exists(self._TO_USER, _mysqlcon):
                    # _TO_USER not registered, save action as pending
                    self.save('pending')
                    # Send notice to _FROM_USER
                    msg = "Hey %s, /u/%s doesn't have an account with tip bot yet. I'll tell him/her to register and +accept the tip." % (self._FROM_USER.name, self._TO_USER.name)
                    lg.debug("CtbAction::_validate(): " + msg)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip pending acceptance", msg)
                    # Send notice to _TO_USER
                    msg = "Hey %s, /u/%s sent you a __%f %s__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Baccept)__ to claim it."
                    msg = msg % (self._TO_USER.name, self._FROM_USER.name, self._TO_AMNT, self._COIN.upper(), self._CTB._config['reddit-user'])
                    lg.debug("CtbAction::_validate(): " + msg)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip pending acceptance", msg)
                    return False

            if bool(self._TO_USER):
                # get _TO_USER's address
                sql = "SELECT address from t_addrs WHERE username = '%s' AND coin = '%s'" % (self._TO_USER.name.lower(), self._COIN)
                mysqlrow = _mysqlcon.execute(sql).fetchone()
                if mysqlrow == None:
                    # Couldn't find _TO_USER's address

                    # Send notice to _FROM_USER
                    msg = "I'm sorry, %s doesn't have a %s address registered. I'll tell him/her to get one." % (self._TO_USER.name, self._COIN.upper())
                    lg.debug("CtbAction::_validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)

                    # Send notice to _TO_USER
                    msg = "Hey %s, /u/%s tried to send you a %f %s tip, but you don't have a %s address registered."
                    msg = msg % (self._TO_USER.name, self._FROM_USER.name, self._TO_AMNT, self._COIN.upper(), self._COIN.upper())
                    lg.debug("CtbAction::_validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip failed", msg)

                    # Save transaction as failed
                    self.save('failed')
                    return False

                self._TO_ADDR = mysqlrow['address']

            # Validate _TO_ADDR
            addr_valid = _coincon[self._COIN].validateaddress(self._TO_ADDR)
            if not addr_valid['isvalid']:
                msg = "I'm sorry, __%s__ address __%s__ appears to be invalid (is there a typo?)." % (self._COIN.upper(), self._TO_ADDR)
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)
                return False

            if bool(self._TO_USER):
                # Ensure _TO_ADDR belongs to _TO_USER
                if not addr_valid['account'].lower() == self._TO_USER.name.lower():
                    lg.error("CtbAction::_validate(): %s doesn't think address %s belongs to %s" % (self._COIN, self._TO_ADDR, self._TO_USER.name))
                    return False

        # Action is valid
        lg.debug("< CtbAction::_validate() DONE")
        return True

    def _givetip(self):
        """
        Initiate tip
        """
        lg.debug("> CtbAction::_givetip()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        # Validate action
        if not self._validate():
            # Couldn't validate action, returning
            return False

        # Check if action has been processed
        if bool(_load_action(type=self._TYPE, msg_id=self._MSG.id, created_utc=self._MSG.created_utc, _ctb=self._CTB)):
            # Found action in database, returning
            lg.warning("CtbAction::_givetip(): action already in database; ignoring")
            return False

        if bool(self._TO_USER):
            # Process tip to user

            try:
                lg.debug("CtbAction::_givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN.upper(), self._TO_ADDR)
                if bool(_cc[self._COIN]['walletpassphrase']):
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 10)
                self._TXID = _coincon[self._COIN].sendfrom(self._FROM_USER.name.lower(), self._TO_ADDR, self._TO_AMNT, _cc[self._COIN]['minconf'])
            except Exception, e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%f %s__ to /u/%s has failed to process." % (self._FROM_USER.name, self._TO_AMNT, self._COIN.upper(), self._TO_USER.name)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)

                # Log error
                lg.error("CtbAction::_givetip(): tx of %f %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN.upper(), self._FROM_ADDR, self._TO_ADDR, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Send confirmation to _TO_USER
                msg = "Hey %s, you have received a __%f %s__ tip from /u/%s." % (self._TO_USER.name, self._TO_AMNT, self._COIN.upper(), self._FROM_USER.name)
                lg.debug("CtbAction::_givetip(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                msg += "\n* [transaction details](%s)" % (_cc[self._COIN]['explorer']['transaction'] + tx)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip succeeded", msg)

                # Post verification comment
                amnt = ('%f' % self._TO_AMNT).rstrip('0').rstrip('.')
                cmnt = "* __[Verified](%s)__: /u/%s -> /u/%s, __%s %s__" % (_cc[self._COIN]['explorer']['transaction'] + tx, self._FROM_USER.name, self._TO_USER.name, amnt, self._COIN.upper())
                lg.debug("CtbAction::_givetip(): " + cmnt)
                ctb_misc._reddit_say(_redditcon, self._MSG, None, None, cmnt)
            except Exception, e:
                # Couldn't post to Reddit
                lg.error("CtbAction::_givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::_givetip() DONE")
            return True

        elif bool(self._TO_ADDR):
            # Process tip to address

            try:
                lg.debug("CtbAction::_givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN, self._TO_ADDR)
                if bool(_cc[self._COIN]['walletpassphrase']):
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 10)
                self._TXID = _coincon[self._COIN].sendfrom(self._FROM_USER.name.lower(), self._TO_ADDR, self._TO_AMNT, _cc[self._COIN]['minconf'])
            except Exception, e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of %f %s to %s has failed to process." % (self._FROM_USER.name, self._TO_AMNT, self._COIN.upper(), self._TO_ADDR)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip failed", msg)

                # Log error
                lg.error("CtbAction::_givetip(): tx of %f %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN, self._FROM_ADDR, self._TO_ADDR, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Post verification comment
                ex = _cc[self._COIN]['explorer']
                amnt = ('%f' % self._TO_AMNT).rstrip('0').rstrip('.')
                cmnt = "* __[Verified](%s)__: /u/%s -> [%s](%s), __%s %s__" % (ex['transaction'] + tx, self._FROM_USER.name, self._TO_ADDR, ex['address'] + self._TO_ADDR, amnt, self._COIN.upper())
                lg.debug("CtbAction::_givetip(): " + cmnt)
                ctb_misc._reddit_say(_redditcon, self._MSG, None, None, cmnt)
            except Exception, e:
                # Couldn't post to Reddit
                lg.error("CtbAction::_givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::_givetip() DONE")
            return True

        lg.debug("< CtbAction::_givetip() DONE")
        return None

    def _info(self):
        """
        Send user info about account
        """
        lg.debug("> CtbAction::_info()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon
        _cc = self._CTB._config['cc']
        _redditcon = self._CTB._redditcon

        # Check if user exists
        if not ctb_misc._check_user_exists(self._FROM_USER.name, _mysqlcon):
            msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._FROM_USER.name, self._CTB._config['reddit-user'])
            ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+info failed", msg)
            return False

        # Gather data for info message
        info = []
        for c in _coincon:
            coin_info = {}
            coin_info['coin'] = c
            try:
                coin_info['balance'] = _coincon[c].getbalance(self._FROM_USER.name.lower(), _cc[c]['minconf'])
                coin_info['ubalance'] = _coincon[c].getbalance(self._FROM_USER.name.lower(), 0)
                info.append(coin_info)
            except Exception, e:
                lg.error("CtbAction::_info(%s): error retrieving %s coin_info: %s", self._FROM_USER.name, c, str(e))
                raise

        # Get coin addresses from MySQL
        for i in info:
            sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER.name.lower(), i['coin'])
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                raise Exception("CtbAction::_info(%s): no result from <%s>" % (self._FROM_USER.name, sql))
            i['address'] = mysqlrow['address']

        # Format info message
        msg = "Hello %s! Here's your account info.\n\n" % self._FROM_USER.name
        msg += "coin|address|balance|unconfirmed\n:---|:---|---:|---:\n"
        for i in info:
            balance_str = ('%f' % i['balance']).rstrip('0').rstrip('.')
            ubalance_str = ('%f' % (i['ubalance'] - i['balance'])).rstrip('0').rstrip('.')
            address_str = '[%s](' + _cc[i['coin']]['explorer']['address'] + '%s)'
            address_str_fmtd = address_str % (i['address'], i['address'])
            msg += i['coin'] + '|' + address_str_fmtd + '|__' + balance_str + "__|" + ubalance_str + "\n"
        msg += "\nUse addresses above to deposit coins into your account."

        # Send info message
        try:
            ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+info", msg)
        except Exception, e:
            lg.error("CtbAction::_info(%s): error sending message", self._FROM_USER.name)
            raise

        lg.debug("< CtbAction::_info() DONE")
        return True

    def _register(self):
        """
        Register a new user
        """
        lg.debug("> CtbAction::_register()")

        _mysqlcon = self._CTB._mysqlcon
        _coincon = self._CTB._coincon

        # If user exists, do nothing
        if ctb_misc._check_user_exists(self._FROM_USER.name, _mysqlcon):
            lg.debug("CtbAction::_register(%s): user already exists; ignoring request", self._FROM_USER.name)
            return True

        # Add user to database
        try:
            sql_adduser = "INSERT INTO t_users (username) VALUES ('%s')" % self._FROM_USER.name.lower()
            mysqlexec = _mysqlcon.execute(sql_adduser)
            if mysqlexec.rowcount <= 0:
                lg.error("CtbAction::_register(%s): rowcount <= 0 while executing <%s>", self._FROM_USER.name, sql_adduser)
                return False
        except Exception, e:
            lg.error("CtbAction::_register(%s): exception while executing <%s>: %s", self._FROM_USER.name, sql_adduser, str(e))
            raise

        # Get new coin addresses
        new_addrs = {}
        for c in _coincon:
            try:
                # Generate new address for user
                new_addrs[c] = _coincon[c].getaccountaddress(self._FROM_USER.name.lower())
                if not bool(new_addrs[c]):
                    new_addrs[c] = _coincon[c].getnewaddress(self._FROM_USER.name.lower())
                lg.debug("CtbAction::_register(%s): got %s address %s", self._FROM_USER.name, c, new_addrs[c])
            except Exception, e:
                lg.error("CtbAction::_register(%s): error getting %s address: %s", self._FROM_USER.name, c, str(e))
                ctb_misc._delete_user(self._FROM_USER.name, _mysqlcon)
                raise

        # Add coin addresses to database
        for c in new_addrs:
            try:
                sql_addr = "REPLACE INTO t_addrs (username, coin, address) VALUES ('%s', '%s', '%s')" % (self._FROM_USER.name.lower(), c, new_addrs[c])
                mysqlexec = _mysqlcon.execute(sql_addr)
                if mysqlexec.rowcount <= 0:
                    # Undo change to database
                    ctb_misc._delete_user(self._FROM_USER.name, _mysqlcon)
                    raise Exception("CtbAction::_register(%s): rowcount <= 0 while executing <%s>" % (self._FROM_USER.name, sql_addr))
            except Exception, e:
                # Undo change to database
                ctb_misc._delete_user(self._FROM_USER.name, _mysqlcon)
                raise

        lg.debug("< CtbAction::_register() DONE")
        return True


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
        if m:
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
    lg.debug("_eval_message(): no match found")
    lg.debug("< _eval_message() DONE")
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
            # If to_user is mentioned, fetch it
            _to_user_obj = None
            if (bool(_to_user)):
                _to_user_obj = ctb_misc._get_reddit_user(_to_user, _ctb._redditcon)
                if not bool(_to_user_obj):
                    lg.warning("_eval_comment(): couldn't fetch reddit user %s, _to_user")
                    return None
            # Check if from_user == to_user
            if bool(_to_user) and _comment.author.name.lower() == _to_user.lower():
                lg.warning("_eval_comment(): _comment.author.name == _to_user, ignoring comment")
                return None
            # If destination not mentioned, find parent submission's author
            if not bool(_to_user) and not bool(_to_addr):
                # set _to_user to author of parent comment
                _to_user = ctb_misc._get_parent_comment_author(_comment, _ctb._redditcon).name
            # Return CtbAction instance with given variables
            lg.debug("_eval_comment(): creating action givetip: msg.id=%s, to=%s, to=%s, to=%s, coin=%s, fiat=%s" % (_comment.id, _to_user, _to_addr, _to_amnt, r['coin'], r['fiat']))
            lg.debug("< _eval_comment() DONE")
            return CtbAction(   atype='givetip',
                                msg=_comment,
                                to_user=_to_user_obj,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                coin=r['coin'],
                                fiat=r['fiat'],
                                ctb=_ctb)
    # No match found
    lg.debug("_eval_comment(): no match found")
    lg.debug("< _eval_comment() DONE")
    return None

def _load_action(type=None, msg_id=None, created_utc=None, _ctb=None):
    """
    Query database and return CtbAction object if found
    """
    lg.debug("> _load_action()")

    conn = _ctb._mysqlcon
    reddit = _ctb._redditcon

    sql = "SELECT * FROM t_action WHERE type = %s AND msg_id = %s AND created_utc = %s"
    try:
        mysqlrow = conn.execute(sql, (type, msg_id, int(created_utc))).fetchone()
        if mysqlrow == None:
            # Action not found
            return None
        else:
            _msg = reddit.get_submission(mysqlrow['msg_link'])
            _to_user = ctb_misc._get_reddit_user(mysqlrow['to_user'], reddit) if bool(mysqlrow['to_user']) else None
            lg.debug("< _load_action() DONE")
            return CtbAction(  atype=type,
                               msg=_msg,
                               to_user=_to_user,
                               to_addr=mysqlrow['to_addr'] if not bool(mysqlrow['to_user']) else None,
                               to_amnt=mysqlrow['to_amnt'],
                               coin=mysqlrow['coin'],
                               fiat=mysqlrow['fiat'],
                               ctb=_ctb)
    except Exception, e:
        lg.error("_load_action(): error executing <%s>: %s", sql % (type, msg_id, created_utc), str(e))
        raise

    lg.debug("< _load_action() DONE (should not get here)")
    return None
