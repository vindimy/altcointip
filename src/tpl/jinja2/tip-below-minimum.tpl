{% set user_from = a.u_from.name %}
{% set amount_fmt = "%.9f %s" % (a.coinval, a.coin.upper()) %}
{% set min_fmt = "%.9g" % min_value %}
{% set coin_name = ctb.conf.coins[a.coin].name %}
I'm sorry {{ user_from | replace('_', '\_') }}, your tip/withdraw of __{{ amount_fmt }}__ is below minimum of __{{ min_fmt }}__. I cannot process very small transactions because of high network fee requirement.

If you really need to withdraw this amount, try depositing some {{ coin_name }}s to meet the minimum limit, then withdrawing everything.

{% include 'footer.tpl' %}
