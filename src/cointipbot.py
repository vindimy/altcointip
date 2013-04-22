#!/usr/bin/env python

import ctbutil
import yaml

logger = logging.getLogger('cointipbot')

class CointipBot(object):
	"""
	Main class for cointip bot
	"""

	_DEFAULT_CONFIG_FILENAME = './config.yaml'

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
			print >> sys.stderr, "Error reading config file %s" % filename
			if hasattr(e, 'problem_mark'):
				print >> sys.stderr, "Error position: (line %s, column %s)" % (e.problem_mark.line+1, e.problem_mark.column+1)
		return config


	def __init__(self, config_filename=_DEFAULT_CONFIG_FILENAME):
		"""
		Constructor.
		Parses configuration file and initializes bot.
		"""
		config = self._parse_config(config_filename)
