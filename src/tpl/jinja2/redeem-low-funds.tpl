{% set coinval_fmt = "%s%.9f" % (ctb.conf.coins[a.coin].symbol, a.coinval) %}
{% set fiatval_fmt = "%s%.4f" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
I'm sorry {{ a.u_from.name | replace('_', '\_') }}, I don't have enough {{ ctb.conf.coins[a.coin].name }}s to give you for your karma (you would've gotten {{ coinval_fmt }} {{ ctb.conf.coins[a.coin].name }}s ({{ fiatval_fmt }})). Try again later, or pick a different coin.

{% include 'footer.tpl' %}
