{% set user_from = a._FROM_USER._NAME %}
{% set coin_name = a._COIN.upper() %}
{% set address = a._TO_ADDR %}
I'm sorry {{ user_from | replace('_', '\_') }}, __{{ coin_name }}__ address __{{ address | escape }}__ appears to be invalid (is there a typo?).

{% include 'footer.tpl' %}
