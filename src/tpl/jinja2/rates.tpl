{% set user = a.u_from.name %}

Hello {{ user | replace('_', '\_') }}, here are the latest exchange rates.

{% set header1 = "coin|average" %}
{% set header2 = ":---|---:"
{% for e in exchanges %}
{%   set header1 = header1 + "|" + e %}
{%   set header2 = header2 + "|---:" %}
{% endfor %}

{% set body = "" %}
{% for c in coins %}
{%   set body = body + "**%s (%s)**|%s%.6g ^%s%.4g" % (ctb.conf.coins[c].name, c.upper(), ctb.conf.coins.btc.symbol, rates[c]['average'].btc, ctb.conf.fiat[fiat].symbol, rates[c]['average'][fiat] %}
{%   for e in exchanges %}
{%     set body = body + "|%s%.6g ^%s%.4g" % (ctb.conf.coins.btc.symbol, rates[c][e].btc, ctb.conf.fiat[fiat].symbol, rates[c][e][fiat] %}
{%   endfor %}
{%   set body = body + "\n" %}
{% endfor %}

{{ header1 }}
{{ header2 }}
{{ body }}

{% include 'footer.tpl' %}
