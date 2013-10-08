{% set user_from = a._FROM_USER._NAME %}
{% set user_to = a._TO_USER._NAME %}
{% set coin_amount = a._COIN_VAL %}
{% set coin_name = a._CTB._config.cc[a._COIN].name %}
{% set coin_amount_fmt = " __%.6g %(s)__" % (coin_amount, coin_name) %}
Hey {{ user_from }}, something went wrong, and your tip of {{ coin_amount_fmt }} to __/u/{{ user_to }}__ has failed to process.
