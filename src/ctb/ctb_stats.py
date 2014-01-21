#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import logging, re, time
import ctb_misc

lg = logging.getLogger('cointipbot')

def update_stats(ctb=None):
    """
    Update stats wiki page
    """

    stats = ""

    if not ctb.conf.reddit.stats.enabled:
        return None

    for s in sorted(vars(ctb.conf.db.sql.globalstats)):
        lg.debug("update_stats(): getting stats for '%s'" % s)
        sql = ctb.conf.db.sql.globalstats[s].query
        stats += "\n\n### %s\n\n" % ctb.conf.db.sql.globalstats[s].name
        stats += "%s\n\n" % ctb.conf.db.sql.globalstats[s].desc

        mysqlexec = ctb.db.execute(sql)
        if mysqlexec.rowcount <= 0:
            lg.warning("update_stats(): query <%s> returned nothing" % ctb.conf.db.sql.globalstats[s].query)
            continue

        if ctb.conf.db.sql.globalstats[s].type == "line":
            m = mysqlexec.fetchone()
            k = mysqlexec.keys()[0]
            value = format_value(m, k, '', ctb)
            stats += "%s = **%s**\n" % (k, value)

        elif ctb.conf.db.sql.globalstats[s].type == "table":
            stats += ("|".join(mysqlexec.keys())) + "\n"
            stats += ("|".join([":---"] * len(mysqlexec.keys()))) + "\n"
            for m in mysqlexec:
                values = []
                for k in mysqlexec.keys():
                    values.append(format_value(m, k, '', ctb))
                stats += ("|".join(values)) + "\n"

        else:
            lg.error("update_stats(): don't know what to do with type '%s'" % ctb.conf.db.sql.globalstats[s].type)
            return False

        stats += "\n"

    lg.debug("update_stats(): updating subreddit '%s', page '%s'" % (ctb.conf.reddit.stats.subreddit, ctb.conf.reddit.stats.page))
    return ctb_misc.praw_call(ctb.reddit.edit_wiki_page, ctb.conf.reddit.stats.subreddit, ctb.conf.reddit.stats.page, stats, "Update by ALTcointip bot")

def update_tips(ctb=None):
    """
    Update page listing all tips
    """

    if not ctb.conf.reddit.stats.enabled:
        return None

    # Start building stats page
    tip_list = "### All Completed Tips\n\n"

    q = ctb.db.execute(ctb.conf.db.sql.tips.sql_set)
    tips = ctb.db.execute(ctb.conf.db.sql.tips.sql_list, (ctb.conf.db.sql.tips.limit))
    tip_list += ("|".join(tips.keys())) + "\n"
    tip_list += ("|".join([":---"] * len(tips.keys()))) + "\n"

    # Build tips table
    for t in tips:
        values = []
        for k in tips.keys():
            values.append(format_value(t, k, '', ctb, compact=True))
        tip_list += ("|".join(values)) + "\n"

    lg.debug("update_tips(): updating subreddit '%s', page '%s'" % (ctb.conf.reddit.stats.subreddit, ctb.conf.reddit.stats.page_tips))
    ctb_misc.praw_call(ctb.reddit.edit_wiki_page, ctb.conf.reddit.stats.subreddit, ctb.conf.reddit.stats.page_tips, tip_list, "Update by ALTcointip bot")

    return True

def update_all_user_stats(ctb=None):
    """
    Update individual user stats for all uers
    """

    if not ctb.conf.reddit.stats.enabled:
        lg.error('update_all_user_stats(): stats are not enabled in config.yml')
        return None

    users = ctb.db.execute(ctb.conf.db.sql.userstats.users)
    for u in users:
        update_user_stats(ctb=ctb, username=u['username'])

