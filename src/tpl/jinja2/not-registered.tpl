{% set user_from = a._FROM_USER._NAME %}
{% set user_bot = ctb._config.reddit.user %}
I'm sorry {{ user_from | replace('_', '\_') }}, we've never met. Please __[+register](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=register&message=%2Bregister)__ first!

{% include 'footer.tpl' %}
