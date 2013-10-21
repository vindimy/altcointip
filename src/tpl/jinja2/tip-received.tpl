{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% set coin_val_fmt = "%.6g %s(s)" % (a.coinval, ctb.conf.coins[a.coin].name) %}
{% set fiat_val_fmt = "%s%.4g" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Hey {{ user_to | replace('_', '\_') }}, you have received a __{{ coin_val_fmt }} ({{ fiat_val_fmt }})__ tip from /u/{{ user_from }}.

{% include 'footer.tpl' %}
