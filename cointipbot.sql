SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE TABLE IF NOT EXISTS `t_addrs` (
  `username` varchar(30) NOT NULL,
  `coin` varchar(3) NOT NULL,
  `address` varchar(34) NOT NULL,
  PRIMARY KEY (`username`,`coin`),
  UNIQUE KEY `address` (`address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `t_mrcvd` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(30) NOT NULL,
  `action` int(11) unsigned NOT NULL DEFAULT '0',
  `amount` float unsigned NOT NULL DEFAULT '0',
  `date` date NOT NULL,
  `processed` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 AUTO_INCREMENT=1 ;

CREATE TABLE IF NOT EXISTS `t_msent` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(30) NOT NULL,
  `action` int(11) unsigned NOT NULL DEFAULT '0',
  `amount` float unsigned NOT NULL DEFAULT '0',
  `date` int(11) NOT NULL,
  `processed` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 AUTO_INCREMENT=1 ;

CREATE TABLE IF NOT EXISTS `t_users` (
  `username` varchar(30) NOT NULL,
  `joindate` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `giftamount` float DEFAULT '0',
  PRIMARY KEY (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `t_values` (
  `param0` varchar(64) NOT NULL,
  `param1` varchar(64) DEFAULT NULL,
  `value0` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`param0`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `t_values` (`param0`, `param1`, `value0`) VALUES('last_processed_comment_time', NULL, 0);

