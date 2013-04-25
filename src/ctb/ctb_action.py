import re

class CtbAction(object):
    """
    Action class for cointip bot
    """

    logger=None

    _TYPE=None
    _SUB_TIME=None
    _MSG_ID=None
    _FROM_USER=None
    _TO_USER=None
    _TO_AMNT=None
    _TO_ADDR=None
    _TO_CURR=None

    def __init__(self, logger=None, atype=None, sub_time=None, msg_id=None, from_user=None, to_user=None, to_amnt=None, to_addr=None, to_curr=None):
        """
        Initialize CtbAction object with given parameters
        and run basic checks
        """
        # Assign values to fields
        self._logger=logger
        self._TYPE=atype
        self._SUB_TIME=sub_time
        self._MSG_ID=msg_id
        self._FROM_USER=from_user
        self._TO_USER=to_user
        self._TO_AMNT=to_amnt
        self._TO_ADDR=to_addr
        self._TO_CURR=to_curr
        # Do some checks
        if self._TYPE not in ['info', 'register', 'givetip']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")
        if self._TYPE == 'givetip':
            if not self._SUB_TIME or not self._MSG_ID or not self._FROM_USER or not self._TO_AMNT or not self._TO_CURR:
                raise Exception("CtbAction::__init__(type=givetip): one of required values is missing")
            if not (bool(len(self._TO_USER)) ^ bool(len(self._TO_ADDR))):
                raise Exception("CtbAction::__init__(type=givetip): _TO_USER xor _TO_ADDR must be set")
        if self._TYPE == 'info':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=info): _FROM_USER value is missing")
        if self._TYPE == 'register':
            if not self._FROM_USER:
                raise Exception("CtbAction::__init__(type=register): _FROM_USER value is missing")

    def do(self):
        self._logger.debug("CtbAction::do()")
        return None


def _eval_message(_message, _logger):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    _logger.debug("_eval_message()")
    # rlist is a list of regular expressions to test _message against
    #   't': example text that will match
    #   'p': regular expression
    #   'x': action type
    #   'a': group number to retrieve amount
    #   'l': group number to retrieve coin address
    #   'c': group number to retrieve currency type
    rlist = [
            {'t':     '+register',
             'p':     '(\\+)(register)',
             'x':     'register',
             'a':     -1,
             'l':     -1,
             'c':     -1},
            {'t':     '+info',
             'p':     '(\\+)(info)',
             'x':     'info',
             'a':     -1,
             'l':     -1,
             'c':     -1},
            {'t':     '+withdraw 31uEbMgunupShBVTewXjtqbBv5MndwfXhb 0.25 btc|usd',
             'p':     '(\\+)' + '(withdraw)' + '(\\s+)' + '([1|3][1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|btc)',
             'x':     'withdraw',
             'a':     6,
             'l':     4,
             'c':     8},
            {'t':     '+withdraw LhTfsU9x3mL9NY8UTQRqL5CK2gHtj27eX4 0.25 ltc|usd',
             'p':     '(\\+)' + '(withdraw)' + '(\\s+)' + '(L[1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|ltc)',
             'x':     'withdraw',
             'a':     6,
             'l':     4,
             'c':     8},
            {'t':     '+withdraw PNywpYi6qMMQLTmE9f4bbM7diatb5Wvt8a 0.25 ppc|usd',
             'p':     '(\\+)' + '(withdraw)' + '(\\s+)' + '(P[1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|ppc)',
             'x':     'withdraw',
             'a':     6,
             'l':     4,
             'c':     8}
        ]
    # Do the matching
    for r in rlist:
        rg = re.compile(r['p'], re.IGNORECASE|re.DOTALL)
        _logger.debug("matching '%s' with '%s'", _message.body, r['p'])
        m = rg.search(_message.body)
        if m:
            # Match found
            _logger.debug("_eval_message(): match found (type %s)", r['x'])
            # Extract matched fields into variables
            _to_addr = m.group(r['l']) if r['l'] > 0 else None
            _to_amnt = m.group(r['a']) if r['a'] > 0 else None
            _to_curr = m.group(r['c']) if r['c'] > 0 else None
            # Return CtbAction instance with given variables
            return CtbAction(   logger=_logger,
                                atype=r['x'],
                                sub_time=_message.created_utc,
                                msg_id=_message.id,
                                from_user=_message.author.name,
                                to_user=None,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                to_curr=_to_curr)
    # No match found
    _logger.debug("_eval_message(): no match found")
    return None

