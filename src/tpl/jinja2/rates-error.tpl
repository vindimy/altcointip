{% set user = a.u_from.name %}
Hey {{ user | replace('_', '\_') }}, I couldn't get the rates for you because exchange **{{ exchange }}** didn't respond. Please try again later.

{% include 'footer.tpl' %}
