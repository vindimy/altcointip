{% set user = a._FROM_USER._NAME %}
{% set amount_fmt = "%s%.2f" % (a._CTB._config.fiat[a._FIAT].symbol, a._FIAT_VAL) %}
Sorry {{ user }}, you don't have any coin balances enough for a __{{ amount_fmt }}__ tip.
