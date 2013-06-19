# Reddit ALTcointip bot

## Introduction

For introduction and how to use ALTcointip bot, see http://www.reddit.com/r/ALTcointip/wiki/index

## Getting Started

### Python Dependencies

The following Python libraries are necessary to run ALTcointip bot:

* praw (https://github.com/praw-dev/praw)
* pifkoin (https://github.com/dpifke/pifkoin)

You can install praw using pip or built-in package manager. For _pifkoin_, you'll need to copy or symlink contents of "python" subdirectory to "src/pifkoin".

### Database

Create a new MySQL database instance and run included SQL file altcointip.sql to create necessary tables. Create a MySQL user and grant it all privileges on the database. If you don't like to deal with command-line MySQL, use phpMyAdmin.

### Configuration

Rename or copy included _sample-config.yml_ to _config.yml_ and configure necessary settings. Configure at least one type of cryptocoin in _cc_ section.

Most configuration options are self-explanatory, the ones that are not are explaines below.

* _reddit.scan.my-subreddits_: If true, scan subscribed subreddits for new comments (not recommended).
* _reddit.scan.these-subreddits_: If specified, scan given subreddits for comments (not recommended).
* _reddit.scan.ignore-subreddits_: If specified, ignore given subreddits (when these-subreddits is specified) - Reddit Gold required.

>__Note:__ Setting reddit.scan.my-subreddits to false and not specifying reddit.scan.these-subreddits will result in ALTcointip bot checking its inbox only. In such case the bot will rely on the Reddit Gold "mention" feature, where users "mention" bot's username when tipping (such as +/u/mybotuser 1 ltc). Reddit "mention" feature is the most reliable way to operate ALTcointip bot.

* _misc.subtract-txfee_: If true, network transaction fee is subtracted from the amount specified (when required). Otherwise, it is added to the amount specified.

* _regex.keywords_: Regular expressions that are used to recognize commands like tipping, info, and withdrawing. Make sure that your tipping keywords are unique on Reddit, otherwise it will conflict with other tip bots.

* _kw_: Here you can define keywords that can be used in place of amount. You can specify a float value, or a string of Python code that will be executed to determine the value. The string of Python code should return a float.

* _logging_: Provide INFO-level and DEBUG-level filename to which ALTcointip bot will log its activity. On Unix/Linux, you can use _tail -f filename.log_ to monitor the log file.

* _fiat_: Fiat (such as USD) parameters are defined here. At the very least, fiat.usd is required to be present and configured.

* _cc_: Croptocoin (such as Litecoin) parameters are defined here. At least one cryptocoin needs to be configured. A few are provided for your convenience.

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
1. Execute _python _run.py_
1. Monitor configured INFO-level or DEBUG-level log file wth _tail -f filename.log_ (on Unix/Linux)
