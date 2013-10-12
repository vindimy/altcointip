# Reddit ALTcointip bot

## Introduction

For introduction to and use of ALTcointip bot, see __http://www.reddit.com/r/ALTcointip/wiki/index__

## Getting Started

>**NEW: See [altcointip-chef](https://github.com/vindimy/altcointip-chef) for Chef-automated installation and configuration of ALTcointip bot.**

### Python Dependencies

The following Python libraries are necessary to run ALTcointip bot:

* __jinja2__ (http://jinja.pocoo.org/)
* __pifkoin__ (https://github.com/dpifke/pifkoin)
* __pyvircurex__ (https://github.com/christopherpoole/pyvircurex)
* __praw__ (https://github.com/praw-dev/praw)
* __sqlalchemy__ (http://www.sqlalchemy.org/)
* __yaml__ (http://pyyaml.org/wiki/PyYAML)

You can install _jinja2_, _praw_, _sqlalchemy_, and _yaml_ using _pip_ (Python Package Index tool) or a package manager in your OS. For _pifkoin_, you'll need to copy or symlink its "python" subdirectory to "src/pifkoin". For _pyvircurex_, you'll need to copy or symlink its "vircurex" subdirectory to "src/ctb/pyvircurex".

### Database

Create a new MySQL database instance and run included SQL file _[altcointip.sql](altcointip.sql)_ to create necessary tables. Create a MySQL user and grant it all privileges on the database. If you don't like to deal with command-line MySQL, use _phpMyAdmin_.

### Coin Daemons

Download one or more coin daemon executable. Create a configuration file for it in appropriate directory (such as `~/.litecoin/litecoin.conf` for Litecoin), specifying `rpcuser`, `rpcpassword`, `rpcport`, and `server=1`, then start the daemon. It will take some time for the daemon to download the blockchain, after which you should verify that it's accepting commands (such as `getinfo`).

### Reddit Account

You should create a dedicated Reddit account for your bot. Initially, Reddit will ask for CAPTCHA input when bot posts a comment or message. To remove CAPTCHA requirement, the bot account needs to accumulate positive karma.

### Configuration

Rename or copy included _[src/sample-config.yml](src/sample-config.yml)_ to _src/config.yml_ and configure necessary settings. Configure at least one type of cryptocoin in _cc_ section.

Most configuration options are self-explanatory, the ones that are not are explained below.

* _reddit.scan.my-subreddits_: If true, scan subscribed subreddits for new comments (not recommended).
* _reddit.scan.these-subreddits_: If specified, scan given subreddits for comments (not recommended).
* _reddit.scan.ignore-subreddits_: If specified, ignore given subreddits (when these-subreddits is specified) - Reddit Gold required.

>__Note:__ Setting _reddit.scan.my-subreddits_ to false and not specifying _reddit.scan.these-subreddits_ will result in ALTcointip bot checking its inbox only. In such case the bot will rely on the Reddit Gold "mention" feature, where users "mention" bot's username when tipping (such as +/u/mybotuser 1 ltc). Reddit "mention" feature is the most reliable way to operate ALTcointip bot.

* _misc.subtract-txfee_: If true, network transaction fee is subtracted from the amount specified (when required). Otherwise, it is added to the amount specified. If you'd like to disable transaction fees (not recommended), set _cc.COIN.txfee_ setting to `0.0` for particular _COIN_.

* _regex.keywords_: Regular expressions that are used to recognize commands like tipping, info, and withdrawing. Make sure that your tipping keywords are unique on Reddit, otherwise it will conflict with other tip bots.

* _kw_: Here you can define keywords that can be used in place of amount. You can specify a float value, or a string of Python code that will be executed (from within `CtbAction::__init()__`) to determine the value. The string of Python code should return a float. Don't forget to update _regex.amount.keyword_ when you make changes to _kw_.

* _logging_: Provide INFO-level and DEBUG-level filename to which ALTcointip bot will log its activity. On Unix/Linux, you can use `tail -f filename.log` to monitor the log file.

* _fiat_: Fiat (such as USD) parameters are defined here. At the very least, _fiat.usd_ is required.

* _cc_: Each cryptocoin (such as Litecoin) parameters are defined here. At least one cryptocoin needs to be configured. A few cryptocoin configurations are provided (but disabled) for your convenience. Set _cc.COIN.enabled_ to _true_ to enable particular cryptocoin.

>__Note:__ You can see that ALTcointip is relying on coin daemon configuration file in order to connect to coin daemon. For example, _cc.ltc.conf-file_ provides the location of Litecoin coin daemon configuration file. The following settings should be specified in the coin daemon configuration file:

>* rpcuser
>* rpcpassword
>* rpcport
>* server=1

* _cc.COIN.minconf_: Minimum number of network confirmations required before balance is available. "givetip" is non-network transaction, so the setting is set to 1, while "withdraw" is a network transaction, so the setting is set to a higher value.

* _cc.COIN.walletpassphrase_: For coin daemons that support wallet encryption, you can encrypt the wallet and specify encryption password using this setting. ALTcointip bot will only unlock the wallet when performing a network transaction (such as "withdraw").

### Running the Bot

1. Ensure MySQL is running and accepting connections given configured username/password
1. Ensure each configured coin daemon is running and responding to commands
1. Ensure Reddit authenticates configured user. _Note that from new users Reddit will require CAPTCHA responses when posting and sending messages. You will be able to type in CAPTCHA responses._
1. Execute `python _run.py` from _[src](src/)_ directory. The command will not return for as long as the bot is running.
1. Monitor configured INFO-level or DEBUG-level log file wth `tail -f filename.log` where _filename.log_ is the log file name you've configured (on Unix/Linux).

Here's the first few lines of INFO-level log after successful initialization:

    INFO 2013-06-19 06:51:12,216 CointipBot::_init_logging(): -------------------- logging initialized --------------------
    INFO 2013-06-19 06:51:12,217 Logging level INFO to ctb-info.log
    INFO 2013-06-19 06:51:12,417 Connected to database
    INFO 2013-06-19 06:51:12,418 Connected to Peercoin
    INFO 2013-06-19 06:51:12,418 Setting tx fee of 0.010000
    INFO 2013-06-19 06:51:12,421 Connected to Litecoin
    INFO 2013-06-19 06:51:12,421 Setting tx fee of 0.010000
    INFO 2013-06-19 06:51:12,423 Connected to Novacoin
    INFO 2013-06-19 06:51:12,423 Setting tx fee of 0.010000
    INFO 2013-06-19 06:51:12,426 Connected to Namecoin
    INFO 2013-06-19 06:51:12,426 Setting tx fee of 0.010000
    INFO 2013-06-19 06:51:12,428 Connected to Terracoin
    INFO 2013-06-19 06:51:12,428 Setting tx fee of 0.010000
    INFO 2013-06-19 06:51:12,430 Connected to Devcoin
    INFO 2013-06-19 06:51:12,431 Setting tx fee of 1.000000
    INFO 2013-06-19 06:51:15,132 Logged in to Reddit
    INFO 2013-06-19 06:51:25,492 < CointipBot::__init__(): DONE, batch-limit = 99999, sleep-seconds = 30

### Backups

Backups are very important! The last thing you want is losing user wallets or record of transactions in the databse. 

There are two simple backup scripts included (`src/_backup_db.py` and `src/_backup_wallets.py`) that support backup to local directory and (optionally) to a remote host with `rsync`. Here's a `crontab` crontab entry scheduling a backup every 15 minutes to a local directory `~/backups` as well as to remote server `my-server-1.example.com:backups/`:

    */15    *       *       *       *       cd ~/git/altcointip/src && python _backup_db.py ~/backups my-server-1.example.com:backups/ && python _backup_wallets.py ~/backups my-server-1.example.com:backups/
    
Make sure to create all destination directories, and test whether backup is actually being performed.
    
### What If I Want To Enable More Cryptocoins Later?

If you want to add a new cryptocoin after you already have a few registered users, you need to retroactively create the new cryptocoin address for users who have already registered. See _[src/_add_coin.py](src/_add_coin.py)_ for details on how to do that.
