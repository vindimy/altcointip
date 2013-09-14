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
    Update stats wiki page
    """
    mysqlcon = ctb._mysqlcon
    redditcon = ctb._redditcon

    stats = ""

    if not ctb._config['reddit']['stats']['enabled']:
        return None

    for s in sorted(ctb._config['reddit']['stats']['sql']):
        lg.debug("update_stats(): getting stats for '%s'" % s)
        sql = ctb._config['reddit']['stats']['sql'][s]['query']
        stats += "\n\n### %s\n\n" % ctb._config['reddit']['stats']['sql'][s]['name']
        stats += "%s\n\n" % ctb._config['reddit']['stats']['sql'][s]['desc']

        mysqlexec = mysqlcon.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.warning("update_stats(): query <%s> returned nothing" % ctb._config['reddit']['stats']['sql'][s]['query'])
            continue

        if ctb._config['reddit']['stats']['sql'][s]['type'] == "line":
            m = mysqlexec.fetchone()
            k = mysqlexec.keys()[0]
            if k.find("usd") > -1:
                stats += "%s = **$%.2f**\n" % (k, m[k])
            else:
                stats += "%s = **%s**\n" % (k, m[k])
        elif ctb._config['reddit']['stats']['sql'][s]['type'] == "table":
            stats += ("|".join(mysqlexec.keys())) + "\n"
            stats += ("|".join([":---"] * len(mysqlexec.keys()))) + "\n"
            for m in mysqlexec:
                values = []
                for k in mysqlexec.keys():
                    if type(m[k]) == float and k.find("coin") > -1:
                        values.append("%.8g" % m[k])
                    elif type(m[k]) == float and k.find("fiat") > -1:
                        values.append("$%.2f" % m[k])
                    elif k.find("user") > -1:
                        values.append("/u/" + str(m[k]))
                    elif k.find("subreddit") > -1:
                        values.append("/r/" + str(m[k]))
                    elif k.find("link") > -1:
                        values.append("[link](%s)" % m[k])
                    else:
                        values.append(str(m[k]))
                stats += ("|".join(values)) + "\n"
        else:
            lg.error("update_stats(): don't know what to do with type '%s'" % ctb._config['reddit']['stats']['sql'][s]['type'])
            return False

        stats += "\n"

    lg.debug("update_stats(): updating subreddit '%s', page '%s'" % (ctb._config['reddit']['stats']['subreddit'], ctb._config['reddit']['stats']['page']))
    return redditcon.edit_wiki_page(ctb._config['reddit']['stats']['subreddit'], ctb._config['reddit']['stats']['page'], stats, "Update by ALTcointip bot")
