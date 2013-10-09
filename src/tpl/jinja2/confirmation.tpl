{% set title_fmt = "^__[%s]__:" % title %}
{% set user_from_fmt = " ^/u/%s" % a._FROM_USER._NAME %}
{% set arrow_fmt = " ^->" %}
{% if a._TO_USER: %}
{%   set user_to_fmt = " ^/u/%s" % a._TO_USER._NAME %}
{%   if ctb._config.reddit.stats.enabled: %}
{%     set stats_user_to_fmt = " ^^[[stats]](%s_%s)" % (ctb._config.reddit.stats.url, a._TO_USER._NAME) %}
{%   endif %}
{% endif %}
{% if a._TO_ADDR: %}
{%   set ex = ctb._config.cc[a._COIN].explorer.address %}
{%   set user_to_fmt = " ^[%s](%s%s)" % (a._TO_ADDR, ex.address, a._TO_ADDR) %}
{%   set arrow_fmt = " ^[->](%s%s)" % (ex.transaction, a._TXID) %}
{% endif %}
{% if a._COIN_VAL: %}
{%   set coin_amount = a._COIN_VAL %}
{%   set coin_name = ctb._config.cc[a._COIN].name %}
{%   set coin_amount_fmt = " __^%.6g ^%s(s)__" % (coin_amount, coin_name) %}
{% endif %}
{% if a._FIAT_VAL: %}
{%   set fiat_amount = a._FIAT_VAL %}
{%   set fiat_symbol = ctb._config.fiat[a._FIAT].symbol %}
{%   set fiat_amount_fmt = "&nbsp;^__(%s%.2f)__" % (fiat_symbol, fiat_amount) %}
{% endif %}
{% if ctb._config.reddit.stats.enabled: %}
{%   set stats_user_from_fmt = " ^^[[stats]](%s_%s)" % (ctb._config.reddit.stats.url, a._FROM_USER._NAME) %}
{%   set stats_link_fmt = " ^[[stats]](%s)" % ctb._config.reddit.stats.url %}
{% endif %}
{% if ctb._config.reddit.help.enabled: %}
{%   set help_link_fmt = " ^[[help]](%s)" % ctb._config.reddit.help.url %}
{% endif %}
{{ title_fmt }}{{ user_from_fmt }}{{ stats_user_from_fmt }}{{ arrow_fmt }}{{ user_to_fmt }}{{ stats_user_to_fmt }}{{ coin_amount_fmt }}{{ fiat_amount_fmt }}{{ help_link_fmt }}{{ stats_link_fmt }}
