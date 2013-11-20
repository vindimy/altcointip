{% set user_from = a.u_from.name %}
{% set amount_fmt = "%s%.6g" % (ctb.conf.fiat[a.fiat].symbol, a.fiatval) %}
Sorry {{ user_from | replace('_', '\_') }}, you don't have any coin balances enough for a {{ amount_fmt }} tip.

{% include 'footer.tpl' %}
