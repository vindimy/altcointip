{% if ctb and ctb._config.reddit.help.enabled %}
{%   set help_link = "[verify syntax](%s)" % ctb._config.reddit.help.url %}
{% else %}
{%   set help_link = "verify syntax" %}
{% endif %}
Sorry {{ user_from }}, I didn't understand your {{ what }}. Please {{ help_link }} and try again.

{% include 'footer.tpl' %}
