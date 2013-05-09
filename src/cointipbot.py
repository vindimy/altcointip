#!/usr/bin/env python

from ctb import ctb_db, ctb_action, ctb_misc

import gettext, locale, logging, sys, time
import praw, re, sqlalchemy, yaml
from pifkoin.bitcoind import Bitcoind, BitcoindException
from urllib2 import HTTPError

# Configure CointipBot logger
lg = logging.getLogger('cointipbot')
hdlr = logging.StreamHandler()
fmtr = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
hdlr.setFormatter(fmtr)
lg.addHandler(hdlr)
lg.setLevel(logging.DEBUG)
# Configure Bitcoin logger
bt = logging.getLogger('bitcoin')
bt.addHandler(hdlr)
bt.setLevel(logging.DEBUG)

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
        dsn = "mysql+mysqldb://" + str(config['mysql-user']) + ":" + str(config['mysql-pass']) + "@" + str(config['mysql-host']) + ":" + str(config['mysql-port']) + "/" + str(config['mysql-db'])
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
            conn = praw.Reddit(user_agent = config['reddit-useragent'])
            conn.login(config['reddit-user'], config['reddit-pass'])
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
        if 'reddit-batch-limit' in self._config:
            self._REDDIT_BATCH_LIMIT = self._config['reddit-batch-limit']
        if 'bot-sleep-time' in self._config:
            self._DEFAULT_SLEEP_TIME = self._config['sleep-time']

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

    def _check_inbox(self):
        """
        Evaluate new messages in inbox
        """
        lg.debug("> _check_inbox()")

        # Try to fetch some messages
        try:
            messages = self._redditcon.get_unread(limit=self._REDDIT_BATCH_LIMIT)
        except HTTPError, e:
            lg.warning("_check_inbox(): Reddit is down, skipping processing...")
            time.sleep(60)
            return False
        except Exception, e:
            lg.error("_check_inbox(): couldn't fetch messages: %s", str(e))
            return False

        # Process messages
        for m in messages:

            # Ignore replies to bot's comments
            if m.was_comment:
                try:
                    lg.debug("_check_inbox(): ignoring reply to bot's comments")
                    m.mark_as_read()
                    continue
                except HTTPError, e:
                    lg.warning("_check_inbox(): Reddit is down, skipping processing...")
                    time.sleep(60)
                    return False
                except Exception, e:
                    lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                    return False

            # Ignore self messages
            if m.author.name.lower() == self._config['reddit-user'].lower():
                try:
                    lg.debug("_check_inbox(): ignoring message from self")
                    m.mark_as_read()
                    continue
                except HTTPError, e:
                    lg.warning("_check_inbox(): Reddit is down, skipping processing...")
                    time.sleep(60)
                    return False
                except Exception, e:
                    lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                    return False

            # Attempt to evaluate message
            action = ctb_action._eval_message(m, self)

            # Perform action if necessary
            if action != None:
                lg.debug("_check_inbox(): calling action.do() (type %s)...", action._TYPE)
                try:
                    action.do()
                    lg.info("_check_inbox(): executed action %s from message_id %s", action._TYPE, str(m.id))
                except Exception, e:
                    lg.error("_check_inbox(): error executing action %s from message_id %s: %s", action._TYPE, str(m.id), str(e))
                    raise

            # Mark message as read
            try:
                m.mark_as_read()
            except HTTPError, e:
                lg.warning("_check_inbox(): Reddit is down, skipping processing...")
                time.sleep(60)
                return False
            except Exception, e:
                lg.error("_check_inbox(): couldn't mark message as read: %s", str(e))
                return False

        lg.debug("< check_inbox() DONE")
        return True

    def _check_subreddits(self):
        lg.debug("> _check_subreddits()")

        # Get subscribed subreddits
        try:
            my_reddits = self._redditcon.get_my_reddits()
            my_reddits_list = []
            for my_reddit in my_reddits:
                my_reddits_list.append(my_reddit.display_name.lower())
            lg.debug("_check_subreddits(): subreddits: %s", '+'.join(my_reddits_list))
            my_reddits_multi = self._redditcon.get_subreddit('+'.join(my_reddits_list))
        except HTTPError, e:
            lg.warning("_check_subreddits(): Reddit is down, skipping processing...")
            time.sleep(60)
            return False
        except Exception, e:
            lg.error("_check_subreddits(): couldn't fetch subreddits: %s", str(e))
            raise

        # Fetch comments from subreddits
        try:
            my_comments = my_reddits_multi.get_comments(limit=self._REDDIT_BATCH_LIMIT)
        except HTTPError, e:
            lg.warning("_check_subreddits(): Reddit is down, skipping processing...")
            time.sleep(60)
            return False
        except Exception, e:
            lg.error("_check_subreddits(): coudln't fetch comments: %s", str(e))
            raise

        # Process comments until old comment reached
        self._last_processed_comment_time = ctb_misc._get_value(conn=self._mysqlcon, param0="last_processed_comment_time")
        _updated_last_processed_time = 0
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
                lg.debug("_check_subreddits(): calling action.do() (type %s)", action._TYPE)
                try:
                    action.do()
                    lg.info("_check_subreddits(): executed %s from %s", action._TYPE, c.permalink)
                except Exception, e:
                    lg.exception("_check_subreddits(): error doing %s from %s", action._TYPE, c.permalink)
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

