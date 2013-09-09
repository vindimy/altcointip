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

import logging

lg = logging.getLogger('cointipbot')

def update_stats(ctb=None):
    """
    Refresh stats wiki page
    """
    mysqlcon = ctb._mysqlcon
    redditcon = ctb._redditcon

    stats = ""

    if not ctb._config['reddit']['stats']['enabled']:
        return None

    for s in ctb._config['reddit']['stats']['sql']:
        sql = ctb._config['reddit']['stats']['sql'][s]
        stats += "\n\n### %s\m\m" % s

        mysqlexec = mysqlcon.execute(sql)
        if mysqlexec.rowcount <= 0:
            continue;

        stats += ("|".join(mysqlexec.keys())) + "\n"
        stats += ("|".join([":---"] * len(mysqlexec.keys()))) + "\n"

        for m in mysqlexec:
            values = []
            for k in mysqlexec.keys():
                values.append(m[k])
            stats += ("|".join(values)) + "\n"

        stats += "\n"

    return stats
