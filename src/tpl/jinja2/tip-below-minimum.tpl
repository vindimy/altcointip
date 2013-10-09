{% set user_from = a._FROM_USER._NAME %}
{% set amount_fmt = "%.6g %s" % (a._COIN_VAL, a._COIN.upper()) %}
{% set min_fmt = "%.6g" % min_value %}
I'm sorry {{ user_from | replace('_', '\_') }}, your tip/withdraw of __{{ amount_fmt }}__ is below minimum of __{{ min_fmt }}__.

{% include 'footer.tpl' %}
