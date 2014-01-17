{% set user_from = a.u_from.name %}
{% set user_bot = ctb.conf.reddit.auth.user %}
Welcome {{ user_from | replace('_', '\_') }}!

Thank you for registering. You can now view your balances and deposit addresses with __[+info](http://www.reddit.com/message/compose?to={{ user_bot }}&subject=info&message=%2Binfo)__ command.

For more commands and helpful information on getting started, see the footer of this message. Happy tipping!
{% include 'footer.tpl' %}
