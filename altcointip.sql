SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE TABLE IF NOT EXISTS `t_action` (
  `type` enum('givetip','withdraw','info','register','accept','decline','history','redeem','rates') NOT NULL,
  `state` enum('completed','pending','failed','declined','expired') NOT NULL,
  `created_utc` int(11) unsigned NOT NULL,
  `from_user` varchar(30) NOT NULL,
  `to_user` varchar(30) DEFAULT NULL,
  `to_addr` varchar(34) DEFAULT NULL,
  `coin_val` float unsigned DEFAULT NULL,
  `fiat_val` float unsigned DEFAULT NULL,
  `txid` varchar(64) DEFAULT NULL,
  `coin` varchar(3) DEFAULT NULL,
  `fiat` varchar(3) DEFAULT NULL,
  `subreddit` varchar(30) DEFAULT NULL,
  `msg_id` varchar(10) NOT NULL,
  `msg_link` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`type`,`created_utc`,`msg_id`),
  UNIQUE KEY `msg_id` (`msg_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `t_addrs` (
  `username` varchar(30) NOT NULL,
  `coin` varchar(3) NOT NULL,
  `address` varchar(34) NOT NULL,
  PRIMARY KEY (`username`,`coin`),
  UNIQUE KEY `address` (`address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `t_users` (
  `username` varchar(30) NOT NULL,
  `joindate` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `giftamount` float DEFAULT '0',
  PRIMARY KEY (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `t_values` (
  `param0` varchar(64) NOT NULL,
  `value0` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`param0`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
