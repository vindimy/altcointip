{% if ctb and ctb.conf.reddit.help.enabled %}
{%   set help_link = "[verify syntax](%s)" % ctb.conf.reddit.help.url %}
{% else %}
{%   set help_link = "verify syntax" %}
{% endif %}
Sorry {{ user_from | replace('_', '\_') }}, I didn't understand your {{ what }}. Please {{ help_link }} and try again.

{% set user = user_from %}
{% include 'footer.tpl' %}
