{% set user_from = a._FROM_USER._NAME %}
{% set user_to = a._TO_USER._NAME %}
{% set coin_val_fmt = "%.6g %s(s)" % (a._COIN_VAL, a._CTB._config.cc[a._COIN].name) %}
{% set fiat_val_fmt = "%s%.4g" % (a._CTB._config.fiat[a._FIAT].symbol, a._FIAT_VAL) %}
Hey {{ user_to }}, you have received a __{{ coin_val_fmt }} ({{ fiat_val_fmt }})__ tip from {{ user_from }}.
