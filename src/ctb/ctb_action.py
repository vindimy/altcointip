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
        self._FROM_USER = self._MSG.author.name.lower()

    def save(self, state=None, errmsg=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save()")
        lg.debug("< CtbAction::save() DONE")
        return None

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
            if not ctb_misc._check_user_exists(self._FROM_USER, _mysqlcon):
                msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._FROM_USER, self._CTB._config['reddit-user'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)
                return False

            # Verify that _FROM_USER has coin address
            sql = "SELECT address from t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER, self._COIN)
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                msg = "I'm sorry %s, you don't seem to have %s address." % (self._FROM_USER, self._COIN.upper())
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)
                return False
            else:
                self._FROM_ADDR = mysqlrow['address']

            # Verify minimum transaction size
            if self._TO_AMNT < _cc[self._COIN]['txmin']:
                msg = "I'm sorry, your tip of %f %s is below minimum (%f)." % (self._TO_AMNT, self._COIN.upper(), _cc[self._COIN]['txmin'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)
                return False

            # Verify balance
            balance_avail = _coincon[self._COIN].getbalance(self._FROM_USER)
            if not balance_avail >= self._TO_AMNT + _cc[self._COIN]['txfee']:
                msg = "I'm sorry, your balance of %f %s is too small (there's a %f network transaction fee)." % (balance_avail, self._COIN.upper(), _cc[self._COIN]['txfee'])
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)
                return False

            if bool(self._TO_USER):
                # get _TO_USER's address
                sql = "SELECT address from t_addrs WHERE username = '%s' AND coin = '%s'" % (self._TO_USER, self._COIN)
                mysqlrow = _mysqlcon.execute(sql).fetchone()
                if mysqlrow == None:
                    # Couldn't find _TO_USER's address

                    # Send notice to _FROM_USER
                    msg = "I'm sorry, %s doesn't have a %s address registered. I'll tell him/her to get one." % (self._TO_USER, self._COIN.upper())
                    lg.debug("CtbAction::_validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)

                    # Send notice to _TO_USER
                    msg = "Hey %s, /u/%s tried to send you a %f %s tip, but you don't have a %s address registered." % (self._TO_USER, self._FROM_USER, self._TO_AMNT, self._COIN.upper(), self._COIN.upper())
                    lg.debug("CtbAction::_validate(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip", msg)

                    # Save transaction as pending
                    self.save('pending')
                    return False

                self._TO_ADDR = mysqlrow['address']

            # Validate _TO_ADDR
            addr_valid = _coincon[self._COIN].validateaddress(self._TO_ADDR)
            if not addr_valid['isvalid']:
                msg = "I'm sorry, %s address %s appears to be invalid (is there a typo?)." % (self._COIN.upper(), self._TO_ADDR)
                lg.debug("CtbAction::_validate(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)
                return False

            if bool(self._TO_USER):
                # Ensure _TO_ADDR belongs to _TO_USER
                if not addr_valid['account'].lower() == self._TO_USER.lower():
                    lg.error("CtbAction::_validate(): %s doesn't think address %s belongs to %s" % (self._COIN, self._TO_ADDR, self._TO_USER))
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
        if bool(_load_action(self._FROM_USER, self._MSG.id)):
            # Found action in database, returning
            return False

        if bool(self._TO_USER):
            # Process tip to user

            if ctb_misc._check_user_exists(self._TO_USER, _mysqlcon):
                # if _TO_USER has registered, simply process the tip

                # Process transaction
                try:
                    lg.debug("CtbAction::_givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN.upper(), self._TO_ADDR)
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 10)
                    tx = _coincon[self._COIN].sendfrom(self._FROM_USER, self._TO_ADDR, self._TO_AMNT, self._MSG.id)
                except Exception, e:
                    # Transaction failed

                    # Save transaction to database
                    self.save('failed', str(e))

                    # Log error
                    lg.error("CtbAction::_givetip(): tx of %f %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN.upper(), self._FROM_ADDR, self._TO_ADDR, str(e)))

                    # Send notice to _FROM_USER
                    msg = "Hey %s, something went wrong, and your tip of %f %s to /u/%s has failed to process." % (self._FROM_USER, self._TO_AMNT, self._COIN.upper(), self._TO_USER)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)

                    # Return
                    lg.debug("< CtbAction::_givetip() DONE")
                    return False

                # Transaction succeeded

                # Save transaction to database
                self.save('completed')

                try:
                    # Send confirmation to _TO_USER
                    msg = "Hey %s, you have received a __%f %s__ tip from /u/%s." % (self._TO_USER, self._TO_AMNT, self._COIN.upper(), self._FROM_USER)
                    lg.debug("CtbAction::_givetip(): " + msg)
                    msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                    msg += "\n* [transaction details](%s)" % (_cc[self._COIN]['explorer']['transaction'] + tx)
                    ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip", msg)

                    # Post verification comment
                    amnt = ('%f' % self._TO_AMNT).rstrip('0').rstrip('.')
                    cmnt = "* __[Verified](%s)__: /u/%s -> /u/%s, __%s %s__" % (_cc[self._COIN]['explorer']['transaction'] + tx, self._FROM_USER, self._TO_USER, amnt, self._COIN.upper())
                    lg.debug("CtbAction::_givetip(): " + cmnt)
                    ctb_misc._reddit_say(_redditcon, self._MSG, None, None, cmnt)
                except Exception, e:
                    # Couldn't post to Reddit
                    lg.error("CtbAction::_givetip(): error communicating with Reddit: %s" % str(e))
                    raise

                lg.debug("< CtbAction::_givetip() DONE")
                return True

            else:
                # if _TO_USER hasn't registered, mark tip as pending acceptance

                # Save transaction to database
                self.save('pending')

                # Send notice to _TO_USER
                msg = "Hey %s, you have received a %s tip of %f from /u/%s. To accept, reply with +accept now." % (self._TO_USER, self._COIN.upper(), self._TO_AMNT, self._FROM_USER)
                lg.debug("CtbAction::_givetip(): " + msg)
                msg += "\n\n* [+givetip comment](%s)" % (self._MSG.permalink)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._TO_USER, "+givetip", msg)

                lg.debug("< CtbAction::_givetip() DONE")
                return True

        elif bool(self._TO_ADDR):
            # Process tip to address

            try:
                lg.debug("CtbAction::_givetip(): sending %f %s to %s...", self._TO_AMNT, self._COIN, self._TO_ADDR)
                res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 10)
                tx = _coincon[self._COIN].sendfrom(self._FROM_USER, self._TO_ADDR, self._TO_AMNT, self._MSG.id)
            except Exception, e:
                # Transaction failed

                # Save transaction to database
                self.save('failed', str(e))

                # Log error
                lg.error("CtbAction::_givetip(): tx of %f %s from %s to %s failed: %s" % (self._TO_AMNT, self._COIN, self._FROM_ADDR, self._TO_ADDR, str(e)))

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of %f %s to %s has failed to process." % (self._FROM_USER, self._TO_AMNT, self._COIN.upper(), self._TO_ADDR)
                ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+givetip", msg)

                lg.debug("< CtbAction::_givetip() DONE")
                return False

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Post verification comment
                ex = _cc[self._COIN]['explorer']
                cmnt = "* [Verified](%s): /u/%s -> [%s](%s), %f %s" % (ex['transaction'] + tx, self._FROM_USER, self._TO_ADDR, ex['address'] + self._TO_ADDR, self._TO_AMNT, self._COIN.upper())
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
        if not ctb_misc._check_user_exists(self._FROM_USER, _mysqlcon):
            msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (self._FROM_USER, self._CTB._config['reddit-user'])
            ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+info", msg)
            return False

        # Gather data for info message
        info = []
        for c in _coincon:
            coin_info = {}
            coin_info['coin'] = c
            try:
                coin_info['balance'] = _coincon[c].getbalance(self._FROM_USER)
                info.append(coin_info)
            except Exception, e:
                lg.error("CtbAction::_info(%s): error retrieving %s coin_info: %s", self._FROM_USER, c, str(e))
                raise

        # Get coin addresses from MySQL
        for i in info:
            sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER, i['coin'])
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                raise Exception("CtbAction::_info(%s): no result from <%s>" % (self._FROM_USER, sql))
            i['address'] = mysqlrow['address']

        # Format info message
        msg = "Hello %s! Here's your account info.\n\n" % self._FROM_USER
        msg += "coin|address|balance\n:---|:---|---:\n"
        for i in info:
            balance_str = ('%f' % i['balance']).rstrip('0').rstrip('.')
            address_str = '[%s](' + _cc[i['coin']]['explorer']['address'] + '%s)'
            address_str_fmtd = address_str % (i['address'], i['address'])
            msg += i['coin'] + '|' + address_str_fmtd + '|' + balance_str + "\n"
        msg += "\nUse addresses above to deposit coins into your account."

        # Send info message
        try:
            ctb_misc._reddit_say(_redditcon, self._MSG, self._FROM_USER, "+info", msg)
        except Exception, e:
            lg.error("CtbAction::_info(%s): error sending message", self._FROM_USER)
            return False

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
        if ctb_misc._check_user_exists(self._FROM_USER, _mysqlcon):
            lg.debug("CtbAction::_register(%s): user already exists; ignoring request", self._FROM_USER)
            return True

        # Add user to database
        try:
            sql_adduser = "INSERT INTO t_users (username) VALUES ('%s')" % self._FROM_USER
            mysqlexec = _mysqlcon.execute(sql_adduser)
            if mysqlexec.rowcount <= 0:
                lg.error("CtbAction::_register(%s): rowcount <= 0 while executing <%s>", self._FROM_USER, sql_adduser)
                return False
        except Exception, e:
            lg.error("CtbAction::_register(%s): exception while executing <%s>: %s", self._FROM_USER, sql_adduser, str(e))
            return False

        # Get new coin addresses
        new_addrs = {}
        for c in _coincon:
            try:
                # Generate new address for user
                new_addrs[c] = _coincon[c].getaccountaddress(self._FROM_USER)
                if not bool(new_addrs[c]):
                    new_addrs[c] = _coincon[c].getnewaddress(self._FROM_USER)
                lg.debug("CtbAction::_register(%s): got %s address %s", self._FROM_USER, c, new_addrs[c])
            except Exception, e:
                lg.error("CtbAction::_register(%s): error getting %s address: %s", self._FROM_USER, c, str(e))
                _delete_user(self._FROM_USER, _mysqlcon)
                return False

        # Add coin addresses to database
        for c in new_addrs:
            try:
                sql_addr = "REPLACE INTO t_addrs (username, coin, address) VALUES ('%s', '%s', '%s')" % (self._FROM_USER, c, new_addrs[c])
                mysqlexec = _mysqlcon.execute(sql_addr)
                if mysqlexec.rowcount <= 0:
                    lg.error("CtbAction::_register(%s): rowcount <= 0 while executing <%s>", self._FROM_USER, sql_addr)
                    # Undo change to database
                    _delete_user(self._FROM_USER, _mysqlcon)
                    return False
            except Exception, e:
                lg.error("CtbAction::_register(%s): exception while executing <%s>: %s", self._FROM_USER, sql_addr, str(e))
                # Undo change to database
                _delete_user(self._FROM_USER, _mysqlcon)
                return False

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
        lg.debug("matching '%s' with '%s'", _message.body, r['regex'])
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
        if m:
            # Match found
            lg.debug("_eval_comment(): match found (type givetip)")
            # Extract matched fields into variables
            _to_user = m.group(r['rg-to-user']) if r['rg-to-user'] > 0 else None
            _to_addr = m.group(r['rg-address']) if r['rg-address'] > 0 else None
            _to_amnt = m.group(r['rg-amount']) if r['rg-amount'] > 0 else None
            # If destination not mentioned, find parent submission's author
            if not _to_user and not _to_addr:
                # set _to_user to author of parent comment
                _to_user = ctb_misc._get_parent_comment_author(_comment, _ctb._redditcon).name
            # Check if from_user == to_user
            if bool(_to_user) and _comment.author.name.lower() == _to_user.lower():
                lg.debug("_eval_comment(): _comment.author.name == _to_user, ignoring comment")
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
                                ctb=_ctb)
    # No match found
    lg.debug("_eval_comment(): no match found")
    lg.debug("< _eval_comment() DONE")
    return None

