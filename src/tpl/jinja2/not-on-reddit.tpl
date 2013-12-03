{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
I'm sorry {{ user_from | replace('_', '\_') }}, your tip has failed because user **{{ user_to | replace('_', '\_') }}** is not on Reddit.

{% include 'footer.tpl' %}
