I'm sorry {{ a.u_from.name | replace('_', '\_') }}, you total karma needs to be greater or equal to {{ ctb.conf.reddit.redeem.min_karma }} for this feature (you have {{ user_karma }}).

{% include 'footer.tpl' %}
