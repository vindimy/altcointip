{% set user_from = a.u_from.name %}
{% if a.u_to %}
{%   set user_to_fmt = "/u/%s" % a.u_to.name %}
{% else %}
{%   set user_to_fmt = a.addr_to %}
{% endif %}
{% set coin_amount = a.coinval %}
{% set coin_name = ctb.conf.coins[a.coin].name %}
{% set coin_amount_fmt = " __%.6g %(s)__" % (coin_amount, coin_name) %}
Hey {{ user_from | replace('_', '\_') }}, something went wrong and your tip of {{ coin_amount_fmt }} to {{ user_to_fmt }} has failed to process.

{% include 'footer.tpl' %}
