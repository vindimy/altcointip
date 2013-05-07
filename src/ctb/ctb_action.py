import logging, re

lg = logging.getLogger('cointipbot')

class CtbAction(object):
    """
    Action class for cointip bot
    """

    _TYPE=None
    _SUB_TIME=None
    _MSG_ID=None
    _MSG_LINK=None
    _FROM_USER=None
    _TO_USER=None
    _TO_AMNT=None
    _TO_ADDR=None
    _COIN=None
    _FIAT=None
    _CTB=None

    def __init__(self, atype=None, sub_time=None, msg_id=None, msg_link=None, from_user=None, to_user=None, to_amnt=None, to_addr=None, coin=None, fiat=None, ctb=None):
        """
        Initialize CtbAction object with given parameters
        and run basic checks
        """
        # Assign values to fields
        # Action properties
        self._TYPE=atype
        self._SUB_TIME=sub_time
        self._MSG_ID=msg_id
        self._MSG_LINK=msg_link
        self._FROM_USER=from_user
        self._TO_USER=to_user
        self._TO_AMNT=to_amnt
        self._TO_ADDR=to_addr
        self._COIN=coin
        self._FIAT=fiat
        # Reference to CointipBot
        self._CTB=ctb

        # Do some checks
        if not bool(self._TYPE) or self._TYPE not in ['accept', 'decline', 'info', 'register', 'givetip']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")
        if self._TYPE == 'givetip':
            if not bool(self._SUB_TIME) or not bool(self._MSG_ID) or not bool(self._MSG_LINK) or not bool(self._FROM_USER) or not bool(self._TO_AMNT):
                raise Exception("CtbAction::__init__(type=givetip): one of required values is missing")
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
            if not (bool(self._COIN) ^ bool(self._FIAT)):
                raise Exception("CtbAction::__init__(type=givetip): _COIN xor _FIAT must be set")
        if self._TYPE == 'accept':
            if not bool(self._FROM_USER):
                raise Exception("CtbAction::__init__(type=accept): _FROM_USER value is missing")
        if self._TYPE == 'decline':
            if not bool(self._FROM_USER):
                raise Exception("CtbAction::__init__(type=decline): _FROM_USER value is missing")
        if self._TYPE == 'info':
            if not bool(self._FROM_USER):
                raise Exception("CtbAction::__init__(type=info): _FROM_USER value is missing")
        if self._TYPE == 'register':
            if not bool(self._FROM_USER):
                raise Exception("CtbAction::__init__(type=register): _FROM_USER value is missing")
        if not bool(self._CTB):
            raise Exception("CtbAction::__init__(): no reference to CointipBot (self._CTB)")

        # Commit action to database
        self.save()

    def save(self):
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

    def _givetip(self):
        """
        Initiate tip
        """
        lg.debug("> CtbAction::_givetip()")
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
        if not _check_user_exists(self._FROM_USER, _mysqlcon):
            _redditcon.get_redditor(self._FROM_USER).send_message("+info", "I'm sorry, we've never met. Please +register first!")
            return False

        # Gather data for info message
        info = []
        for c in _coincon:
            coin_info = {}
            coin_info['coin'] = c
            try:
                coin_info['address'] = _coincon[c].getaccountaddress(self._FROM_USER)
                coin_info['balance'] = _coincon[c].getbalance(self._FROM_USER)
                coin_info['balance-un'] = _coincon[c].getbalance(self._FROM_USER, 0)
                info.append(coin_info)
            except Exception, e:
                lg.error("CtbAction::_info(%s): error retrieving %s coin_info: %s", self._FROM_USER, c, str(e))
                return False

        # Confirm coin addresses against MySQL
        for i in info:
            sql = "SELECT address FROM t_addrs WHERE username = '%s' AND coin = '%s'" % (self._FROM_USER, i['coin'])
            mysqlrow = _mysqlcon.execute(sql).fetchone()
            if mysqlrow == None:
                raise Exception("CtbAction::_info(%s): no results from <%s> when expecting %s", self._FROM_USER, sql, i['address'])
            addr = mysqlrow['address']
            # Compare addr to that returned by coin daemon
            if not addr == i['address']:
                raise Exception("CtbAction::_info(%s): %s addresses don't match (%s in database vs %s in coin daemon)", self._FROM_USER, i['coin'], addr, i['address'])

        # Format info message
        msg = "Hello %s! Here's your account info.\n\n" % self._FROM_USER
        msg += "coin|address|balance |balance (+unconfirmed)\n:---|:---|---:|---:\n"
        for i in info:
            balance_str = ('%f' % i['balance']).rstrip('0').rstrip('.')
            balance_un_str = ('%f' % i['balance-un']).rstrip('0').rstrip('.')
            address_str = '[%s](' + _cc[i['coin']]['explorer']['address'] + '%s)'
            address_str_fmtd = address_str % (i['address'], i['address'])
            msg += i['coin'] + '|' + address_str_fmtd + '|' + balance_str + '|' + balance_un_str + "\n"
        msg += "\nUse addresses above to deposit coins into your account."

        # Send info message
        try:
            _redditcon.get_redditor(self._FROM_USER).send_message("+info", msg)
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
        if _check_user_exists(self._FROM_USER, _mysqlcon):
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
        return None

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
                    {'regex':      '(\\+)' + '(withdraw)' + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + _cc[c]['regex']['units'],
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
                                sub_time=_message.created_utc,
                                msg_id=_message.id,
                                from_user=_message.author.name,
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
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  -1,
             'rg-amount':   6,
             'rg-address':  4,
             'coin':        _cc[c]['unit'],
             'fiat':        None})
            rlist.append(
            # +givetip 0.25 units
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  -1,
             'rg-amount':   4,
             'rg-address':  -1,
             'coin':        _cc[c]['unit'],
             'fiat':        None})
            rlist.append(
            # +givetip @user 0.25 units
            {'regex':       '(\\+)' + '(givetip)' + '(\\s+)' + '(@\w+)' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + _cc[c]['regex']['units'],
             'action':      'givetip',
             'rg-to-user':  4,
             'rg-amount':   6,
             'rg-address':  -1,
             'coin':        _cc[c]['unit'],
             'fiat':        None})
    # Do the matching
    for r in rlist:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        lg.debug("_eval_comment(): matching '%s' using <%s>", _comment.body, r['regex'])
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
                _to_user = _get_parent_comment_author(_comment, _reddit).name
            # Check if from_user == to_user
            if _comment.author.name.lower() == _to_user.lower():
                lg.debug("_eval_comment(): _comment.author.name == _to_user, ignoring comment")
                return None
            # Return CtbAction instance with given variables
            lg.debug("< _eval_comment() DONE")
            return CtbAction(   atype='givetip',
                                sub_time=_comment.created_utc,
                                msg_id=_comment.id,
                                msg_link=_comment.permalink,
                                from_user=_comment.author.name,
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

