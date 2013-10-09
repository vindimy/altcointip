{% if not user_from and a %}
{%   set user_from = a._FROM_USER._NAME %}
{% endif %}
{% if not user_bot and ctb %}
{%   set user_bot = ctb._config.reddit.user %}
{% endif %}
{% set compose_url = "http://www.reddit.com/message/compose?to=%s&subject=%s&message=%%2B%s" %}
{% set a_url = compose_url % (user_bot, "accept", "accept") %}
{% set d_url = compose_url % (user_bot, "decline", "decline") %}
{% set i_url = compose_url % (user_bot, "info", "info") %}
{% set h_url = compose_url % (user_bot, "history", "history") %}
{% set r_url = compose_url % (user_bot, "register", "register") %}
{% set w_url = compose_url % (user_bot, "withdraw", "withdraw%20ADDRESS%20AMOUNT%20COIN_NAME") %}
{% if ctb and ctb._config.reddit.help.enabled %}
{%   set help_link = " ^[[help]](%s)" % ctb._config.reddit.help.url %}
{% endif %}
{% if ctb and ctb._config.reddit.contact.enabled %}
{%   set contact_link = " ^[[contact]](%s)" % ctb._config.reddit.contact.url %}
{% endif %}
{% if ctb and ctb._config.reddit.stats.enabled %}
{%   set stats_user_link = " **^[[your_stats]](%s_%s)**" % (ctb._config.reddit.stats.url, user_from) %}
{%   set stats_global_link = " ^[[global_stats]](%s)" % ctb._config.reddit.stats.url %}
{% endif %}
*****

^Helpful ^Links|&nbsp;
:---|:---
{% if a and a._MSG and a._MSG.permalink %}
^Source ^comment|^[[link]]({{ a._MSG.permalink }})
{% elif source_link %}
^Source ^comment|^[[link]]({{ source_link }})
{% endif %}
^Quick ^commands|^[+accept]({{ a_url }}) ^[+decline]({{ d_url }}) **^[+info]({{ i_url }})** ^[+history]({{ h_url }}) ^[+register]({{ r_url }}) ^[+withdraw]({{ w_url }})
^Resources|{{ help_link }}{{ contact_link }}{{ stats_user_link }}{{ stats_global_link }}
