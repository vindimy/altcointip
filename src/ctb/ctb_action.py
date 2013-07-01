import ctb_user, ctb_misc

import logging, praw, re, time
from random import randint

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
    _TO_ADDR=None       # destination cryptocoin address of 'givetip' and 'withdraw' actions, if applicable

    _COIN=None          # coin for this action (for example, 'ltc')
    _FIAT=None          # fiat for this action (for example, 'usd'), if applicable
    _COIN_VAL=None      # coin value of 'givetip' and 'withdraw' actions
    _FIAT_VAL=None      # fiat value of the 'givetip' or 'withdraw' action

    _SUBR=None          # subreddit that originated the action, if applicable

    _MSG=None           # Reddit object pointing to originating message/comment
    _CTB=None           # CointipBot instance

    def __init__(self, atype=None, msg=None, to_user=None, to_addr=None, coin=None, fiat=None, coin_val=None, fiat_val=None, subr=None, ctb=None):
        """
        Initialize CtbAction object with given parameters and run basic checks
        """
        lg.debug("> CtbAction::__init__(atype=%s, from_user=%s)", atype, msg.author.name)

        self._TYPE = atype

        self._COIN = coin.lower() if bool(coin) else None
        self._FIAT = fiat.lower() if bool(fiat) else None
        self._COIN_VAL = coin_val if bool(coin_val) else None
        self._FIAT_VAL = fiat_val if bool(fiat_val) else None

        self._MSG = msg
        self._CTB = ctb

        self._TO_ADDR = to_addr
        self._TO_USER = ctb_user.CtbUser(name=to_user, ctb=ctb) if bool(to_user) else None
        self._FROM_USER = ctb_user.CtbUser(name=msg.author.name, redditobj=msg.author, ctb=ctb) if bool(msg) else None
        self._SUBR = subr

        # Do some checks
        if not bool(self._TYPE) or self._TYPE not in ['accept', 'decline', 'history', 'info', 'register', 'givetip', 'withdraw']:
            raise Exception("CtbAction::__init__(type=?): proper type is required")
        if not bool(self._CTB):
            raise Exception("CtbAction::__init__(type=%s): no reference to CointipBot", self._TYPE)
        if not bool(self._MSG):
            raise Exception("CtbAction::__init__(type=%s): no reference to Reddit message/comment", self._TYPE)
        if self._TYPE in ['givetip', 'withdraw']:
            if not (bool(self._TO_USER) ^ bool(self._TO_ADDR)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): _TO_USER xor _TO_ADDR must be set" % (self._TYPE, self._FROM_USER._NAME))
            if not (bool(self._COIN) or bool(self._FIAT)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): _COIN or _FIAT must be set" % (self._TYPE, self._FROM_USER._NAME))
            if not (bool(self._COIN_VAL) or bool(self._FIAT_VAL)):
                raise Exception("CtbAction::__init__(atype=%s, from_user=%s): _COIN_VAL or _FIAT_VAL must be set" % (self._TYPE, self._FROM_USER._NAME))

        # Convert _COIN_VAL and _FIAT_VAL to float, if necesary
        if bool(self._COIN_VAL) and type(self._COIN_VAL) == unicode and self._COIN_VAL.replace('.', '').isnumeric():
            self._COIN_VAL = float(self._COIN_VAL)
        if bool(self._FIAT_VAL) and type(self._FIAT_VAL) == unicode and self._FIAT_VAL.replace('.', '').isnumeric():
            self._FIAT_VAL = float(self._FIAT_VAL)

        lg.debug("CtbAction::__init__(): %s", self)

        # Determine amount, if keyword is given instead of numeric value
        if self._TYPE in ['givetip', 'withdraw']:
            if bool(self._COIN) and not type(self._COIN_VAL) in [float, int] and not self._COIN_VAL == None:
                # Determine coin value
                lg.debug("CtbAction::__init__(): determining coin value given '%s'", self._COIN_VAL)
                val = self._CTB._config['kw'][self._COIN_VAL.lower()]
                if type(val) == float:
                    self._COIN_VAL = val
                elif type(val) == str:
                    lg.debug("CtbAction::__init__(): evaluating '%s'", val)
                    self._COIN_VAL = eval(val)
                    if not type(self._COIN_VAL) == float:
                        lg.warning("CtbAction::__init__(atype=%s, from_user=%s): could not determine _COIN_VAL given %s" % (self._TYPE, self._FROM_USER._NAME, self._COIN_VAL))
                        return None
                else:
                    lg.warning("CtbAction::__init__(atype=%s, from_user=%s): could not determine _COIN_VAL given %s" % (self._TYPE, self._FROM_USER._NAME, self._COIN_VAL))
                    return None
            if bool(self._FIAT) and not type(self._FIAT_VAL) in [float, int] and not self._FIAT_VAL == None:
                # Determine fiat value
                lg.debug("CtbAction::__init__(): determining fiat value given '%s'", self._FIAT_VAL)
                val = self._CTB._config['kw'][self._FIAT_VAL.lower()]
                if type(val) == float:
                    self._FIAT_VAL = val
                elif type(val) == str:
                    lg.debug("CtbAction::__init__(): evaluating '%s'", val)
                    self._FIAT_VAL = eval(val)
                    if not type(self._FIAT_VAL) == float:
                        lg.warning("CtbAction::__init__(atype=%s, from_user=%s): could not determine _FIAT_VAL given %s" % (self._TYPE, self._FROM_USER._NAME, self._FIAT_VAL))
                        return None
                else:
                    lg.warning("CtbAction::__init__(atype=%s, from_user=%s): could not determine _FIAT_VAL given %s" % (self._TYPE, self._FROM_USER._NAME, self._FIAT_VAL))
                    return None

        # Determine coin, if applicable
        if self._TYPE in ['givetip']:
            if bool(self._FIAT) and not bool(self._COIN):
                if not self._FROM_USER.is_registered():
                    # Can't proceed, abort
                    lg.warning("CtbAction::__init__(): can't determine coin for un-registered user %s", self._FROM_USER._NAME)
                    return None
                # Set the coin based on from_user's available balance
                _cc = self._CTB._config['cc']
                _fiat = self._CTB._config['fiat']
                for c in _cc:
                    if _cc[c]['enabled']:
                        # First, check if we have a ticker value for this coin and fiat
                        if not ( hasattr(ctb, '_ticker_val') and ctb._ticker_val.has_key(_cc[c]['unit']+'_btc') and ctb._ticker_val.has_key('btc_'+self._FIAT) and ctb._ticker_val[_cc[c]['unit']+'_btc']['avg'] > 0 and ctb._ticker_val['btc_'+self._FIAT]['avg'] > 0 ):
                            continue
                        # Compare available and needed coin balances
                        coin_balance_avail = self._FROM_USER.get_balance(coin=_cc[c]['unit'], kind='givetip')
                        coin_balance_need = float( self._FIAT_VAL / ( ctb._ticker_val[_cc[c]['unit']+'_btc']['avg'] * ctb._ticker_val['btc_'+self._FIAT]['avg'] ) )
                        if coin_balance_avail > coin_balance_need or abs(coin_balance_avail - coin_balance_need) < 0.000001:
                            # Found coin with enough balance
                            self._COIN = _cc[c]['unit']
                            break
            if not bool(self._COIN):
                # Couldn't deteremine coin, abort
                lg.warning("CtbAction::__init__(): can't determine coin for user %s", self._FROM_USER._NAME)
                return None

        # Determine fiat or coin value
        if self._TYPE in ['givetip', 'withdraw']:
            if not bool(self._FIAT):
                # Set fiat to 'usd' if not specified
                self._FIAT = 'usd'
            if not bool(self._FIAT_VAL):
                # Determine fiat value
                if hasattr(ctb, '_ticker_val') and ctb._ticker_val.has_key(self._COIN+'_btc') and ctb._ticker_val.has_key('btc_'+self._FIAT) and ctb._ticker_val[self._COIN+'_btc']['avg'] > 0 and ctb._ticker_val['btc_'+self._FIAT]['avg'] > 0:
                    self._FIAT_VAL = float( self._COIN_VAL * ctb._ticker_val[self._COIN+'_btc']['avg'] * ctb._ticker_val['btc_'+self._FIAT]['avg'] )
                else:
                    lg.warning("CtbAction::__init__(atype=%s, from_user=%s): can't determine %s value of %s", self._TYPE, self._FROM_USER._NAME, self._FIAT, self._COIN)
                    self._FIAT_VAL = float(0)
            elif not bool(self._COIN_VAL):
                # Determine coin value
                if hasattr(ctb, '_ticker_val') and ctb._ticker_val.has_key(self._COIN+'_btc') and ctb._ticker_val.has_key('btc_'+self._FIAT) and ctb._ticker_val[self._COIN+'_btc']['avg'] > 0 and ctb._ticker_val['btc_'+self._FIAT]['avg'] > 0:
                    self._COIN_VAL = float( self._FIAT_VAL / ( ctb._ticker_val[self._COIN+'_btc']['avg'] * ctb._ticker_val['btc_'+self._FIAT]['avg'] ) )
                else:
                    lg.warning("CtbAction::__init__(atype=%s, from_user=%s): can't determine %s value of %s", self._TYPE, self._FROM_USER._NAME, self._COIN, self._FIAT)
                    self._COIN_VAL = float(0)

        # Subtract tx fee if needed
        if self._CTB._config['misc']['subtract-txfee']:
            if bool(self._TO_ADDR):
                self._COIN_VAL -= self._CTB._config['cc'][self._COIN]['txfee']

        lg.debug("< CtbAction::__init__(atype=%s, from_user=%s) DONE", self._TYPE, self._FROM_USER._NAME)

    def __str__(self):
        """""
        Return string representation of self
        """
        me = "<CtbAction: atype=%s, msg=%s, to_user=%s, to_addr=%s, coin=%s, fiat=%s, coin_val=%s, fiat_val=%s, subr=%s, ctb=%s>"
        me = me % (self._TYPE, self._MSG, self._TO_USER, self._TO_ADDR, self._COIN, self._FIAT, self._COIN_VAL, self._FIAT_VAL, self._SUBR, self._CTB)
        return me

    def save(self, state=None):
        """
        Save action to database
        """
        lg.debug("> CtbAction::save(%s)", state)

        conn = self._CTB._mysqlcon
        sql = "REPLACE INTO t_action (type, state, created_utc, from_user, to_user, to_addr, coin_val, fiat_val, txid, coin, fiat, subreddit, msg_id, msg_link)"
        sql += " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        try:
            mysqlexec = conn.execute(sql,
                    (self._TYPE,
                     state,
                     self._MSG.created_utc,
                     self._FROM_USER._NAME.lower(),
                     self._TO_USER._NAME.lower() if bool(self._TO_USER) else None,
                     self._TO_ADDR,
                     self._COIN_VAL,
                     self._FIAT_VAL,
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
                self._COIN_VAL,
                self._FIAT_VAL,
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
            if self.accept():
                self._TYPE = 'info'
                return self.info()
            else:
                return False

        if self._TYPE == 'decline':
            return self.decline()

        if self._TYPE == 'givetip':
            return self.givetip()

        if self._TYPE == 'history':
            return self.history()

        if self._TYPE == 'info':
            return self.info()

        if self._TYPE == 'register':
            if self.register():
                self._TYPE = 'info'
                return self.info()
            else:
                return False

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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, ctb=self._CTB)):
            lg.warning("CtbAction::accept(): duplicate action %s (from %s), ignoring", self._TYPE, self._MSG.id)
            return False

        # Register as new user
        if not self._FROM_USER.is_registered():
            if not self._FROM_USER.register():
                lg.warning("CtbAction::accept(): self._FROM_USER.register() failed")
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
            txt = "I'm sorry %s, you don't have any pending tips. Perhaps they've been already confirmed, or already expired (tips are auto-confirmed after you've registered)." % self._FROM_USER._NAME
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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, ctb=self._CTB)):
            lg.warning("CtbAction::decline(): duplicate action %s (from %s), ignoring", self._TYPE, self._MSG.id)
            return False

        actions = _get_actions(atype='givetip', to_user=self._FROM_USER._NAME, state='pending', ctb=self._CTB)
        if bool(actions):
            for a in actions:
                # Move coins back into a._FROM_USER account
                try:
                    lg.debug("CtbAction::decline(): moving %s %s from %s to %s", str(a._COIN_VAL), a._COIN, _config['reddit']['user'].lower(), a._FROM_USER._NAME.lower())
                    m = _coincon[a._COIN].move(_config['reddit']['user'].lower(), a._FROM_USER._NAME.lower(), a._COIN_VAL)
                    # Sleep for 0.5 seconds to not overwhelm coin daemon
                    time.sleep(0.5)
                except Exception as e:
                    lg.error("CtbAction::decline(): error: %s", str(e))
                    raise
                # Save transaction as declined
                a.save('declined')
                # Respond to tip comment
                cmnt = "^__[Declined]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (a._FROM_USER._NAME, a._TO_USER._NAME, a._COIN_VAL, _cc[a._COIN]['name'])
                if bool(a._FIAT_VAL):
                    cmnt += "&nbsp;^__(%s%.4g)__" % (_fiat[a._FIAT]['symbol'], a._FIAT_VAL)
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                lg.debug("CtbAction::decline(): " + cmnt)
                if _config['reddit']['comments']['declined']:
                    if not ctb_misc._reddit_reply(msg=a._MSG, txt=cmnt):
                        a._FROM_USER.tell(subj="+tip declined", msg=cmnt)
                else:
                    a._FROM_USER.tell(subj="+tip declined", msg=cmnt)

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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        # Move coins back into self._FROM_USER account
        try:
            lg.info("CtbAction::expire(): moving %s %s from %s to %s", str(self._COIN_VAL), self._COIN, _config['reddit']['user'], self._FROM_USER._NAME.lower())
            m = _coincon[self._COIN].move(_config['reddit']['user'].lower(), self._FROM_USER._NAME.lower(), self._COIN_VAL)
            # Sleep for 0.5 seconds to not overwhelm coin daemon
            time.sleep(0.5)
        except Exception as e:
            lg.error("CtbAction::expire(): error: %s", str(e))
            raise

        # Save transaction as declined
        self.save('declined')

        # Respond to tip comment
        cmnt = "^__[Expired]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._COIN_VAL, _cc[self._COIN]['name'])
        if bool(self._FIAT_VAL):
            cmnt += "&nbsp;^__(%s%.4g)__" % (_fiat[self._FIAT]['symbol'], self._FIAT_VAL)
        cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
        lg.debug("CtbAction::expire(): " + cmnt)
        if _config['reddit']['comments']['expired']:
            if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                self._FROM_USER.tell(subj="+tip expired", msg=cmnt)
        else:
            self._FROM_USER.tell(subj="+tip expired", msg=cmnt)

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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        if self._TYPE in ['givetip', 'withdraw']:
            # Check if _FROM_USER has registered
            if not self._FROM_USER.is_registered():
                msg = "I'm sorry %s, we've never met. Please __[+register](http://www.reddit.com/message/compose?to=%s&subject=register&message=%%2Bregister)__ first!" % (re.escape(self._FROM_USER._NAME), self._CTB._config['reddit']['user'])
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+tip failed", msg=msg)
                self.save('failed')
                return False

            # Verify that coin type is set
            if not bool(self._COIN):
                msg = "Sorry %s, you don't have any coin balances enough for a __%s%.4g tip__." % (re.escape(self._FROM_USER._NAME), _fiat[self._FIAT]['symbol'], self._FIAT_VAL)
                lg.debug("CtbAction::__init__(): %s", msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+tip failed", msg=msg)
                self.save('failed')
                return False

            # Verify that _FROM_USER has coin address
            if not self._FROM_USER.get_addr(coin=self._COIN):
                msg = "I'm sorry %s, you don't seem to have a %s address." % (re.escape(self._FROM_USER._NAME), self._COIN.upper())
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+tip failed", msg=msg)
                self.save('failed')
                return False

            # Verify minimum transaction size
            txkind = 'givetip' if bool(self._TO_USER) else 'withdraw'
            if self._COIN_VAL < _cc[self._COIN]['txmin'][txkind]:
                msg = "I'm sorry %s, your tip/withdraw of __%.6g %s__ is below minimum of __%.6g__." % (re.escape(self._FROM_USER._NAME), self._COIN_VAL, self._COIN.upper(), _cc[self._COIN]['txmin'][txkind])
                lg.debug("CtbAction::validate(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._FROM_USER.tell(subj="+tip failed", msg=msg)
                self.save('failed')
                return False

            # Verify balance (unless it's a pending transaction being processed, in which case coins have been already moved to pending acct)
            if bool(self._TO_USER) and not is_pending:
                # Tip to user (requires less confirmations)
                balance_avail = self._FROM_USER.get_balance(coin=self._COIN, kind='givetip')
                if not ( balance_avail > self._COIN_VAL or abs(balance_avail - self._COIN_VAL) < 0.000001 ):
                    msg = "I'm sorry %s, your confirmed _tip_ balance of __%.6g %s__ is insufficient for this tip." % (re.escape(self._FROM_USER._NAME), balance_avail, self._COIN.upper())
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+tip failed", msg=msg)
                    self.save('failed')
                    return False
            elif bool(self._TO_ADDR):
                # Tip/withdrawal to address (requires more confirmations)
                balance_avail = self._FROM_USER.get_balance(coin=self._COIN, kind='withdraw')
                balance_need = self._COIN_VAL
                if not _config['misc']['subtract-txfee']:
                    balance_need += _cc[self._COIN]['txfee']
                if not ( balance_avail > balance_need or abs(balance_avail - balance_need) < 0.000001 ):
                    msg = "I'm sorry %s, your confirmed _withdraw_ balance of __%.6g %s__ is insufficient for this action (%s confirmations needed)." % (re.escape(self._FROM_USER._NAME), balance_avail, self._COIN.upper(), _cc[self._COIN]['minconf']['withdraw'])
                    if not _config['misc']['subtract-txfee']:
                        msg += " There is a %.6g %s network transaction fee." % (_cc[self._COIN]['txfee'], self._COIN.upper())
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+tip failed", msg=msg)
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
                    msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+tip failed", msg=msg)
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
                    lg.info("CtbAction::validate(): moving %s %s from %s to %s", str(self._COIN_VAL), self._COIN, self._FROM_USER._NAME.lower(), _config['reddit']['user'])
                    m = _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), _config['reddit']['user'].lower(), self._COIN_VAL)
                    # Sleep for 0.5 seconds to not overwhelm coin daemon
                    time.sleep(0.5)
                except Exception as e:
                    lg.error("CtbAction::validate(): error: %s", str(e))
                    raise

                # Save action as pending
                self.save('pending')

                # Respond to tip comment
                cmnt = "^(__[Verified]__:) ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._COIN_VAL, _cc[self._COIN]['name'])
                if bool(self._FIAT_VAL):
                    cmnt += "&nbsp;^__(%s%.4g)__" % (_fiat[self._FIAT]['symbol'], self._FIAT_VAL)
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                lg.debug("CtbAction::validate(): " + cmnt)
                if _config['reddit']['comments']['verify']:
                    if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                        self._FROM_USER.tell(subj="+tip pending +accept", msg=cmnt)
                else:
                    self._FROM_USER.tell(subj="+tip pending +accept", msg=cmnt)

                # Send notice to _TO_USER
                msg = "Hey %s, /u/%s sent you a __%.6g %s(s) (%s%.4g)__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to=%s&subject=accept&message=%%2Baccept)__ to claim it. "
                msg += "Reply with __[+decline](http://www.reddit.com/message/compose?to=%s&subject=decline&message=%%2Bdecline)__ to decline it."
                msg = msg % (re.escape(self._TO_USER._NAME), re.escape(self._FROM_USER._NAME), self._COIN_VAL, _cc[self._COIN]['name'], _fiat[self._FIAT]['symbol'], self._FIAT_VAL, self._CTB._config['reddit']['user'], self._CTB._config['reddit']['user'])
                msg += " Pending tips expire in %.1g days." % ( float(_config['misc']['expire-pending-hours']) / float(24) )
                lg.debug("CtbAction::validate(): %s", msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._TO_USER.tell(subj="+tip pending", msg=msg)

                # Action saved as 'pending', return false to avoid processing it
                return False

            # Validate _TO_ADDR, if applicable
            if bool(self._TO_ADDR):
                addr_valid = _coincon[self._COIN].validateaddress(self._TO_ADDR)
                if not addr_valid['isvalid']:
                    msg = "I'm sorry %s, __%s__ address __%s__ appears to be invalid (is there a typo?)." % (re.escape(self._FROM_USER._NAME), self._COIN.upper(), self._TO_ADDR)
                    lg.debug("CtbAction::validate(): " + msg)
                    msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                    msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                    self._FROM_USER.tell(subj="+tip failed", msg=msg)
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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        # Check if action has been processed
        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, ctb=self._CTB, is_pending=is_pending)):
            # Found action in database, returning
            lg.warning("CtbAction::givetipt(): duplicate action %s (from %s), ignoring", self._TYPE, self._MSG.id)
            return False

        # Validate action
        if not self.validate(is_pending=is_pending):
            # Couldn't validate action, returning
            return False

        if bool(self._TO_USER):
            # Process tip to user

            try:
                if is_pending:
                    lg.info("CtbAction::givetip(): sending %f %s from %s to %s...", self._COIN_VAL, self._COIN.upper(), _config['reddit']['user'].lower(), self._TO_USER._NAME.lower())
                    _coincon[self._COIN].move(_config['reddit']['user'].lower(), self._TO_USER._NAME.lower(), self._COIN_VAL, _cc[self._COIN]['minconf'][self._TYPE])
                else:
                    lg.info("CtbAction::givetip(): sending %f %s from %s to %s...", self._COIN_VAL, self._COIN.upper(), self._FROM_USER._NAME.lower(), self._TO_USER._NAME.lower())
                    _coincon[self._COIN].move(self._FROM_USER._NAME.lower(), self._TO_USER._NAME.lower(), self._COIN_VAL, _cc[self._COIN]['minconf'][self._TYPE])
                # Sleep for 0.5 seconds to not overwhelm coin daemon
                time.sleep(0.5)
            except Exception as e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%.6g %s(s)__ to /u/%s has failed to process." % (re.escape(self._FROM_USER._NAME), self._COIN_VAL, _cc[self._COIN]['name'], re.escape(self._TO_USER._NAME))
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+tip failed", msg=msg)

                # Log error
                lg.error("CtbAction::givetip(): move of %s %s from %s to %s failed: %s" % (self._COIN_VAL, self._COIN, (self._FROM_USER._NAME if is_pending else _config['reddit']['user']), self._TO_USER._NAME, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Send confirmation to _TO_USER
                msg = "Hey %s, you have received a __%.6g %s(s) (%s%.4g)__ tip from /u/%s." % (re.escape(self._TO_USER._NAME), self._COIN_VAL, _cc[self._COIN]['name'], _fiat[self._FIAT]['symbol'], self._FIAT_VAL, re.escape(self._FROM_USER._NAME))
                lg.debug("CtbAction::givetip(): " + msg)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                msg += "\n* [+tip comment](%s)" % (self._MSG.permalink) if hasattr(self._MSG, 'permalink') else ""
                self._TO_USER.tell(subj="+tip received", msg=msg)

                if not is_pending:
                    # This is not an +accept, so post verification comment
                    cmnt = "^__[Verified]__: ^/u/%s ^-> ^/u/%s, __^%.6g ^%s(s)__" % (self._FROM_USER._NAME, self._TO_USER._NAME, self._COIN_VAL, _cc[self._COIN]['name'])
                    if bool(self._FIAT_VAL):
                        cmnt += "&nbsp;^__(%s%.4g)__" % (_fiat[self._FIAT]['symbol'], self._FIAT_VAL)
                    lg.debug("CtbAction::givetip(): " + cmnt)
                    cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                    if _config['reddit']['comments']['verify']:
                        if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                            self._FROM_USER.tell(subj="+tip succeeded", msg=cmnt)
                    else:
                        self._FROM_USER.tell(subj="+tip succeeded", msg=cmnt)

            except Exception as e:
                # Couldn't post to Reddit
                lg.error("CtbAction::givetip(): error communicating with Reddit: %s" % str(e))
                raise

            lg.debug("< CtbAction::givetip() DONE")
            return True

        elif bool(self._TO_ADDR):
            # Process tip to address

            try:
                lg.info("CtbAction::givetip(): sending %f %s to %s...", self._COIN_VAL, self._COIN, self._TO_ADDR)
                # Unlock wallet, if applicable
                if _cc[self._COIN].has_key('walletpassphrase'):
                    res = _coincon[self._COIN].walletpassphrase(_cc[self._COIN]['walletpassphrase'], 1)
                # Perform transaction
                self._TXID = _coincon[self._COIN].sendfrom(self._FROM_USER._NAME.lower(), self._TO_ADDR, self._COIN_VAL, _cc[self._COIN]['minconf'][self._TYPE])
                # Lock wallet, if applicable
                if _cc[self._COIN].has_key('walletpassphrase'):
                    _coincon[self._COIN].walletlock()
                # Sleep for 2 seconds to not overwhelm coin daemon
                time.sleep(2)

            except Exception as e:
                # Transaction failed

                # Save transaction to database
                self.save('failed')

                # Send notice to _FROM_USER
                msg = "Hey %s, something went wrong, and your tip of __%.6g %s(s)__ to __%s__ has failed to process." % (re.escape(self._FROM_USER._NAME), self._COIN_VAL, _cc[self._COIN]['name'], self._TO_ADDR)
                msg += "\n\n* [%s help](%s)" % (_config['reddit']['user'], _config['reddit']['help-url'])
                self._FROM_USER.tell(subj="+tip failed", msg=msg)
                lg.error("CtbAction::givetip(): tx of %f %s from %s to %s failed: %s" % (self._COIN_VAL, self._COIN, self._FROM_USER._NAME, self._TO_ADDR, str(e)))
                raise

            # Transaction succeeded

            # Save transaction to database
            self.save('completed')

            try:
                # Post verification comment
                ex = _cc[self._COIN]['explorer']
                cmnt = "^__[[Verified](%s)]__: ^/u/%s ^-> ^[%s](%s), __^%.6g ^%s(s)__" % (ex['transaction'] + self._TXID, self._FROM_USER._NAME, self._TO_ADDR, ex['address'] + self._TO_ADDR, self._COIN_VAL, _cc[self._COIN]['name'])
                if bool(self._FIAT_VAL):
                    cmnt += "&nbsp;^__(%s%.4g)__" % (_fiat[self._FIAT]['symbol'], self._FIAT_VAL)
                lg.debug("CtbAction::givetip(): " + cmnt)
                cmnt += " ^[[help]](%s)" % (_config['reddit']['help-url'])
                if _config['reddit']['comments']['verify']:
                    if not ctb_misc._reddit_reply(msg=self._MSG, txt=cmnt):
                        self._FROM_USER.tell(subj="+tip succeeded", msg=cmnt)
                else:
                    self._FROM_USER.tell(subj="+tip succeeded", msg=cmnt)
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
        _fiat = self._CTB._config['fiat']
        _redditcon = self._CTB._redditcon

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, ctb=self._CTB)):
            lg.warning("CtbAction::info(): duplicate action %s (from %s), ignoring", self._TYPE, self._MSG.id)
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
            txt += "__%s (%s)__|%s&nbsp;^%s&nbsp;%s|__%.6g&nbsp;^$%.4g__|%.6g&nbsp;^$%.4g\n" % (_cc[i['coin']]['name'], i['coin'].upper(), i['address'], addr_ex_str, addr_qr_str, i['tbalance'], tbalance_usd, i['wbalance'], wbalance_usd)
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

        if bool(_check_action(atype=self._TYPE, msg_id=self._MSG.id, ctb=self._CTB)):
            lg.warning("CtbAction::register(): duplicate action %s (from %s), ignoring", self._TYPE, self._MSG.id)
            return False

        # If user exists, do nothing
        if self._FROM_USER.is_registered():
            lg.debug("CtbAction::register(%s): user already exists; ignoring request", self._FROM_USER._NAME)
            self.save('failed')
            return True

        result = self._FROM_USER.register()

        # Save action to database
        self.save('completed')

        lg.debug("< CtbAction::register() DONE")
        return result

