{% set user_from = a.u_from.name %}
{% set user_bot = ctb.conf.reddit.auth.user %}
I'm sorry {{ user_from | replace('_', '\_') }}, we've never met. Please __[+register](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=register&message=%2Bregister)__ first!

{% include 'footer.tpl' %}
