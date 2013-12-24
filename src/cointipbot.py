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

from ctb import ctb_action, ctb_coin, ctb_db, ctb_exchange, ctb_log, ctb_misc, ctb_user

import gettext, locale, logging, praw, smtplib, sys, time, traceback, yaml
from email.mime.text import MIMEText
from jinja2 import Environment, PackageLoader

from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout

# Configure CointipBot logger
logging.basicConfig()
lg = logging.getLogger('cointipbot')


class CointipBot(object):
    """
    Main class for cointip bot
    """

    conf = None
    db = None
    reddit = None
    coins = {}
    exchanges = {}
    jenv = None
    runtime = {'ev': {}, 'regex': []}

    def init_logging(self):
        """
        Initialize logging handlers
        """

        handlers = {}
        levels = ['warning', 'info', 'debug']
        lg = logging.getLogger('cointipbot')
        bt = logging.getLogger('bitcoin')

        # Get handlers
        handlers = {}
        for l in levels:
            if self.conf.logs.levels[l].enabled:
                handlers[l] = logging.FileHandler(self.conf.logs.levels[l].filename, mode='a' if self.conf.logs.levels[l].append else 'w')
                handlers[l].setFormatter(logging.Formatter(self.conf.logs.levels[l].format))

        # Set handlers
        for l in levels:
            if handlers.has_key(l):
                level = logging.WARNING if l == 'warning' else (logging.INFO if l == 'info' else logging.DEBUG)
                handlers[l].addFilter(ctb_log.LevelFilter(level))
                lg.addHandler(handlers[l])
                bt.addHandler(handlers[l])

        # Set default levels
        lg.setLevel(logging.DEBUG)
        bt.setLevel(logging.DEBUG)

        lg.info('CointipBot::init_logging(): -------------------- logging initialized --------------------')
        return True

    def parse_config(self):
        """
        Returns a Python object with CointipBot configuration
        """
        lg.debug('CointipBot::parse_config(): parsing config files...')

        conf = {}
        try:
            prefix='./conf/'
            for i in ['coins', 'db', 'exchanges', 'fiat', 'keywords', 'logs', 'misc', 'reddit', 'regex']:
                lg.debug("CointipBot::parse_config(): reading %s%s.yml", prefix, i)
                conf[i] = yaml.load(open(prefix+i+'.yml'))
        except yaml.YAMLError as e:
            lg.error("CointipBot::parse_config(): error reading config file: %s", e)
            if hasattr(e, 'problem_mark'):
                lg.error("CointipBot::parse_config(): error position: (line %s, column %s)", e.problem_mark.line+1, e.problem_mark.column+1)
            sys.exit(1)

        lg.info('CointipBot::parse_config(): config files has been parsed')
        return ctb_misc.DotDict(conf)

    def connect_db(self):
        """
        Returns a database connection object
        """
        lg.debug('CointipBot::connect_db(): connecting to database...')

        dsn = "mysql+mysqldb://%s:%s@%s:%s/%s?charset=utf8" % (self.conf.db.auth.user, self.conf.db.auth.password, self.conf.db.auth.host, self.conf.db.auth.port, self.conf.db.auth.dbname)
        dbobj = ctb_db.CointipBotDatabase(dsn)

        try:
            conn = dbobj.connect()
        except Exception as e:
            lg.error("CointipBot::connect_db(): error connecting to database: %s", e)
            sys.exit(1)

        lg.info("CointipBot::connect_db(): connected to database %s as %s", self.conf.db.auth.dbname, self.conf.db.auth.user)
        return conn

    def connect_reddit(self):
        """
        Returns a praw connection object
        """
        lg.debug('CointipBot::connect_reddit(): connecting to Reddit...')

        conn = praw.Reddit(user_agent = self.conf.reddit.auth.user)
        conn.login(self.conf.reddit.auth.user, self.conf.reddit.auth.password)

        lg.info("CointipBot::connect_reddit(): logged in to Reddit as %s", self.conf.reddit.auth.user)
        return conn

    def self_checks(self):
        """
        Run self-checks before starting the bot
        """

        # Ensure bot is a registered user
        b = ctb_user.CtbUser(name=self.conf.reddit.auth.user.lower(), ctb=self)
        if not b.is_registered():
            b.register()

        # Ensure (total pending tips) < (CointipBot's balance)
        for c in self.coins:
            ctb_balance = b.get_balance(coin=c, kind='givetip')
            pending_tips = float(0)
            actions = ctb_action.get_actions(atype='givetip', state='pending', coin=c, ctb=self)
            for a in actions:
                pending_tips += a.coinval
            if (ctb_balance - pending_tips) < -0.000001:
                raise Exception("CointipBot::self_checks(): CointipBot's %s balance (%s) < total pending tips (%s)" % (c.upper(), ctb_balance, pending_tips))

        # Ensure coin balances are positive
        for c in self.coins:
            b = float(self.coins[c].conn.getbalance())
            if b < 0:
                raise Exception("CointipBot::self_checks(): negative balance of %s: %s" % (c, b))

        # Ensure user accounts are intact and balances are not negative
        sql = "SELECT username FROM t_users ORDER BY username"
        for mysqlrow in self.db.execute(sql):
            u = ctb_user.CtbUser(name=mysqlrow['username'], ctb=self)
            if not u.is_registered():
                raise Exception("CointipBot::self_checks(): user %s is_registered() failed" % mysqlrow['username'])
        #    for c in vars(self.coins):
        #        if u.get_balance(coin=c, kind='givetip') < 0:
        #            raise Exception("CointipBot::self_checks(): user %s %s balance is negative" % (mysqlrow['username'], c))

        return True

    def expire_pending_tips(self):
        """
        Decline any pending tips that have reached expiration time limit
        """

        # Calculate timestamp
        seconds = int(self.conf.misc.times.expire_pending_hours * 3600)
        created_before = time.mktime(time.gmtime()) - seconds
        counter = 0

        # Get expired actions and decline them
        for a in ctb_action.get_actions(atype='givetip', state='pending', created_utc='< ' + str(created_before), ctb=self):
            a.expire()
            counter += 1

        # Done
        return (counter > 0)

    def check_inbox(self):
        """
        Evaluate new messages in inbox
        """
        lg.debug('> CointipBot::check_inbox()')

        try:

            # Try to fetch some messages
            messages = list(ctb_misc.praw_call(self.reddit.get_unread, limit=self.conf.reddit.scan.batch_limit))
            messages.reverse()

            # Process messages
            for m in messages:
                # Sometimes messages don't have an author (such as 'you are banned from' message)
                if not m.author:
                    lg.info("CointipBot::check_inbox(): ignoring msg with no author")
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                lg.info("CointipBot::check_inbox(): %s from %s", "comment" if m.was_comment else "message", m.author.name)

                # Ignore duplicate messages (sometimes Reddit fails to mark messages as read)
                if ctb_action.check_action(msg_id=m.id, ctb=self):
                    lg.warning("CointipBot::check_inbox(): duplicate action detected (msg.id %s), ignoring", m.id)
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                # Ignore self messages
                if m.author and m.author.name.lower() == self.conf.reddit.auth.user.lower():
                    lg.debug("CointipBot::check_inbox(): ignoring message from self")
                    ctb_misc.praw_call(m.mark_as_read)
                    continue

                # Ignore messages from banned users
                if m.author and self.conf.reddit.banned_users:
                    lg.debug("CointipBot::check_inbox(): checking whether user '%s' is banned..." % m.author)
                    u = ctb_user.CtbUser(name = m.author.name, redditobj = m.author, ctb = self)
                    if u.banned:
                        lg.info("CointipBot::check_inbox(): ignoring banned user '%s'" % m.author)
                        ctb_misc.praw_call(m.mark_as_read)
                        continue

                action = None
                if m.was_comment:
                    # Attempt to evaluate as comment / mention
                    action = ctb_action.eval_comment(m, self)
                else:
                    # Attempt to evaluate as inbox message
                    action = ctb_action.eval_message(m, self)

                # Perform action, if found
                if action:
                    lg.info("CointipBot::check_inbox(): %s from %s (m.id %s)", action.type, action.u_from.name, m.id)
                    lg.debug("CointipBot::check_inbox(): message body: <%s>", m.body)
                    action.do()
                else:
                    lg.info("CointipBot::check_inbox(): no match")
                    if self.conf.reddit.messages.sorry and not m.subject in ['post reply', 'comment reply']:
                        user = ctb_user.CtbUser(name=m.author.name, redditobj=m.author, ctb=self)
                        tpl = self.jenv.get_template('didnt-understand.tpl')
                        msg = tpl.render(user_from=user.name, what='comment' if m.was_comment else 'message', source_link=m.permalink if hasattr(m, 'permalink') else None, ctb=self)
                        lg.debug("CointipBot::check_inbox(): %s", msg)
                        user.tell(subj='What?', msg=msg, msgobj=m if not m.was_comment else None)

                # Mark message as read
                ctb_misc.praw_call(m.mark_as_read)

        except (HTTPError, ConnectionError, Timeout, timeout) as e:
            lg.warning("CointipBot::check_inbox(): Reddit is down (%s), sleeping", e)
            time.sleep(self.conf.misc.times.sleep_seconds)
            pass
        except RateLimitExceeded as e:
             lg.warning("CointipBot::check_inbox(): rate limit exceeded, sleeping for %s seconds", e.sleep_time) 
             time.sleep(e.sleep_time)
             time.sleep(1)
             pass
        except Exception as e:
            lg.error("CointipBot::check_inbox(): %s", e)
            raise

        lg.debug("< CointipBot::check_inbox() DONE")
        return True

    def init_subreddits(self):
        """
        Determine a list of subreddits and create a PRAW object
        """
        lg.debug("> CointipBot::init_subreddits()")

        try:

            if not hasattr(self.conf.reddit, 'subreddits'):
                my_reddits_list = None
                my_reddits_string = None

                if hasattr(self.conf.reddit.scan, 'these_subreddits'):
                    # Subreddits are specified in conf.yml
                    my_reddits_list = list(self.conf.reddit.scan.these_subreddits)

                elif self.conf.reddit.scan.my_subreddits:
                    # Subreddits are subscribed to by bot user
                    my_reddits = ctb_misc.praw_call(self.reddit.get_my_subreddits, limit=None)
                    my_reddits_list = []
                    for my_reddit in my_reddits:
                        my_reddits_list.append(my_reddit.display_name.lower())
                    my_reddits_list.sort()

                else:
                    # No subreddits configured
                    lg.debug("< CointipBot::check_subreddits() DONE (no subreddits configured to scan)")
                    return False

                # Build subreddits string
                my_reddits_string = "+".join(my_reddits_list)

                # Get multi-reddit PRAW object
                lg.debug("CointipBot::check_subreddits(): multi-reddit string: %s", my_reddits_string)
                self.conf.reddit.subreddits = ctb_misc.praw_call(self.reddit.get_subreddit, my_reddits_string)

        except Exception as e:
            lg.error("CointipBot::check_subreddits(): coudln't get subreddits: %s", e)
            raise

        lg.debug("< CointipBot::init_subreddits() DONE")
        return True

    def check_subreddits(self):
        """
        Evaluate new comments from configured subreddits
        """
        lg.debug("> CointipBot::check_subreddits()")

        try:
            # Process comments until old comment reached

            # Get last_processed_comment_time if necessary
            if not hasattr(self.conf.reddit, 'last_processed_comment_time') or self.conf.reddit.last_processed_comment_time <= 0:
                self.conf.reddit.last_processed_comment_time = ctb_misc.get_value(conn=self.db, param0='last_processed_comment_time')
            updated_last_processed_time = 0

            # Fetch comments from subreddits
            my_comments = ctb_misc.praw_call(self.conf.reddit.subreddits.get_comments, limit=self.conf.reddit.scan.batch_limit)

            # Match each comment against regex
            counter = 0
            for c in my_comments:
                # Stop processing if old comment reached
                #lg.debug("check_subreddits(): c.id %s from %s, %s <= %s", c.id, c.subreddit.display_name, c.created_utc, self.conf.reddit.last_processed_comment_time)
                if c.created_utc <= self.conf.reddit.last_processed_comment_time:
                    lg.debug("CointipBot::check_subreddits(): old comment reached")
                    break
                counter += 1
                if c.created_utc > updated_last_processed_time:
                    updated_last_processed_time = c.created_utc

                # Ignore duplicate comments (may happen when bot is restarted)
                if ctb_action.check_action(msg_id=c.id, ctb=self):
                    lg.warning("CointipBot::check_inbox(): duplicate action detected (comment.id %s), ignoring", c.id)
                    continue

                # Ignore comments from banned users
                if c.author and self.conf.reddit.banned_users:
                    lg.debug("CointipBot::check_subreddits(): checking whether user '%s' is banned..." % c.author)
                    u = ctb_user.CtbUser(name = c.author.name, redditobj = c.author, ctb = self)
                    if u.banned:
                        lg.info("CointipBot::check_subreddits(): ignoring banned user '%s'" % c.author)
                        continue

                # Attempt to evaluate comment
                action = ctb_action.eval_comment(c, self)

                # Perform action, if found
                if action:
                    lg.info("CointipBot::check_subreddits(): %s from %s (%s)", action.type, action.u_from.name, c.id)
                    lg.debug("CointipBot::check_subreddits(): comment body: <%s>", c.body)
                    action.do()
                else:
                    lg.info("CointipBot::check_subreddits(): no match")

            lg.debug("CointipBot::check_subreddits(): %s comments processed", counter)
            if counter >= self.conf.reddit.scan.batch_limit - 1:
                lg.warning("CointipBot::check_subreddits(): conf.reddit.scan.batch_limit (%s) was not large enough to process all comments", self.conf.reddit.scan.batch_limit)

        except (HTTPError, RateLimitExceeded, timeout) as e:
            lg.warning("CointipBot::check_subreddits(): Reddit is down (%s), sleeping", e)
            time.sleep(self.conf.misc.times.sleep_seconds)
            pass
        except Exception as e:
            lg.error("CointipBot::check_subreddits(): coudln't fetch comments: %s", e)
            raise

        # Save updated last_processed_time value
        if updated_last_processed_time > 0:
            self.conf.reddit.last_processed_comment_time = updated_last_processed_time
        ctb_misc.set_value(conn=self.db, param0='last_processed_comment_time', value0=self.conf.reddit.last_processed_comment_time)

        lg.debug("< CointipBot::check_subreddits() DONE")
        return True

    def refresh_ev(self):
        """
        Refresh coin/fiat exchange values using self.exchanges
        """

        # Return if rate has been checked in the past hour
        seconds = int(1 * 3600)
        if hasattr(self.conf.exchanges, 'last_refresh') and self.conf.exchanges.last_refresh + seconds > int(time.mktime(time.gmtime())):
            lg.debug("< CointipBot::refresh_ev(): DONE (skipping)")
            return

        # For each enabled coin...
        for c in vars(self.conf.coins):
            if self.conf.coins[c].enabled:

                # Get BTC/coin exchange rate
                values = []
                result = 0.0

                if not self.conf.coins[c].unit == 'btc':
                    # For each exchange that supports this coin...
                    for e in self.exchanges:
                        if self.exchanges[e].supports_pair(_name1=self.conf.coins[c].unit, _name2='btc'):
                            # Get ticker value from exchange
                            value = self.exchanges[e].get_ticker_value(_name1=self.conf.coins[c].unit, _name2='btc')
                            if value and float(value) > 0.0:
                                values.append(float(value))

                    # Result is average of all responses
                    if len(values) > 0:
                        result = sum(values) / float(len(values))

                else:
                    # BTC/BTC rate is always 1
                    result = 1.0

                # Assign result to self.runtime['ev']
                if not self.runtime['ev'].has_key(c):
                    self.runtime['ev'][c] = {}
                self.runtime['ev'][c]['btc'] = result

        # For each enabled fiat...
        for f in vars(self.conf.fiat):
            if self.conf.fiat[f].enabled:

                # Get fiat/BTC exchange rate
                values = []
                result = 0.0

                # For each exchange that supports this fiat...
                for e in self.exchanges:
                    if self.exchanges[e].supports_pair(_name1='btc', _name2=self.conf.fiat[f].unit):
                        # Get ticker value from exchange
                        value = self.exchanges[e].get_ticker_value(_name1='btc', _name2=self.conf.fiat[f].unit)
                        if value and float(value) > 0.0:
                            values.append(float(value))

                # Result is average of all responses
                if len(values) > 0:
                    result = sum(values) / float(len(values))

                # Assign result to self.runtime['ev']
                if not self.runtime['ev'].has_key('btc'):
                    self.runtime['ev']['btc'] = {}
                self.runtime['ev']['btc'][f] = result

        lg.debug("CointipBot::refresh_ev(): %s", self.runtime['ev'])

        # Update last_refresh
        self.conf.exchanges.last_refresh = int(time.mktime(time.gmtime()))

    def coin_value(self, _coin, _fiat):
        """
        Quick method to return _fiat value of _coin
        """
        try:
            value = self.runtime['ev'][_coin]['btc'] * self.runtime['ev']['btc'][_fiat]
        except KeyError as e:
            lg.warning("CointipBot::coin_value(%s, %s): KeyError", _coin, _fiat)
            value = 0.0
        return value

    def notify(self, _msg=None):
        """
        Send _msg to configured destination
        """

        # Construct MIME message
        msg = MIMEText(_msg)
        msg['Subject'] = self.conf.misc.notify.subject
        msg['From'] = self.conf.misc.notify.addr_from
        msg['To'] = self.conf.misc.notify.addr_to

        # Send MIME message
        server = smtplib.SMTP(self.conf.misc.notify.smtp_host)
        if self.conf.misc.notify.smtp_tls:
            server.starttls()
        server.login(self.conf.misc.notify.smtp_username, self.conf.misc.notify.smtp_password)
        server.sendmail(self.conf.misc.notify.addr_from, self.conf.misc.notify.addr_to, msg.as_string())
        server.quit()

    def __init__(self, self_checks=True, init_reddit=True, init_coins=True, init_exchanges=True, init_db=True, init_logging=True):
        """
        Constructor. Parses configuration file and initializes bot.
        """
        lg.info("CointipBot::__init__()...")

        # Configuration
        self.conf = self.parse_config()

        # Logging
        if init_logging:
            self.init_logging()

        # Templating with jinja2
        self.jenv = Environment(trim_blocks=True, loader=PackageLoader('cointipbot', 'tpl/jinja2'))

        # Database
        if init_db:
            self.db = self.connect_db()

        # Coins
        if init_coins:
            for c in vars(self.conf.coins):
                if self.conf.coins[c].enabled:
                    self.coins[c] = ctb_coin.CtbCoin(_conf=self.conf.coins[c])
            if not len(self.coins) > 0:
                lg.error("CointipBot::__init__(): Error: please enable at least one type of coin")
                sys.exit(1)

        # Exchanges
        if init_exchanges:
            for e in vars(self.conf.exchanges):
                if self.conf.exchanges[e].enabled:
                    self.exchanges[e] = ctb_exchange.CtbExchange(_conf=self.conf.exchanges[e])
            if not len(self.exchanges) > 0:
                lg.warning("Cointipbot::__init__(): Warning: no exchanges are enabled")

        # Reddit
        if init_reddit:
            self.reddit = self.connect_reddit()
            self.init_subreddits()
            # Regex for Reddit messages
            ctb_action.init_regex(self)

        # Self-checks
        if self_checks:
            self.self_checks()

        lg.info("< CointipBot::__init__(): DONE, batch-limit = %s, sleep-seconds = %s", self.conf.reddit.scan.batch_limit, self.conf.misc.times.sleep_seconds)

    def __str__(self):
        """
        Return string representation of self
        """
        me = "<CointipBot: sleepsec=%s, batchlim=%s, ev=%s"
        me = me % (self.conf.misc.times.sleep_seconds, self.conf.reddit.scan.batch_limit, self.runtime['ev'])
        return me

    def main(self):
        """
        Main loop
        """

        while (True):
            try:
                lg.debug("CointipBot::main(): beginning main() iteration")

                # Refresh exchange rate values
                self.refresh_ev()

                # Check personal messages
                self.check_inbox()

                # Expire pending tips
                self.expire_pending_tips()

                # Check subreddit comments for tips
                if self.conf.reddit.scan.my_subreddits or hasattr(self.conf.reddit.scan, 'these_subreddits'):
                    self.check_subreddits()

                # Sleep
                lg.debug("CointipBot::main(): sleeping for %s seconds...", self.conf.misc.times.sleep_seconds)
                time.sleep(self.conf.misc.times.sleep_seconds)

            except Exception as e:
                lg.error("CointipBot::main(): exception: %s", e)
                tb = traceback.format_exc()
                lg.error("CointipBot::main(): traceback: %s", tb)
                # Send a notification, if enabled
                if self.conf.misc.notify.enabled:
                    self.notify(_msg=tb)
                sys.exit(1)