def _eval_comment(_comment):
    """
    Evaluate comment body and return a CtbAction
    object if successful
    """
    # rlist is a list of regular expressions to test _comment against
    #   't': example text that will match
    #   'p': regular expression
    #   'u': group number to retrieve reddit username
    #   'a': group number to retrieve tip amount
    #   'l': group number to retrieve coin address
    #   'c': group number to retrieve currency type
    rlist = [
            {'t':     '+givetip 0.25 btc|ltc|ppc|usd',
             'p':     '(\\+)' + '(givetip)' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|btc|ltc|ppc)',
             'u':     -1,
             'a':     4,
             'l':     -1,
             'c':     6},
            {'t':     '+givetip @user 0.25 btc|ltc|ppc|usd',
             'p':     '(\\+)' + '(givetip)' + '(\\s+)' + '(@\w+)' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|btc|ltc|ppc)',
             'u':     4,
             'a':     6,
             'l':     -1,
             'c':     8},
            {'t':     '+givetip 31uEbMgunupShBVTewXjtqbBv5MndwfXhb 0.25 btc|usd',
             'p':     '(\\+)' + '(givetip)' + '(\\s+)' + '([1|3][1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|btc)',
             'u':     -1,
             'a':     6,
             'l':     4,
             'c':     8},
            {'t':     '+givetip LhTfsU9x3mL9NY8UTQRqL5CK2gHtj27eX4 0.25 ltc|usd',
             'p':     '(\\+)' + '(givetip)' + '(\\s+)' + '(L[1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|ltc)',
             'u':     -1,
             'a':     6,
             'l':     4,
             'c':     8},
            {'t':     '+givetip PNywpYi6qMMQLTmE9f4bbM7diatb5Wvt8a 0.25 ppc|usd',
             'p':     '(\\+)' + '(givetip)' + '(\\s+)' + '(P[1-9a-z]{20,40})' + '(\\s+)' + '(\\d*\\.\\d+)(?![0-9\\.])' + '(\\s+)' + '(usd|ppc)',
             'u':     -1,
             'a':     6,
             'l':     4,
             'c':     8}
        ]
    # Do the matching
    for r in rlist:
        rg = re.compile(r['p'], re.IGNORECASE|re.DOTALL)
        m = rg.search(_comment.body)
        if m:
            # Match found
            # Extract matched fields into variables
            _to_user = m.group(r['u']) if r['u'] > 0 else None
            _to_addr = m.group(r['l']) if r['l'] > 0 else None
            _to_amnt = m.group(r['a']) if r['a'] > 0 else None
            _to_curr = m.group(r['c']) if r['c'] > 0 else None
            # If destination not mentioned, find parent submission's author
            if not _to_user and not _to_addr:
                # set _to_user to author of parent comment
                _to_user = "cointipbot" #TODO
            # Check if from_user == to_user
            if _comment.author.name.lower() == _to_user.lower():
                return None
            # Return CtbAction instance with given variables
            return CtbAction(   logger=_logger,
                                atype='givetip',
                                sub_time=_coment.created_utc,
                                msg_id=_comment.id,
                                from_user=_comment.author.name,
                                to_user=_to_user,
                                to_addr=_to_addr,
                                to_amnt=_to_amnt,
                                to_curr=_to_curr)
    # No match found
    return None
