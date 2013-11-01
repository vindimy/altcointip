{% set coinval_fmt = "%.6g" % a.coinval %}
{% set usdval_fmt = "%.2f" % usd_val %}
Hey {{ a.u_from.name | replace('_', '\_') }}, you have received __{{ coinval_fmt }} {{ ctb.conf.coins[a.coin].name }}s (${{ usdval_fmt }})__ for your karma.

{% include 'footer.tpl' %}
