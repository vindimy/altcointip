{% set coinval_fmt = "%s%.6g" % (ctb.conf.coins[a.coin].symbol, a.coinval) %}
{% set fiatval_fmt = "%s%.2f" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Hey {{ a.u_from.name | replace('_', '\_') }}, you have received __{{ coinval_fmt }} {{ ctb.conf.coins[a.coin].name }}s ({{ fiatval_fmt }})__ for your karma.

{% include 'footer.tpl' %}
