{% set user_from = a.u_from.name %}
{% set coin_name = a.coin.upper() %}
{% set address = a.addr_to %}
I'm sorry {{ user_from | replace('_', '\_') }}, __{{ coin_name }}__ address __{{ address | escape }}__ appears to be invalid (is there a typo?).

{% include 'footer.tpl' %}
