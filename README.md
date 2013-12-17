# Reddit ALTcointip bot

## Introduction

For introduction to and use of ALTcointip bot, see __http://www.reddit.com/r/ALTcointip/wiki/index__

## Getting Started

>**NEW: See [altcointip-chef](https://github.com/vindimy/altcointip-chef) for Chef-automated installation and configuration of ALTcointip bot.**

### Python Dependencies

The following Python libraries are necessary to run ALTcointip bot:

* __jinja2__ (http://jinja.pocoo.org/)
* __pifkoin__ (https://github.com/dpifke/pifkoin)
* __praw__ (https://github.com/praw-dev/praw)
* __sqlalchemy__ (http://www.sqlalchemy.org/)
* __yaml__ (http://pyyaml.org/wiki/PyYAML)

You can install `jinja2`, `praw`, `sqlalchemy`, and `yaml` using `pip` (Python Package Index tool) or a package manager in your OS. For `pifkoin`, you'll need to copy or symlink its "python" subdirectory to `src/ctb/pifkoin`.

### Database

Create a new MySQL database instance and run included SQL file [altcointip.sql](altcointip.sql) to create necessary tables. Create a MySQL user and grant it all privileges on the database. If you don't like to deal with command-line MySQL, use `phpMyAdmin`.

### Coin Daemons

Download one or more coin daemon executable. Create a configuration file for it in appropriate directory (such as `~/.mycoin/mycoin.conf` for Litecoin), specifying `rpcuser`, `rpcpassword`, `rpcport`, and `server=1`, then start the daemon. It will take some time for the daemon to download the blockchain, after which you should verify that it's accepting commands (such as `mycoind getinfo` and `mycoind listaccounts`).

### Reddit Account

You should create a dedicated Reddit account for your bot. Initially, Reddit will ask for CAPTCHA input when bot posts a comment or message. To remove CAPTCHA requirement, the bot account needs to accumulate positive karma.

### Configuration

Copy included set of configuration files [src/conf-sample/](src/conf-sample/) as `src/conf/` and edit `reddit.yml`, `db.yml`, `coins.yml`, and `regex.yml`, specifying necessary settings.

Most configuration options are described inline in provided sample configuration files.

### Running the Bot

1. Ensure MySQL is running and accepting connections given configured username/password
1. Ensure each configured coin daemon is running and responding to commands
1. Ensure Reddit authenticates configured user. _Note that from new users Reddit will require CAPTCHA responses when posting and sending messages. You will be able to type in CAPTCHA responses when required._
1. Execute `_start.sh` from [src](src/) directory. The command will not return for as long as the bot is running.

Here's the first few lines of DEBUG-level console output during successful initialization.

    user@host:/opt/altcointip/altcointip/src$ ./_start.sh
    INFO:cointipbot:CointipBot::init_logging(): -------------------- logging initialized --------------------
    DEBUG:cointipbot:CointipBot::connect_db(): connecting to database...
    INFO:cointipbot:CointipBot::connect_db(): connected to database altcointip as altcointip
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Peercoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/ppcoin/ppcoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:19902
    INFO:cointipbot:CtbCoin::__init__():: connected to Peercoin
    INFO:cointipbot:Setting tx fee of 0.010000
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 4 ms
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Primecoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/primecoin/primecoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:18772
    INFO:cointipbot:CtbCoin::__init__():: connected to Primecoin
    INFO:cointipbot:Setting tx fee of 0.010000
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 1 ms
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Megacoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/megacoin/megacoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:17950
    INFO:cointipbot:CtbCoin::__init__():: connected to Megacoin
    INFO:cointipbot:Setting tx fee of 0.010000
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 1 ms
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Litecoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/litecoin/litecoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:19332
    INFO:cointipbot:CtbCoin::__init__():: connected to Litecoin
    INFO:cointipbot:Setting tx fee of 0.020000
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 2 ms
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Namecoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/namecoin/namecoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:18336
    INFO:cointipbot:CtbCoin::__init__():: connected to Namecoin
    INFO:cointipbot:Setting tx fee of 0.010000
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 1 ms
    DEBUG:cointipbot:CtbCoin::__init__(): connecting to Bitcoin...
    DEBUG:bitcoin:Read 5 parameters from /opt/altcointip/coins/bitcoin/bitcoin.conf
    DEBUG:bitcoin:Making HTTP connection to 127.0.0.1:18332
    INFO:cointipbot:CtbCoin::__init__():: connected to Bitcoin
    INFO:cointipbot:Setting tx fee of 0.000100
    DEBUG:bitcoin:Starting "settxfee" JSON-RPC request
    DEBUG:bitcoin:Got 36 byte response from server in 1 ms
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange crypto-trade.com
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange www.bitstamp.net
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange bter.com
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange blockchain.info
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange campbx.com
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange vircurex.com
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange pubapi.cryptsy.com
    DEBUG:cointipbot:CtbExchange::__init__(): initialized exchange btc-e.com
    DEBUG:cointipbot:CointipBot::connect_reddit(): connecting to Reddit...
    INFO:cointipbot:CointipBot::connect_reddit(): logged in to Reddit as ALTcointip
    ...
    
ALTcointip bot is configured by default to append INFO-level log messages to `logs/info.log`, and WARNING-level log messages to `logs/warning.log`, while DEBUG-level log messages are output to the console.

### Cron: Backups

Backups are very important! The last thing you want is losing user wallets or record of transactions in the databse. 

There are three simple backup scripts included that support backing up database, wallets, and configuration files to local directory and (optionally) to a remote host with `rsync`. Make sure to schedule regular backups with cron and test whether they are actually performed. Example cron configuration:

    0 8,20 * * * cd /opt/altcointip/altcointip/src && python _backup_db.py ~/backups
    0 9,21 * * * cd /opt/altcointip/altcointip/src && python _backup_wallets.py ~/backups
    0 10 * * * cd /opt/altcointip/altcointip/src && python _backup_config.py ~/backups

### Cron: Statistics

ALTcointip bot can be configured to generate tipping statistics pages (overall and per-user) and publish them using subreddit's wiki. After you configure and enable statistics in configuration, add the following cron job to update the main statistics page periodically:

    0 */3 * * * cd /opt/altcointip/altcointip/src && python _update_stats.py
    
### What If I Want To Enable More Cryptocoins Later?

If you want to add a new cryptocoin after you already have a few registered users, you need to retroactively create the new cryptocoin address for users who have already registered. See [src/_add_coin.py](src/_add_coin.py) for details.