def _init_regex(_ctb):
    """
    Initialize regular expressions used to match
    messages and comments
    """
    lg.debug("> _init_regex")

    _cc = _ctb._config['cc']
    _fiat = _ctb._config['fiat']

    if not bool(_ctb._rlist_message):
        # rlist_message is a list of regular expressions to test _message against
        #   'regex': regular expression
        #   'action': action type
        #   'coin': unit of cryptocurrency, if applicable
        #   'fiat': unit of fiat, if applicable
        #   'rg-amount': group number to retrieve amount, if applicable
        #   'rg-address': group number to retrieve coin address, if applicable

        # Add 'register', 'accept', 'decline', 'history', and 'info' regex
        _ctb._rlist_message = [
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['register'],
                 'action':     'register',
                 'rg-amount':  None,
                 'rg-address': None,
                 'coin':       None,
                 'fiat':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['accept'],
                 'action':     'accept',
                 'rg-amount':  None,
                 'rg-address': None,
                 'coin':       None,
                 'fiat':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['decline'],
                 'action':     'decline',
                 'rg-amount':  None,
                 'rg-address': None,
                 'coin':       None,
                 'fiat':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['history'],
                 'action':     'history',
                 'rg-amount':  None,
                 'rg-address': None,
                 'coin':       None,
                 'fiat':       None},
                {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['info'],
                 'action':     'info',
                 'rg-amount':  None,
                 'rg-address': None,
                 'coin':       None,
                 'fiat':       None},
                ]

        # Add 'withdraw' regex for each enabled cryptocoin and fiat
        for c in _cc:
            if _cc[c]['enabled']:
                _ctb._rlist_message.append(
                   # +withdraw ADDR 0.25 UNIT
                   {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['withdraw'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                    'action':     'withdraw',
                    'coin':       _cc[c]['unit'],
                    'fiat':       None,
                    'rg-amount':  6,
                    'rg-address': 4})
                _ctb._rlist_message.append(
                   # +withdraw ADDR KEYWORD UNIT
                   {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['withdraw'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                    'action':     'withdraw',
                    'coin':       _cc[c]['unit'],
                    'fiat':       None,
                    'rg-amount':  6,
                    'rg-address': 4})
            for f in _fiat:
                if _fiat[f]['enabled']:
                    _ctb._rlist_message.append(
                       # +withdraw ADDR $0.25 UNIT
                       {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['withdraw'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                        'action':     'withdraw',
                        'coin':       _cc[c]['unit'],
                        'fiat':       _fiat[f]['unit'],
                        'rg-amount':  7,
                        'rg-address': 4})
                    _ctb._rlist_message.append(
                       # +withdraw ADDR $KEYWORD UNIT
                       {'regex':      '(\\+)' + _ctb._config['regex']['keywords']['withdraw'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                        'action':     'withdraw',
                        'coin':       _cc[c]['unit'],
                        'fiat':       _fiat[f]['unit'],
                        'rg-amount':  7,
                        'rg-address': 4})

    if not bool(_ctb._rlist_comment):
        # rlist_comment is a list of regular expressions to test _comment against
        #   'regex': regular expression
        #   'action': action type
        #   'rg-to-user': group number to retrieve tip receiver username
        #   'rg-amount': group number to retrieve tip amount
        #   'rg-address': group number to retrieve tip receiver coin address
        #   'coin': unit of cryptocurrency
        #   'fiat': unit of fiat, if applicable

        # Add 'givetip' regex for each enabled cryptocoin and fiat
        for c in _cc:
            if _cc[c]['enabled']:
                _ctb._rlist_comment.append(
                    # +givetip ADDR 0.25 UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  None,
                     'rg-amount':   6,
                     'rg-address':  4,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip 0.25 UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  None,
                     'rg-amount':   4,
                     'rg-address':  None,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip @USER 0.25 UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  4,
                     'rg-amount':   6,
                     'rg-address':  None,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip ADDR KEYWORD UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  None,
                     'rg-amount':   6,
                     'rg-address':  4,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip KEYWORD UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  None,
                     'rg-amount':   4,
                     'rg-address':  None,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
                _ctb._rlist_comment.append(
                    # +givetip @USER KEYWORD UNIT
                    {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                     'action':      'givetip',
                     'rg-to-user':  4,
                     'rg-amount':   6,
                     'rg-address':  None,
                     'coin':        _cc[c]['unit'],
                     'fiat':        None})
            for f in _fiat:
                if _fiat[f]['enabled']:
                    _ctb._rlist_comment.append(
                        # +givetip ADDR $0.25 UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  None,
                         'rg-amount':   7,
                         'rg-address':  4,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})
                    _ctb._rlist_comment.append(
                        # +givetip $0.25 UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  None,
                         'rg-amount':   5,
                         'rg-address':  None,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})
                    _ctb._rlist_comment.append(
                        # +givetip @USER $0.25 UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  4,
                         'rg-amount':   7,
                         'rg-address':  None,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})
                    _ctb._rlist_comment.append(
                        # +givetip ADDR $KEYWORD UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _cc[c]['regex']['address'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  None,
                         'rg-amount':   7,
                         'rg-address':  4,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})
                    _ctb._rlist_comment.append(
                        # +givetip $KEYWORD UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  None,
                         'rg-amount':   5,
                         'rg-address':  None,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})
                    _ctb._rlist_comment.append(
                        # +givetip @USER $KEYWORD UNIT
                        {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'] + '(\\s+)' + _cc[c]['regex']['units'],
                         'action':      'givetip',
                         'rg-to-user':  4,
                         'rg-amount':   7,
                         'rg-address':  None,
                         'coin':        _cc[c]['unit'],
                         'fiat':        _fiat[f]['unit']})

    # These should always be last because they're very general
    for f in _fiat:
        if _fiat[f]['enabled']:
            _ctb._rlist_comment.append(
                # +givetip $0.25
                {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'],
                 'action':      'givetip',
                 'rg-to-user':  None,
                 'rg-amount':   5,
                 'rg-address':  None,
                 'coin':        None,
                 'fiat':        _fiat[f]['unit']})
            _ctb._rlist_comment.append(
                # +givetip $KEYWORD
                {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'],
                 'action':      'givetip',
                 'rg-to-user':  None,
                 'rg-amount':   5,
                 'rg-address':  None,
                 'coin':        None,
                 'fiat':        _fiat[f]['unit']})
            _ctb._rlist_comment.append(
                # +givetip @USER $0.25
                {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['num'],
                 'action':      'givetip',
                 'rg-to-user':  4,
                 'rg-amount':   7,
                 'rg-address':  None,
                 'coin':        None,
                 'fiat':        _fiat[f]['unit']})
            _ctb._rlist_comment.append(
                # +givetip @USER $KEYWORD
                {'regex':       '(\\+)' + _ctb._config['regex']['keywords']['givetip'] + '(\\s+)' + '(@\w+)' + '(\\s+)' + _fiat[f]['regex']['units'] + _ctb._config['regex']['amount']['keyword'],
                 'action':      'givetip',
                 'rg-to-user':  4,
                 'rg-amount':   7,
                 'rg-address':  None,
                 'coin':        None,
                 'fiat':        _fiat[f]['unit']})

