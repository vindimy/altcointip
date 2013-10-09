{% set user_from = a._FROM_USER._NAME %}
{% if a._TO_USER %}
{%   set user_to_fmt = "/u/%s" % a._TO_USER._NAME %}
{% else %}
{%   set user_to_fmt = a._TO_ADDR %}
{% endif %}
{% set coin_amount = a._COIN_VAL %}
{% set coin_name = ctb._config.cc[a._COIN].name %}
{% set coin_amount_fmt = " __%.6g %(s)__" % (coin_amount, coin_name) %}
Hey {{ user_from | replace('_', '\_') }}, something went wrong and your tip of {{ coin_amount_fmt }} to {{ user_to_fmt }} has failed to process.

{% include 'footer.tpl' %}
