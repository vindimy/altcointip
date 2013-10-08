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

import cointipbot, logging
from ctb import ctb_stats

lg = logging.getLogger('cointipbot')
cb = cointipbot.CointipBot(self_checks=False, init_reddit=True, init_coins=False, init_db=True, init_logging=False)

result = ctb_stats.update_stats(ctb=cb)
lg.debug(result)

user_result = ctb_stats.update_user_stats(ctb=cb)
lg.debug(user_result)
