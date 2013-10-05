#!/usr/bin/env python

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

from ctb import ctb_action, ctb_db, ctb_log, ctb_misc, ctb_user

import gettext, locale, logging, sys, time
import praw, re, sqlalchemy, yaml
from pifkoin.bitcoind import Bitcoind, BitcoindException

from requests.exceptions import HTTPError
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

# Configure CointipBot logger
logging.basicConfig()
lg = logging.getLogger('cointipbot')

class CointipBot(object):
    """
    Main class for cointip bot
    """
    _DEFAULT_CONFIG_FILENAME = './config.yml'
    _DEFAULT_SLEEP_TIME = 60*0.5
    _REDDIT_BATCH_LIMIT=10

    _config = None
    _mysqlcon = None
    _redditcon = None
    _coincon = {}

    _ticker = None
    _ticker_pairs = None
    _ticker_val = {}
    _ticker_last_refresh = 0

    _subreddits = None

    _rlist_message = []
    _rlist_comment = []

    _last_processed_comment_time = 0

    def _init_logging(self):
        """
        Set up logging
        """
        hdlr_info = None
        hdlr_debug = None
        lg = logging.getLogger('cointipbot')
        bt = logging.getLogger('bitcoin')

        # Get handlers
        if self._config['logging'].has_key('info-log-filename'):
            # INFO-level log file in append mode
            hdlr_info = logging.FileHandler(self._config['logging']['info-log-filename'], mode='a')
        if self._config['logging'].has_key('debug-log-filename'):
            # DEBUG-level log file in write mode
            hdlr_debug = logging.FileHandler(self._config['logging']['debug-log-filename'], mode='w')

        if not bool(hdlr_info) and not bool(hdlr_debug):
            print "CointipBot::_init_logging(): Warning: no logging handlers are set up. Logging is disabled."
            return False

        # Get formatter
        fmtr = logging.Formatter("%(levelname)s %(asctime)s %(message)s")

        # Set handlers
        if bool(hdlr_info):
            hdlr_info.setFormatter(fmtr)
            hdlr_info.addFilter(ctb_log.LevelFilter(logging.INFO))
            lg.addHandler(hdlr_info)
            bt.addHandler(hdlr_info)

        if bool(hdlr_debug):
            hdlr_debug.setFormatter(fmtr)
            hdlr_debug.addFilter(ctb_log.LevelFilter(logging.DEBUG))
            lg.addHandler(hdlr_debug)
            bt.addHandler(hdlr_debug)

        # Set levels
        lg.setLevel(logging.DEBUG)
        bt.setLevel(logging.DEBUG)

        lg.info("CointipBot::_init_logging(): -------------------- logging initialized --------------------")
        if bool(hdlr_info):
            lg.info("Logging level INFO to %s", self._config['logging']['info-log-filename'])
        if bool(hdlr_debug):
            lg.info("Logging level DEBUG to %s", self._config['logging']['debug-log-filename'])

        return True

    def _parse_config(self, filename=_DEFAULT_CONFIG_FILENAME):
        """
        Returns a Python object with CointipBot configuration

        :param filename:
            The filename from which the configuration should be read.
        """
        lg.debug("Parsing config file...")

        try:
            config = yaml.load(open(filename))
        except yaml.YAMLError as e:
            lg.error("Error reading config file "+filename)
            if hasattr(e, 'problem_mark'):
                lg.error("Error position: (line "+str(e.problem_mark.line+1)+", column "+str(e.problem_mark.column+1)+")");
            sys.exit(1)

        lg.info("Config file has been read")
        return config

    def _connect_db(self, config):
        """
        Returns a database connection object
        """
        lg.debug("Connecting to MySQL...")

        dsn = "mysql+mysqldb://" + str(config['mysql']['user']) + ":" + str(config['mysql']['pass'])
        dsn += "@" + str(config['mysql']['host']) + ":" + str(config['mysql']['port']) + "/" + str(config['mysql']['db'])
        dbobj = ctb_db.CointipBotDatabase(dsn)

        try:
            conn = dbobj.connect()
        except Exception as e:
            lg.error("Error connecting to database: "+str(e))
            sys.exit(1)

        lg.info("Connected to database %s as %s", config['mysql']['host'], config['mysql']['user'])
        return conn

    def _connect_coin(self, c):
        """
        Returns a coin daemon connection object
        """
        lg.debug("Connecting to %s...", c['name'])

        try:
            conn = Bitcoind(c['conf-file'])
        except BitcoindException as e:
            lg.error("Error connecting to %s: %s", c['name'], str(e))
            sys.exit(1)
        lg.info("Connected to %s", c['name'])

        # Set tx fee
        lg.info("Setting tx fee of %f", c['txfee'])
        conn.settxfee(c['txfee'])

        # Done
        return conn

    def _connect_reddit(self, config):
        """
        Returns a praw connection object
        """
        lg.debug("Connecting to Reddit...")

        while True:
            try:
                conn = praw.Reddit(user_agent = config['reddit']['useragent'])
                conn.login(config['reddit']['user'], config['reddit']['pass'])
                break
            except HTTPError as e:
                lg.warning("CointipBot::_connect_reddit(): Reddit is down (%s), sleeping...", str(e))
                time.sleep(self._DEFAULT_SLEEP_TIME)
                pass
            except timeout:
                lg.warning("CointipBot::_connect_reddit(): Reddit is down (timeout), sleeping...")
                time.sleep(self._DEFAULT_SLEEP_TIME)
                pass
            except Exception as e:
                lg.error("CointipBot::_connect_reddit(): Error connecting to Reddit: %s", str(e))
                raise

        lg.info("Logged in to Reddit as %s", config['reddit']['user'])
        return conn

    def _self_checks(self):
        """
        Run self-checks before starting the bot
        """
        # Ensure bot is a registered user
        b = ctb_user.CtbUser(name=self._config['reddit']['user'].lower(), ctb=self)
        if not b.is_registered():
            b.register()

        # Ensure (total pending tips) < (CointipBot's balance)
        for c in self._coincon:
            ctb_balance = float(b.get_balance(coin=c, kind='givetip'))
            pending_tips = float(0)
            actions = ctb_action._get_actions(atype='givetip', state='pending', coin=c, ctb=self)
            for a in actions:
                pending_tips += a._COIN_VAL
            if (ctb_balance - pending_tips) < -0.000001:
                raise Exception("CointipBot::_self_checks(): CointipBot's %s balance (%s) < total pending tips (%s)" % (c.upper(), ctb_balance, pending_tips))

        # Ensure coin balances are positive
        for c in self._coincon:
            b = self._coincon[c].getbalance()
            if b < 0:
                raise Exception("CointipBot::_self_checks(): negative balance of %s: %s" % (c, b))

        # Ensure user accounts are intact and balances are not negative
        sql = "SELECT username FROM t_users ORDER BY username"
        for mysqlrow in self._mysqlcon.execute(sql):
            u = ctb_user.CtbUser(name=mysqlrow['username'], ctb=self)
            if not u.is_registered():
                raise Exception("CointipBot::_self_checks(): user %s is_registered() failed" % mysqlrow['username'])
        #    for c in self._coincon:
        #        if u.get_balance(coin=c, kind='givetip') < 0:
        #            raise Exception("CointipBot::_self_checks(): user %s %s balance is negative" % (mysqlrow['username'], c))

        # Done
        return True

    def _expire_pending_tips(self):
        """
        Decline any pending tips that have reached expiration time limit
        """
        # Calculate timestamp
        seconds = int(self._config['misc']['expire-pending-hours'] * 3600)
        created_before = time.mktime(time.gmtime()) - seconds
        counter = 0

        # Get expired actions and decline them
        for a in ctb_action._get_actions(atype='givetip', state='pending', created_utc='< ' + str(created_before), ctb=self):
            a.expire()
            counter += 1

        # Done
        return (counter > 0)

    def _check_inbox(self):
        """
        Evaluate new messages in inbox
        """
        lg.debug("> _check_inbox()")

        try:

            # Try to fetch some messages
            messages = ctb_misc._praw_call(self._redditcon.get_unread, limit=self._REDDIT_BATCH_LIMIT)

            # Process messages
            for m in messages:
                lg.info("_check_inbox(): %s from %s", "comment" if m.was_comment else "message", m.author.name)

                # Ignore self messages
                if bool(m.author) and m.author.name.lower() == self._config['reddit']['user'].lower():
                    lg.debug("_check_inbox(): ignoring message from self")
                    ctb_misc._praw_call(m.mark_as_read)
                    continue

                # Ignore messages from banned users
                if bool(m.author) and self._config['reddit'].has_key('banned_users'):
                    lg.debug("_check_inbox(): checking whether user '%s' is banned..." % m.author)
                    u = ctb_user.CtbUser(name = m.author.name, redditobj = m.author, ctb = self)
                    if u._IS_BANNED:
                        lg.info("_check_inbox(): ignoring banned user '%s'" % m.author)
                        ctb_misc._praw_call(m.mark_as_read)
                        continue

                action = None
                if m.was_comment:
                    # Attempt to evaluate as comment / mention
                    action = ctb_action._eval_comment(m, self)
                else:
                    # Attempt to evaluate as inbox message
                    action = ctb_action._eval_message(m, self)

                # Perform action, if found
                if bool(action):
                    lg.info("_check_inbox(): %s from %s (m.id %s)", action._TYPE, action._FROM_USER._NAME, str(m.id))
                    action.do()
                else:
                    lg.info("_check_inbox(): no match")
                    if self._config['reddit']['messages']['sorry']:
                        user = ctb_user.CtbUser(name=m.author.name, redditobj=m.author, ctb=self)
                        msg = "Sorry %s, I didn't understand your %s. Please [verify the syntax](%s#wiki_commands) and try again by issuing a new one." % (user._NAME, "comment" if m.was_comment else "message", self._config['reddit']['help-url'])
                        lg.debug("_check_inbox(): %s", msg)
                        msg += "\n\n* [%s help](%s)" % (self._config['reddit']['user'], self._config['reddit']['help-url'])
                        if hasattr(m, 'permalink'):
                            msg += "\n* [source %s](%s)" % ("comment" if m.was_comment else "message", m.permalink)
                        user.tell(subj="Sorry!", msg=msg, msgobj=m if not m.was_comment else None)

                # Mark message as read
                ctb_misc._praw_call(m.mark_as_read)

        except Exception as e:
            lg.error("_check_inbox(): %s", str(e))
            raise

        lg.debug("< check_inbox() DONE")
        return True

    def _init_subreddits(self):
        """
        Determine a list of subreddits and create a PRAW object
        """
        lg.debug("> _init_subreddits()")

        try:
            if not bool(self._subreddits):
                # Get subreddits

                my_reddits_list = None
                my_ignore_list = None
                my_reddits_string = None

                if self._config['reddit']['scan'].has_key('these-subreddits'):
                    # Subreddits are specified in config.yml
                    my_reddits_list = list(self._config['reddit']['scan']['these-subreddits'])
                    if self._config['reddit']['scan'].has_key('ignore-subreddits'):
                        my_ignore_list = list(self._config['reddit']['scan']['ignore-subreddits'])

                elif self._config['reddit']['scan']['my-subreddits']:
                    # Subreddits are subscribed to by bot user
                    my_reddits = ctb_misc._praw_call(self._redditcon.get_my_subreddits, limit=None)
                    my_reddits_list = []
                    for my_reddit in my_reddits:
                        my_reddits_list.append(my_reddit.display_name.lower())
                    my_reddits_list.sort()

                else:
                    # No subreddits configured
                    lg.debug("< _check_subreddits() DONE (no subreddits configured to scan)")
                    return False

                # Build subreddits string
                my_reddits_string = "+".join(my_reddits_list)
                if bool(my_ignore_list):
                    my_reddits_string += ( "-" + "-".join(my_ignore_list) )

                # Get multi-reddit PRAW object
                lg.debug("_check_subreddits(): multi-reddit string: %s", my_reddits_string)
                self._subreddits = ctb_misc._praw_call(self._redditcon.get_subreddit, my_reddits_string)

        except Exception as e:
            lg.error("_check_subreddits(): coudln't fetch comments: %s", str(e))
            raise

        lg.debug("< _init_subreddits() DONE")
        return True

    def _check_subreddits(self):
        """
        Evaluate new comments from configured subreddits
        """
        lg.debug("> _check_subreddits()")

        try:
            # Process comments until old comment reached

            # Get last_processed_comment_time if necessary
            if self._last_processed_comment_time <= 0:
                self._last_processed_comment_time = ctb_misc._get_value(conn=self._mysqlcon, param0='last_processed_comment_time')
            _updated_last_processed_time = 0

            # Fetch comments from subreddits
            my_comments = ctb_misc._praw_call(self._subreddits.get_comments, limit=self._REDDIT_BATCH_LIMIT)

            # Match each comment against regex
            counter = 0
            for c in my_comments:
                # Stop processing if old comment reached
                #lg.debug("_check_subreddits(): c.id %s from %s, %s <= %s", c.id, c.subreddit.display_name, c.created_utc, self._last_processed_comment_time)
                if c.created_utc <= self._last_processed_comment_time:
                    lg.debug("_check_subreddits(): old comment reached")
                    break
                counter += 1
                if c.created_utc > _updated_last_processed_time:
                    _updated_last_processed_time = c.created_utc

                # Ignore comments from banned users
                if bool(c.author) and self._config['reddit'].has_key('banned_users'):
                    lg.debug("_check_subreddits(): checking whether user '%s' is banned..." % c.author)
                    u = ctb_user.CtbUser(name = c.author.name, redditobj = c.author, ctb = self)
                    if u._IS_BANNED:
                        lg.info("_check_subreddits(): ignoring banned user '%s'" % c.author)
                        continue

                # Attempt to evaluate comment
                action = ctb_action._eval_comment(c, self)

                # Perform action, if found
                if bool(action):
                    lg.info("_check_subreddits(): %s from %s (m.id %s)", action._TYPE, action._FROM_USER._NAME, str(c.id))
                    action.do()
                else:
                    lg.info("_check_subreddits(): no match")

            lg.debug("_check_subreddits(): %s comments processed", counter)
            if counter >= self._REDDIT_BATCH_LIMIT - 1:
                lg.warning("_check_subreddits(): _REDDIT_BATCH_LIMIT (%s) was not large enough to process all comments", self._REDDIT_BATCH_LIMIT)

        except Exception as e:
            lg.error("_check_subreddits(): coudln't fetch comments: %s", str(e))
            raise

        # Save updated last_processed_time value
        if _updated_last_processed_time > 0:
            self._last_processed_comment_time = _updated_last_processed_time
        ctb_misc._set_value(conn=self._mysqlcon, param0='last_processed_comment_time', value0=self._last_processed_comment_time)

        lg.debug("< _check_subreddits() DONE")
        return True

    def _clean_up(self):
        lg.debug("> _clean_up()")
        lg.debug("< _clean_up() DONE")
        return None

    def __init__(self, config_filename=_DEFAULT_CONFIG_FILENAME, self_checks=True, init_reddit=True, init_coins=True, init_db=True, init_logging=True):
        """
        Constructor.
        Parses configuration file and initializes bot.
        """
        lg.info("CointipBot::__init__()...")

        # Configuration file
        self._config = self._parse_config(config_filename)
        if 'batch-limit' in self._config['reddit']:
            self._REDDIT_BATCH_LIMIT = self._config['reddit']['batch-limit']
        if 'sleep-seconds' in self._config['misc']:
            self._DEFAULT_SLEEP_TIME = self._config['misc']['sleep-seconds']

        # Logging
        if init_logging:
            if self._config.has_key('logging'):
                self._init_logging()
            else:
                print "CointipBot::__init__(): Warning: no logging handlers configured. Logging is disabled."

        # MySQL
        if init_db:
            self._mysqlcon = self._connect_db(self._config)

        # Coin daemons
        if init_coins:
            num_coins = 0
            for c in self._config['cc']:
                if self._config['cc'][c]['enabled']:
                    self._coincon[self._config['cc'][c]['unit']] = self._connect_coin(self._config['cc'][c])
                    num_coins += 1
            if not num_coins > 0:
                lg.error("Error: please enable at least one type of coin")
                sys.exit(1)

        # Reddit
        if init_reddit:
            self._redditcon = self._connect_reddit(self._config)
            self._init_subreddits()
            # Regex for Reddit messages
            ctb_action._init_regex(self)

        # Self-checks
        if self_checks:
            self._self_checks()

        lg.info("< CointipBot::__init__(): DONE, batch-limit = %s, sleep-seconds = %s", self._REDDIT_BATCH_LIMIT, self._DEFAULT_SLEEP_TIME)

    def __str__(self):
        """
        Return string representation of self
        """
        me = "<CointipBot: dcf=%s, dst=%s, rbl=%s, ticker_val=%s, lpct=%s>"
        me = me % (self._DEFAULT_CONFIG_FILENAME, self._DEFAULT_SLEEP_TIME, self._REDDIT_BATCH_LIMIT, self._ticker_val, self._last_processed_comment_time)
        return me

    def main(self):
        """
        Main loop
        """
        while (True):
            lg.debug("Beginning main() iteration...")
            try:

                # Refresh exchange rates
                ctb_misc._refresh_exchange_rate(self, exchange=self._config['misc']['exchange'])

                # Expire pending tips
                self._expire_pending_tips()

                # Check personal messages
                self._check_inbox()

                # Check subreddit comments for tips
                if bool(self._subreddits):
                    self._check_subreddits()

                # Sleep
                lg.debug("Sleeping for %s seconds...", self._DEFAULT_SLEEP_TIME)
                time.sleep(self._DEFAULT_SLEEP_TIME)

            except Exception as e:
                lg.exception("Caught exception in main() loop: %s", str(e))

                # Clean up
                self._clean_up()

                sys.exit(1)
