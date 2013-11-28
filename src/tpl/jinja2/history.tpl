{% set user = a.u_from.name %}

Hello {{ user | replace('_', '\_') }}, here are your last {{ limit }} transactions.

{{ "|".join(keys) }}
{{ "|".join([":---"] * (keys|length)) }}
{% for h in history %}
{{   "|".join(h) }}
{% endfor %}

{% include 'footer.tpl' %}
