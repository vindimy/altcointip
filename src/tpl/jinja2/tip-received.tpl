{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% if a.coinval: %}
{%   if a.coinval < 0.0001 %}
{%     set coin_amount = ( a.coinval * 100000000.0 ) %}
{%     set amount_prefix_short = "s" %}
{%     set amount_prefix_long = "satoshi" %}
{%   elif a.coinval < 1.0 %}
{%     set coin_amount = ( a.coinval * 1000.0 ) %}
{%     set amount_prefix_short = "m" %}
{%     set amount_prefix_long = "milli" %}
{%   elif a.coinval >= 1000.0 %}
{%     set coin_amount = ( a.coinval / 1000.0 ) %}
{%     set amount_prefix_short = "K" %}
{%     set amount_prefix_long = "kilo" %}
{%   else %}
{%     set coin_amount = a.coinval %}
{%   endif %}
{% endif %}
{% set coinval_fmt = "%s%s%.6g %s%ss" % (amount_prefix_short, ctb.conf.coins[a.coin].symbol, coin_amount, amount_prefix_long, ctb.conf.coins[a.coin].name) %}
{% if amount_prefix_short %}
{%   set coinval_fmt = coinval_fmt + " (%s%.9f %ss)" % (ctb.conf.coins[a.coin].symbol, a.coinval, ctb.conf.coins[a.coin].name) %}
{% endif %}
{% set fiatval_fmt = "%s%.4f" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Hey {{ user_to | replace('_', '\_') }}, you have received a __{{ coinval_fmt }} ({{ fiatval_fmt }})__ tip from /u/{{ user_from }}.

{% set user = user_to %}
{% include 'footer.tpl' %}
