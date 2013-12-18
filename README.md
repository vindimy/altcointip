# Reddit dogetipbot

## Introduction

This is dogetipbot. It's based on vindimy's alcontipbot, but massively optimized and focused on dogecoin.
And when I say focused, I mean... really focused. the volume dogetipbot pushes on the regular is absurd. :O

mad props to vindimy for doing the heavy lifting. I'm hoping to contribute back as much as I can.

Also I tend to be pretty damn laid back and my python isn't as good as my perl, so deal with me. :Package
--mohland

## Getting Started

### Python Dependencies

The following Python libraries are necessary to run ALTcointip bot:

* __jinja2__ (http://jinja.pocoo.org/)
* __pifkoin__ (https://github.com/dpifke/pifkoin)
* __praw__ (https://github.com/praw-dev/praw)
* __sqlalchemy__ (http://www.sqlalchemy.org/)
* __yaml__ (http://pyyaml.org/wiki/PyYAML)

You can install _jinja2_, _praw_, _sqlalchemy_, and _yaml_ using _pip_ (Python Package Index tool) or a package manager in your OS. For _pifkoin_, you'll need to copy or symlink its "python" subdirectory to "src/ctb/pifkoin".

### Database

Create a new MySQL database instance and run included SQL file _[altcointip.sql](altcointip.sql)_ to create necessary tables. Create a MySQL user and grant it all privileges on the database. If you don't like to deal with command-line MySQL, use _phpMyAdmin_.

### Coin Daemons

Download one or more coin daemon executable. Create a configuration file for it in appropriate directory (such as `~/.litecoin/litecoin.conf` for Litecoin), specifying `rpcuser`, `rpcpassword`, `rpcport`, and `server=1`, then start the daemon. It will take some time for the daemon to download the blockchain, after which you should verify that it's accepting commands (such as `getinfo`).

### Reddit Account

You should create a dedicated Reddit account for your bot. Initially, Reddit will ask for CAPTCHA input when bot posts a comment or message. To remove CAPTCHA requirement, the bot account needs to accumulate positive karma.

### Configuration

Copy included set of configuration files _[src/conf-sample/](src/conf-sample/)_ as _src/conf/_ and edit `reddit.yml`, `db.yml`, and `coins.yml`, specifying necessary settings.

Most configuration options are described inline in provided sample configuration files.

### Running the Bot

1. Ensure MySQL is running and accepting connections given configured username/password
1. Ensure each configured coin daemon is running and responding to commands
1. Ensure Reddit authenticates configured user. _Note that from new users Reddit will require CAPTCHA responses when posting and sending messages. You will be able to type in CAPTCHA responses._
1. Execute `_start.sh` from _[src](src/)_ directory. The command will not return for as long as the bot is running.
1. Monitor configured INFO-level or DEBUG-level log file wth `tail -f filename.log` (where _filename.log_ is the log file name you've configured).

Here's the first few lines of INFO-level log after successful initialization:

    INFO 2013-10-31 08:02:40,420 CointipBot::init_logging(): -------------------- logging initialized --------------------
    INFO 2013-10-31 08:02:40,450 CointipBot::connect_db(): connected to database altcointip as altcointip
    INFO 2013-10-31 08:02:40,451 CtbCoin::__init__():: connected to Peercoin
    INFO 2013-10-31 08:02:40,451 Setting tx fee of 0.010000
    INFO 2013-10-31 08:02:40,456 CtbCoin::__init__():: connected to Primecoin
    INFO 2013-10-31 08:02:40,456 Setting tx fee of 0.010000
    INFO 2013-10-31 08:02:40,459 CtbCoin::__init__():: connected to Litecoin
    INFO 2013-10-31 08:02:40,459 Setting tx fee of 0.020000
    INFO 2013-10-31 08:02:40,461 CtbCoin::__init__():: connected to Feathercoin
    INFO 2013-10-31 08:02:40,462 Setting tx fee of 0.010000
    INFO 2013-10-31 08:02:40,464 CtbCoin::__init__():: connected to Namecoin
    INFO 2013-10-31 08:02:40,465 Setting tx fee of 0.010000
    INFO 2013-10-31 08:02:40,468 CtbCoin::__init__():: connected to Bitcoin
    INFO 2013-10-31 08:02:40,468 Setting tx fee of 0.000100
    INFO 2013-10-31 08:02:42,784 CointipBot::connect_reddit(): logged in to Reddit as ALTcointip
    INFO 2013-10-31 08:02:42,792 CtbUser::balance(altcointip): getting ppc givetip balance
    INFO 2013-10-31 08:02:42,798 CtbUser::balance(altcointip): getting xpm givetip balance
    INFO 2013-10-31 08:02:42,805 CtbUser::balance(altcointip): getting ltc givetip balance
    INFO 2013-10-31 08:02:42,814 CtbUser::balance(altcointip): getting ftc givetip balance
    INFO 2013-10-31 08:02:42,818 CtbUser::balance(altcointip): getting nmc givetip balance
    INFO 2013-10-31 08:02:42,933 CtbUser::balance(altcointip): getting btc givetip balance
    INFO 2013-10-31 08:02:43,459 < CointipBot::__init__(): DONE, batch-limit = 1000, sleep-seconds = 60

### Backups

Backups are very important! The last thing you want is losing user wallets or record of transactions in the databse. 

There are three simple backup scripts included that support backing up database, wallets, and configuration files to local directory and (optionally) to a remote host with `rsync`. Make sure to schedule regular backups and test whether they are actually performed.
    
### What If I Want To Enable More Cryptocoins Later?

If you want to add a new cryptocoin after you already have a few registered users, you need to retroactively create the new cryptocoin address for users who have already registered. See _[src/_add_coin.py](src/_add_coin.py)_ for details on how to do that.
