I'm sorry {{ a.u_from.name | replace('_', '\_') }}, you've already redeemed your {{ coin }} karma.

{% if coin %}
Try redeeming a different coin.
{% endif %}

{% include 'footer.tpl' %}
