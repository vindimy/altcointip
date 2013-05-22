#!/usr/bin/env python

from ctb import ctb_action, ctb_db, ctb_log, ctb_misc, ctb_user

import gettext, locale, logging, sys, time, urllib2
import praw, re, sqlalchemy, yaml
from pifkoin.bitcoind import Bitcoind, BitcoindException

# Configure CointipBot logger
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
    _ticket_val = {}

    def _init_localization(self):
        """
        Prepare localization
        """
        locale.setlocale(locale.LC_ALL, '')
        filename = "res/messages_%s.mo" % locale.getlocale()[0][0:2]
        try:
            lg.debug("Opening message file %s for locale %s", filename, locale.getlocale()[0])
            trans = gettext.GNUTranslations(open(filename, "rb"))
        except IOError:
            lg.debug("Locale not found (file %s, locale %s). Using default messages", filename, locale.getlocale()[0])
            trans = gettext.NullTranslations()
        trans.install()
        lg.debug(_("Testing localization..."))

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
            hdlr_info = logging.FileHandler(self._config['logging']['info-log-filename'], mode='a')
        if self._config['logging'].has_key('debug-log-filename'):
            hdlr_debug = logging.FileHandler(self._config['logging']['debug-log-filename'], mode='a')

        if not hdlr_info and not hdlr_debug:
            print "CointipBot::_init_logging(): Warning: no logging handlers are set up. Logging is disabled."
            return False

        # Get formatter
        fmtr = logging.Formatter("%(levelname)s %(asctime)s %(message)s")

        # Set handlers
        if hdlr_info:
            hdlr_info.setFormatter(fmtr)
            hdlr_info.addFilter(ctb_log.LevelFilter(logging.INFO))
            lg.addHandler(hdlr_info)
            bt.addHandler(hdlr_info)

        if hdlr_debug:
            hdlr_debug.setFormatter(fmtr)
            hdlr_debug.addFilter(ctb_log.LevelFilter(logging.DEBUG))
            lg.addHandler(hdlr_debug)
            bt.addHandler(hdlr_debug)

        # Set levels
        lg.setLevel(logging.DEBUG)
        bt.setLevel(logging.DEBUG)

        lg.info("CointipBot::_init_logging(): -------------------- logging initialized --------------------")
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
        except yaml.YAMLError, e:
            lg.error("Error reading config file "+filename)
            if hasattr(e, 'problem_mark'):
                lg.error("Error position: (line "+str(e.problem_mark.line+1)+", column "+str(e.problem_mark.column+1));
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
        except Exception, e:
            lg.error("Error connecting to database: "+str(e))
            sys.exit(1)
        lg.info("Connected to database")
        return conn

    def _connect_coin(self, c):
        """
        Returns a coin daemon connection object
        """
        lg.debug("Connecting to %s...", c['name'])
        try:
            conn = Bitcoind(c['conf-file'])
        except BitcoindException, e:
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
        try:
            conn = praw.Reddit(user_agent = config['reddit']['useragent'])
            conn.login(config['reddit']['user'], config['reddit']['pass'])
        except Exception, e:
            lg.error("Error connecting to Reddit: "+str(e))
            sys.exit(1)
        lg.info("Logged in to Reddit")
        return conn

    def __init__(self, config_filename=_DEFAULT_CONFIG_FILENAME):
        """
        Constructor.
        Parses configuration file and initializes bot.
        """
        # Localization. After this, all output to user is localizable
        # through use of _() function.
        self._init_localization()

        # Configuration file
        self._config = self._parse_config(config_filename)
        if 'batch-limit' in self._config['reddit']:
            self._REDDIT_BATCH_LIMIT = self._config['reddit']['batch-limit']
        if 'sleep-seconds' in self._config['misc']:
            self._DEFAULT_SLEEP_TIME = self._config['misc']['sleep-seconds']

        # Logging
        if self._config.has_key('logging'):
            self._init_logging()
        else:
            print "CointipBot::__init__(): Warning: no logging handlers are set up. Logging is disabled."

        # MySQL
        self._mysqlcon = self._connect_db(self._config)

        # Coin daemons
        num_coins = 0
        for c in self._config['cc']:
            if self._config['cc'][c]['enabled']:
                self._coincon[self._config['cc'][c]['unit']] = self._connect_coin(self._config['cc'][c])
                num_coins += 1
        if not num_coins > 0:
            lg.error("Error: please enable at least one type of coin")
            sys.exit(1)

        # Reddit
        self._redditcon = self._connect_reddit(self._config)

        # Self-checks
        self._self_checks()

        lg.info("CointipBot::__init__(): DONE, batch-limit = %s, sleep-seconds = %s", self._REDDIT_BATCH_LIMIT, self._DEFAULT_SLEEP_TIME)

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
            ctb_balance = float(b.get_balance(coin=c, kind='tip'))
            pending_tips = float(0)
            actions = ctb_action._get_actions(atype='givetip', state='pending', coin=c, ctb=self)
            for a in actions:
                pending_tips += a._TO_AMNT
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
            for c in self._coincon:
                if u.get_balance(coin=c, kind='tip') < 0:
                    raise Exception("CointipBot::_self_checks(): user %s %s balance is negative" % (mysqlrow['username'], c))

        # Done
        return True

    def _expire_pending_tips(self):
        """
        Decline any pending tips that have reached expiration time limit
        """
        # Calculate timestamp
        seconds = int(self._config['misc']['expire-pending-hours'] * 3600)
        created_before = time.mktime(time.gmtime()) - seconds

        # Get expired actions and decline them
        for a in ctb_action._get_actions(atype='givetip', state='pending', created_utc='< ' + str(created_before), ctb=self):
            a.expire()

        # Done
        return True

    def _check_inbox(self):
        """
        Evaluate new messages in inbox
        """
        lg.debug("> _check_inbox()")

        # Try to fetch some messages
        while True:
            try:
                messages = self._redditcon.get_unread(limit=self._REDDIT_BATCH_LIMIT)
                break
            except urllib2.HTTPError, e:
                if e.code in [429, 500, 502, 503, 504]:
                    lg.warning("_check_inbox(): get_unread(): Reddit is down (error %s), sleeping...", e.code)
                    time.sleep(60)
                    pass
                else:
                    raise
            except Exception, e:
                lg.error("_check_inbox(): couldn't fetch messages: %s", str(e))
                raise

        # Process messages
        for m in messages:

            # Ignore replies to bot's comments
            if m.was_comment:
                lg.debug("_check_inbox(): ignoring reply to bot's comments")
                while True:
                    try:
                        m.mark_as_read()
                        break
                    except urllib2.HTTPError, e:
                        if e.code in [429, 500, 502, 503, 504]:
                            lg.warning("_check_inbox(): Reddit is down (error %s), sleeping...", e.code)
                            time.sleep(60)
                            pass
                        else:
                            raise
                    except Exception, e:
                        lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                        raise
                continue

            # Ignore self messages
            if m.author.name.lower() == self._config['reddit']['user'].lower():
                lg.debug("_check_inbox(): ignoring message from self")
                while True:
                    try:
                        m.mark_as_read()
                        break
                    except urllib2.HTTPError, e:
                        if e.code in [429, 500, 502, 503, 504]:
                            lg.warning("_check_inbox(): Reddit is down (error %s), sleeping...", e.code)
                            time.sleep(60)
                            pass
                        else:
                            raise
                    except Exception, e:
                        lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                        raise
                continue

            # Attempt to evaluate message
            action = ctb_action._eval_message(m, self)

            # Perform action if necessary
            if action != None:
                lg.debug("_check_inbox(): calling action.do(%s)...", action._TYPE)
                try:
                    action.do()
                    lg.info("_check_inbox(): executed action %s from message_id %s", action._TYPE, str(m.id))
                except Exception, e:
                    lg.error("_check_inbox(): error executing action %s from message_id %s: %s", action._TYPE, str(m.id), str(e))
                    raise

            # Mark message as read
            while True:
                try:
                    m.mark_as_read()
                    break
                except urllib2.HTTPError, e:
                    if e.code in [429, 500, 502, 503, 504]:
                        lg.warning("_check_inbox(): Reddit is down (error %s), sleeping...", e.code)
                        time.sleep(60)
                        pass
                    else:
                        raise
                except Exception, e:
                    lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                    raise

        lg.debug("< check_inbox() DONE")
        return True

    def _check_subreddits(self):
        lg.debug("> _check_subreddits()")

        my_comments = None

        while True:
            try:
                # Get subscribed subreddits
                my_reddits = self._redditcon.get_my_subreddits()
                my_reddits_list = []
                for my_reddit in my_reddits:
                    my_reddits_list.append(my_reddit.display_name.lower())

                my_reddits_list.sort()
                lg.debug("_check_subreddits(): subreddits: %s", '+'.join(my_reddits_list))
                my_reddits_multi = self._redditcon.get_subreddit('+'.join(my_reddits_list))

                # Fetch comments from subreddits
                my_comments = my_reddits_multi.get_comments(limit=self._REDDIT_BATCH_LIMIT)
                break

            except urllib2.HTTPError, e:
                if e.code in [429, 500, 502, 503, 504]:
                    lg.warning("_check_subreddits(): Reddit is down (error %s), sleeping...", e.code)
                    time.sleep(60)
                    pass
                else:
                    raise
            except Exception, e:
                lg.error("_check_subreddits(): coudln't fetch comments: %s", str(e))
                raise

        # Process comments until old comment reached
        self._last_processed_comment_time = ctb_misc._get_value(conn=self._mysqlcon, param0="last_processed_comment_time")
        _updated_last_processed_time = 0

        try:
            for c in my_comments:
                # Stop processing if old comment reached
                if c.created_utc <= self._last_processed_comment_time:
                    lg.debug("_check_subreddits: old comment reached")
                    break

                _updated_last_processed_time = c.created_utc if c.created_utc > _updated_last_processed_time else _updated_last_processed_time

                # Attempt to evaluate comment
                action = ctb_action._eval_comment(c, self)

                # Perform action if necessary
                if action != None:
                    lg.debug("_check_subreddits(): calling action.do(%s)", action._TYPE)
                    action.do()
                    lg.info("_check_subreddits(): executed action %s from comment_id %s", action._TYPE, str(c.id))

        except urllib2.HTTPError, e:
            if e.code in [429, 500, 502, 503, 504]:
                lg.warning("_check_inbox(): Reddit is down (error %s), sleeping...", e.code)
                pass
            else:
                raise
        except Exception, e:
            lg.error("_check_subreddits(): coudln't fetch comments: %s", str(e))
            raise

        # Save updated last_processed_time value
        if _updated_last_processed_time > 0:
            ctb_misc._set_value(conn=self._mysqlcon, param0="last_processed_comment_time", value0=_updated_last_processed_time)

        lg.debug("< _check_subreddits() DONE")
        return True

    def _clean_up(self):
        lg.debug("> _clean_up()")
        lg.debug("< _clean_up() DONE")
        return None

    def main(self):
        """
        Main loop
        """
        while (True):
            lg.debug("Beginning main() iteration...")
            try:
                # Refresh exchange rates
                ctb_misc._refresh_exchange_rate(self)
                # Expire pending tips
                self._expire_pending_tips()
                # Check personal messages
                self._check_inbox()
                # Check subreddit comments for tips
                self._check_subreddits()
                # Sleep
                lg.debug("Sleeping for "+str(self._DEFAULT_SLEEP_TIME)+" seconds")
                time.sleep(self._DEFAULT_SLEEP_TIME)
            except Exception, e:
                lg.exception("Caught exception in main() loop: %s", str(e))
                # Clean up
                self._clean_up()
                sys.exit(1)

