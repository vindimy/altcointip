{% set user = a.u_from.name %}

Hello {{ user | replace('_', '\_') }}, here are the latest exchange rates.

coin|average{% for e in exchanges %}{{ "|" + e }}{% endfor %}

:---|---:{% for e in exchanges %}{{ "|---:" }}{% endfor %}
{% for c in coins %}
{{ "\n**%s&nbsp;(%s)**|%s%.6f^%s%.4f" % (ctb.conf.coins[c].name, c.upper(), ctb.conf.coins.btc.symbol, rates[c]['average'].btc, ctb.conf.fiat[fiat].symbol, rates[c]['average'][fiat]) }}{% for e in exchanges %}
{%     if rates[c][e].btc and rates[c][e][fiat] %}{{ "|%s%.6f^%s%.4f" % (ctb.conf.coins.btc.symbol, rates[c][e].btc, ctb.conf.fiat[fiat].symbol, rates[c][e][fiat]) }}{%     else %}{{ "|-" }}{%     endif %}
{%   endfor %}
{% endfor %}


{% include 'footer.tpl' %}
