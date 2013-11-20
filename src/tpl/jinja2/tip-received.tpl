{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% set coinval_fmt = "%s%.6g %s" % (ctb.conf.coins[a.coin].symbol, a.coinval, ctb.conf.coins[a.coin].name) %}
{% set fiatval_fmt = "%s%.4g" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Hey {{ user_to | replace('_', '\_') }}, you have received a __{{ coinval_fmt }} ({{ fiatval_fmt }})__ tip from /u/{{ user_from }}.

{% set user = user_to %}
{% include 'footer.tpl' %}
