{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% set coin_val_fmt = "%.6g %s(s)" % (a.coinval, ctb.conf.coins[a.coin].name) %}
{% set fiat_val_fmt = "%s%.4g" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
{% set user_bot = ctb.conf.reddit.user %}
{% set expire_days_fmt = "%.1g" % ( ctb.conf.misc.expire_pending_hours / 24.0 ) %}
Hey {{ user_to | replace('_', '\_') }}, /u/{{ user_from }} sent you a __{{ coin_val_fmt }} ({{ fiat_val_fmt }})__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=accept&message=%2Baccept)__ to claim it. Reply with __[+decline](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=decline&message=%2Bdecline)__ to decline it. __Pending tips expire in {{ expire_days_fmt }} days.__

{% include 'footer.tpl' %}
