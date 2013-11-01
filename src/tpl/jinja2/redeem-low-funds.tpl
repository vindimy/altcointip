{% set coinval_fmt = "%.6f" % a.coinval %}
I'm sorry {{ a.u_from.name | replace('_', '\_') }}, I don't have enough {{ ctb.conf.coins[a.coin].name }}s to give you for your karma (you would've gotten {{ coinval_fmt }} {{ ctb.conf.coins[a.coin].name }}s). Try again later, or pick a different coin.

{% include 'footer.tpl' %}