def update_user_stats(ctb=None, username=None):
    """
    Update individual user stats for given username
    """

    if not ctb.conf.reddit.stats.enabled:
        return None

    # List of coins
    coins_q = ctb.db.execute(ctb.conf.db.sql.userstats.coins)
    coins = []
    for c in coins_q:
        coins.append(c['coin'])

    # List of fiat
    fiat_q = ctb.db.execute(ctb.conf.db.sql.userstats.fiat)
    fiat = []
    for f in fiat_q:
        fiat.append(f['fiat'])

    # Start building stats page
    user_stats = "### Tipping Summary for /u/%s\n\n" % username
    page = ctb.conf.reddit.stats.page + '_' + username

    # Total Tipped
    user_stats += "#### Total Tipped (Fiat)\n\n"
    user_stats += "fiat|total\n:---|---:\n"
    total_tipped = []
    for f in fiat:
        mysqlexec = ctb.db.execute(ctb.conf.db.sql.userstats.total_tipped_fiat, (username, f))
        total_tipped_fiat = mysqlexec.fetchone()
        if total_tipped_fiat['total_fiat'] != None:
            user_stats += "**%s**|%s %.2f\n" % (f, ctb.conf.fiat[f].symbol, total_tipped_fiat['total_fiat'])
            total_tipped.append("%s%.2f" % (ctb.conf.fiat[f].symbol, total_tipped_fiat['total_fiat']))
    user_stats += "\n"

    user_stats += "#### Total Tipped (Coins)\n\n"
    user_stats += "coin|total\n:---|---:\n"
    for c in coins:
        mysqlexec = ctb.db.execute(ctb.conf.db.sql.userstats.total_tipped_coin, (username, c))
        total_tipped_coin = mysqlexec.fetchone()
        if total_tipped_coin['total_coin'] != None:
            user_stats += "**%s**|%s %.6f\n" % (c, ctb.conf.coins[c].symbol, total_tipped_coin['total_coin'])
    user_stats += "\n"

    # Total received
    user_stats += "#### Total Received (Fiat)\n\n"
    user_stats += "fiat|total\n:---|---:\n"
    total_received = []
    for f in fiat:
        mysqlexec = ctb.db.execute(ctb.conf.db.sql.userstats.total_received_fiat, (username, f))
        total_received_fiat = mysqlexec.fetchone()
        if total_received_fiat['total_fiat'] != None:
            user_stats += "**%s**|%s %.2f\n" % (f, ctb.conf.fiat[f].symbol, total_received_fiat['total_fiat'])
            total_received.append("%s%.2f" % (ctb.conf.fiat[f].symbol, total_received_fiat['total_fiat']))
    user_stats += "\n"

    user_stats += "#### Total Received (Coins)\n\n"
    user_stats += "coin|total\n:---|---:\n"
    for c in coins:
        mysqlexec = ctb.db.execute(ctb.conf.db.sql.userstats.total_received_coin, (username, c))
        total_received_coin = mysqlexec.fetchone()
        if total_received_coin['total_coin'] != None:
            user_stats += "**%s**|%s %.6f\n" % (c, ctb.conf.coins[c].symbol, total_received_coin['total_coin'])
    user_stats += "\n"

    # History
    user_stats += "#### History\n\n"
    history = ctb.db.execute(ctb.conf.db.sql.userstats.history, (username, username))
    user_stats += ("|".join(history.keys())) + "\n"
    user_stats += ("|".join([":---"] * len(history.keys()))) + "\n"

    # Build history table
    num_tipped = 0
    num_received = 0
    for m in history:
        if m['state'] == 'completed':
            if m['from_user'].lower() == username.lower():
                num_tipped += 1
            elif m['to_user'].lower() == username.lower():
                num_received += 1
        values = []
        for k in history.keys():
            values.append(format_value(m, k, username, ctb))
        user_stats += ("|".join(values)) + "\n"

    # Submit changes
    lg.debug("update_user_stats(): updating subreddit '%s', page '%s'" % (ctb.conf.reddit.stats.subreddit, page))
    ctb_misc.praw_call(ctb.reddit.edit_wiki_page, ctb.conf.reddit.stats.subreddit, page, user_stats, "Update by ALTcointip bot")

    # Update user flair on subreddit
    if ctb.conf.reddit.stats.userflair and ( len(total_tipped) > 0 or len(total_received) > 0 ):
        flair = ""
        if len(total_tipped) > 0:
            flair += "tipped[" + '|'.join(total_tipped) + "]"
            flair += " (%d)" % num_tipped
        if len(total_received) > 0:
            if len(total_tipped) > 0:
                flair += " / "
            flair += "received[" + '|'.join(total_received) + "]"
            flair += " (%d)" % num_received
        lg.debug("update_user_stats(): updating flair for %s (%s)", username, flair)
        r = ctb_misc.praw_call(ctb.reddit.get_subreddit, ctb.conf.reddit.stats.subreddit)
        res = ctb_misc.praw_call(r.set_flair, username, flair, '')
        lg.debug(res)

    return True

def format_value(m, k, username, ctb, compact=False):
    """
    Format value for display based on its type
    m[k] is the value, k is the database row name
    """

    if not m[k]:
        return '-'

    # Format cryptocoin
    if type(m[k]) == float and k.find("coin") > -1:
        coin_symbol = ctb.conf.coins[m['coin']].symbol
        return "%s&nbsp;%.5g" % (coin_symbol, m[k])

    # Format fiat
    elif type(m[k]) == float and ( k.find("fiat") > -1 or k.find("usd") > -1 ):
        fiat_symbol = ctb.conf.fiat[m['fiat']].symbol
        return "%s&nbsp;%.2f" % (fiat_symbol, m[k])

    # Format username
    elif k.find("user") > -1 and type( m[k] ) in [str, unicode]:
        if compact:
            return ("**/u/%s**" % m[k]) if m[k].lower() == username.lower() else ("/u/%s" % m[k])
        else:
            un = ("**%s**" % m[k]) if m[k].lower() == username.lower() else m[k]
            toreturn = "[%s](/u/%s)" % (un, re.escape(m[k]))
            if m[k].lower() != username.lower():
                toreturn += "^[[stats]](/r/%s/wiki/%s_%s)" % (ctb.conf.reddit.stats.subreddit, ctb.conf.reddit.stats.page, m[k])
            return toreturn

    # Format address
    elif k.find("addr") > -1:
        displayaddr = m[k][:6] + "..." + m[k][-5:]
        return "[%s](%s%s)" % (displayaddr, ctb.conf.coins[m['coin']].explorer.address, m[k])

    # Format state
    elif k.find("state") > -1:
        if m[k] == 'completed':
            return unicode('✓', 'utf8')
        else:
            return m[k]

    # Format type
    elif k.find("type") > -1:
        if m[k] == 'givetip':
            return 'tip'
        if compact:
            if m[k] == 'withdraw':
                return 'w'
            if m[k] == 'redeem':
                return 'r'

    # Format subreddit
    elif k.find("subreddit") > -1:
        return "/r/%s" % m[k]

    # Format link
    elif k.find("link") > -1:
        return "[link](%s)" % m[k]

    # Format time
    elif k.find("utc") > -1:
        return "%s" % time.strftime('%Y-%m-%d', time.localtime(m[k]))

    # It's something else
    else:
        return str(m[k])
