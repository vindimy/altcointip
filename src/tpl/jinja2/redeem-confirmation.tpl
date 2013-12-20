{% if a.coinval: %}
{%   if a.coinval < 1.0 %}
{%     set coin_amount = ( a.coinval * 1000.0 ) %}
{%     set amount_prefix_short = "m" %}
{%     set amount_prefix_long = "milli" %}
{%   elif a.coinval >= 1000.0 %}
{%     set coin_amount = ( a.coinval / 1000.0 ) %}
{%     set amount_prefix_short = "M" %}
{%     set amount_prefix_long = "Mega" %}
{%   else %}
{%     set coin_amount = a.coinval %}
{%   endif %}
{% endif %}
{% set coinval_fmt = "%s%s%.6g %s%s" % (amount_prefix_short, ctb.conf.coins[a.coin].symbol, coin_amount, amount_prefix_long, ctb.conf.coins[a.coin].name) %}
{% set fiatval_fmt = "%s%.3f" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Hey {{ a.u_from.name | replace('_', '\_') }}, you have received __{{ coinval_fmt }} ({{ fiatval_fmt }})__ for your karma.

{% include 'footer.tpl' %}
