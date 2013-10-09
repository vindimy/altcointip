{% set user_from = a._FROM_USER._NAME %}
{% set amount_fmt = "%s%.2f" % (ctb._config.fiat[a._FIAT].symbol, a._FIAT_VAL) %}
Sorry {{ user_from | replace('_', '\_') }}, you don't have any coin balances enough for a {{ amount_fmt }} tip.

{% include 'footer.tpl' %}
