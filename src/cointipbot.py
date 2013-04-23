#!/usr/bin/env python

import ctbutil

import sys
import logging
import yaml
import sqlalchemy
import praw
from pifkoin.bitcoind import Bitcoind, BitcoindException

logger = logging.getLogger('cointipbot')
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

class CointipBot(object):
    """
    Main class for cointip bot
    """

    _DEFAULT_CONFIG_FILENAME = './config.yaml'
    _mysqlcon = None
    _bitcoindcon = None
    _litecoindcon = None
    _ppcoindcon = None
    _redditcon = None

    def _parse_config(self, filename=_DEFAULT_CONFIG_FILENAME):
        """
        Returns a Python object with CointipBot configuration

        :param filename:
            The filename from which the configuration should be read.  Defaults
            to ``./config.yaml``.
        """
        try:
            config = yaml.load(open(filename))
        except yaml.YAMLError, e:
            logger.error("Error reading config file "+filename)
            if hasattr(e, 'problem_mark'):
                logger.error("Error position: (line "+str(e.problem_mark.line+1)+", column "+str(e.problem_mark.column+1));
            sys.exit(1)
        logger.info("Config file has been read")
        return config

    def _connect_db(self, config):
        """
        Returns a database connection object
        """
        dsn = "mysql+mysqldb://" + config['mysql-user'] + ":" + config['mysql-pass'] + "@" + config['mysql-host'] + "/" + config['mysql-db']
        dbobj = ctbutil.db.CointipBotDatabase(dsn)
        try:
            conn = dbobj.connect()
        except sqlalchemy.SQLAlchemyError, e:
            logger.error("Error connecting to database: "+str(e))
            sys.exit(1)
        logger.info("Connected to database")
        return conn

    def _connect_bitcoind(self, config):
        """
        Returns a bitcoind connection object
        """
        try:
            conn = Bitcoind('~/.bitcoin/bitcoin.conf')
        except BitcoindException, e:
            logger.error("Error connecting to bitcoind: "+str(e))
            sys.exit(1)
        logger.info("Connected to bitcoind")
        return conn

    def _connect_litecoind(self, config):
        """
        Returns a litecoind connection object
        """
        try:
            conn = Bitcoind('~/.litecoin/litecoin.conf')
        except BitcoindException, e:
            logger.error("Error connecting to litecoind: "+str(e))
            sys.exit(1)
        logger.info("Connected to litecoind")
        return conn

    def _connect_ppcoind(self, config):
        """
        Returns a ppcoind connection object
        """
        try:
            conn = Bitcoind('~/.ppcoin/bitcoin.conf')
        except BitcoindException, e:
            logger.error("Error connecting to ppcoind: "+str(e))
            sys.exit(1)
        logger.info("Connected to ppcoind")
        return conn

    def _connect_reddit(self, config):
        """
        Returns a praw connection object
        """
        try:
            conn = praw.Reddit(user_agent = config['reddit-useragent'])
            conn.login(config['reddit-user'], config['reddit-pass'])
        except Exception, e:
            logger.error("Error connecting to Reddit: "+str(e))
            sys.exit(1)
        logger.info("Logged in to Reddit")
        return conn

    def __init__(self, config_filename=_DEFAULT_CONFIG_FILENAME):
        """
        Constructor.
        Parses configuration file and initializes bot.
        """
        _config = self._parse_config(config_filename)
        _mysqlcon = self._connect_db(_config)
        if _config['bitcoind-enabled']:
            _bitcoindcon = self._connect_bitcoin(_config)
        if _config['litecoind-enabled']:
            _litecoindcon = self._connect_litecoind(_config)
        if _config['ppcoind-enabled']:
            _ppcoindcon = self._connect_ppcoin(_config)
        _redditcon = self._connect_reddit(_config)

