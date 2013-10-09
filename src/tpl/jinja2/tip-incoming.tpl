{% set user_from = a._FROM_USER._NAME %}
{% set user_to = a._TO_USER._NAME %}
{% set coin_val_fmt = "%.6g %s(s)" % (a._COIN_VAL, ctb._config.cc[a._COIN].name) %}
{% set fiat_val_fmt = "%s%.4g" % (ctb._config.fiat[a._FIAT].symbol, a._FIAT_VAL) %}
{% set user_bot = ctb._config.reddit.user %}
{% set expire_days_fmt = "%.1g" % ( ctb._config.misc.expire_pending_hours / 24.0 ) %}
Hey {{ user_to }}, /u/{{ user_from }} sent you a __{{ coin_val_fmt }} ({{ fiat_val_fmt }})__ tip, reply with __[+accept](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=accept&message=%2Baccept)__ to claim it. Reply with __[+decline](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=decline&message=%2Bdecline)__ to decline it. __Pending tips expire in {{ expire_days_fmt }} days.__

{% include 'footer.tpl' %}
