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
    _TO_CURR=None

    def __init__(self, atype=None, sub_time=None, msg_id=None, msg_link=None, from_user=None, to_user=None, to_amnt=None, to_addr=None, coin=None, fiat=None):
        """
        Initialize CtbAction object with given parameters
        and run basic checks
        """
        # Assign values to fields
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

        # Do some checks
        if self._TYPE not in ['accept', 'decline', 'info', 'register', 'givetip']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")
        if self._TYPE == 'givetip':
            if not self._SUB_TIME or not self._MSG_ID or not self._MSG_LINK or not self._FROM_USER or not self._TO_AMNT:
                raise Exception("CtbAction::__init__(type=givetip): one of required values is missing")
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
            if not (bool(self._COIN) ^ bool(self._FIAT)):
                raise Exception("CtbAction::__init__(type=givetip): _COIN xor _FIAT must be set")
        if self._TYPE == 'accept':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=accept): _FROM_USER value is missing")
        if self._TYPE == 'decline':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=decline): _FROM_USER value is missing")
        if self._TYPE == 'info':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=info): _FROM_USER value is missing")
        if self._TYPE == 'register':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=register): _FROM_USER value is missing")

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
            return self._register()
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
        lg.debug("< CtbAction::_info() DONE")
        return None

    def _register(self):
        """
        Register a new user
        """
        lg.debug("> CtbAction::_register()")
        # If user exists, send user info about account
        if _check_user_exists(self._FROM_USER) != None:
            lg.debug("CtbAction::_register(): user already exists; calling _info()")
            return self._info()
        # Get new coin addresses
        lg.debug("< CtbAction::_register() DONE")
        return None

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

def _eval_message(_message, _reddit, _cc):
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
                                fiat=None)
    # No match found
    lg.debug("_eval_message(): no match found")
    lg.debug("< _eval_message() DONE")
    return None

def _eval_comment(_comment, _reddit, _cc):
    """
    Evaluate comment body and return a CtbAction
    object if successful
    """
    lg.debug("> _eval_comment(%s)", _comment.permalink)
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
                                fiat=r['fiat'])
    # No match found
    lg.debug("_eval_comment(): no match found")
    lg.debug("< _eval_comment() DONE")
    return None