def _eval_message(_message, _ctb):
    """
    Evaluate message body and return a CtbAction
    object if successful
    """
    #lg.debug("> _eval_message()")

    # Do the matching
    body = _message.body
    for r in _ctb._rlist_message:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("matching '%s' with '%s'", _message.body, r['regex'])
        m = rg.search(body)

        if bool(m):
            # Match found

            # Extract matched fields into variables
            _to_addr = m.group(r['rg-address']) if bool(r['rg-address']) else None
            _amount = m.group(r['rg-amount']) if bool(r['rg-amount']) else None

            # Return CtbAction instance with given variables
            return CtbAction(   atype=r['action'],
                                msg=_message,
                                to_user=None,
                                to_addr=_to_addr,
                                coin=r['coin'],
                                coin_val=_amount if not bool(r['fiat']) else None,
                                fiat=r['fiat'],
                                fiat_val=_amount if bool(r['fiat']) else None,
                                ctb=_ctb)

    # No match found
    return None

def _eval_comment(_comment, _ctb):
    """
    Evaluate comment body and return a CtbAction
    object if successful
    """
    #lg.debug("> _eval_comment()")

    # Do the matching
    body = _comment.body
    for r in _ctb._rlist_comment:
        rg = re.compile(r['regex'], re.IGNORECASE|re.DOTALL)
        #lg.debug("_eval_comment(): matching '%s' using <%s>", _comment.body, r['regex'])
        m = rg.search(body)

        if bool(m):
            # Match found

            # Extract matched fields into variables
            _to_user = m.group(r['rg-to-user'])[1:] if bool(r['rg-to-user']) else None
            _to_addr = m.group(r['rg-address']) if bool(r['rg-address']) else None
            _amount = m.group(r['rg-amount']) if bool(r['rg-amount']) else None

            # If no destination mentioned, find parent submission's author
            if not bool(_to_user) and not bool(_to_addr):
                # set _to_user to author of parent comment
                _to_user = ctb_misc._reddit_get_parent_author(_comment, _ctb._redditcon, _ctb=_ctb)

            # Check if from_user == to_user
            if bool(_to_user) and _comment.author.name.lower() == _to_user.lower():
                lg.warning("_eval_comment(%s): _comment.author.name == _to_user, ignoring comment", _comment.author.name)
                return None

            # Return CtbAction instance with given variables
            lg.debug("_eval_comment(): creating action %s: to_user=%s, to_addr=%s, amount=%s, coin=%s, fiat=%s" % (r['action'], _to_user, _to_addr, _amount, r['coin'], r['fiat']))
            #lg.debug("< _eval_comment() DONE (yes)")
            return CtbAction(   atype=r['action'],
                                msg=_comment,
                                to_user=_to_user,
                                to_addr=_to_addr,
                                coin=r['coin'],
                                coin_val=_amount if not bool(r['fiat']) else None,
                                fiat=r['fiat'],
                                fiat_val=_amount if bool(r['fiat']) else None,
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
                                      coin=m['coin'],
                                      fiat=m['fiat'],
                                      coin_val=float(m['coin_val']) if bool(m['coin_val']) else None,
                                      fiat_val=float(m['fiat_val']) if bool(m['fiat_val']) else None,
                                      subr=m['subreddit'],
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
