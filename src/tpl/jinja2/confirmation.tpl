{% set title_fmt = "^__[%s]__:" % title %}
{% set user_from_fmt = " ^/u/%s" % a.u_from.name %}
{% set arrow_fmt = " ^->" %}
{% if a.u_to: %}
{%   set user_to_fmt = " ^/u/%s" % a.u_to.name %}
{%   if ctb.conf.reddit.stats.enabled: %}
{%     set stats_user_to_fmt = " ^^[[stats]](%s_%s)" % (ctb.conf.reddit.stats.url, a.u_to.name) %}
{%   endif %}
{% endif %}
{% if a.addr_to: %}
{%   set ex = ctb.conf.coins[a.coin].explorer %}
{%   set user_to_fmt = " ^[%s](%s%s)" % (a.addr_to, ex.address, a.addr_to) %}
{%   set arrow_fmt = " ^[->](%s%s)" % (ex.transaction, a.txid) %}
{% endif %}
{% if a.coinval: %}
{%   set coin_amount = a.coinval %}
{%   set coin_name = ctb.conf.coins[a.coin].name %}
{%   set coin_symbol = ctb.conf.coins[a.coin].symbol %}
{%   set coin_amount_fmt = " __^%s%.7g ^%s(s)__" % (coin_symbol, coin_amount, coin_name) %}
{% endif %}
{% if a.fiatval: %}
{%   set fiat_amount = a.fiatval %}
{%   set fiat_symbol = ctb.conf.fiat[a.fiat].symbol %}
{%   set fiat_amount_fmt = "&nbsp;^__(%s%.6g)__" % (fiat_symbol, fiat_amount) %}
{% endif %}
{% if ctb.conf.reddit.stats.enabled: %}
{%   set stats_user_from_fmt = " ^^[[stats]](%s_%s)" % (ctb.conf.reddit.stats.url, a.u_from.name) %}
{%   set stats_link_fmt = " ^[[stats]](%s)" % ctb.conf.reddit.stats.url %}
{% endif %}
{% if ctb.conf.reddit.help.enabled: %}
{%   set help_link_fmt = " ^[[help]](%s)" % ctb.conf.reddit.help.url %}
{% endif %}
{% include "coins/"+a.coin+"/confirmation.tpl" ignore missing %}
{{ title_fmt }}{{ user_from_fmt }}{{ stats_user_from_fmt }}{{ arrow_fmt }}{{ user_to_fmt }}{{ stats_user_to_fmt }}{{ coin_amount_fmt }}{{ fiat_amount_fmt }}{{ help_link_fmt }}{{ stats_link_fmt }}
