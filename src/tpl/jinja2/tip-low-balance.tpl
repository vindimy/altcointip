{% set user_from = a.u_from.name %}
{% set balance_fmt = "%.9f %s" % (balance, a.coin.upper()) %}
I'm sorry {{ user_from | replace('_', '\_') }}, your {{ action_name }} balance of **{{ balance_fmt }}** is insufficient for this {{ action_name }}.
{% if action_name == 'withdraw' %}
{%   set coin_name = ctb.conf.coins[a.coin].name %}
{%   set coin_confs = ctb.conf.coins[a.coin].minconf.withdraw %}
{%   set coin_fee_fmt = "%.6g" % ctb.conf.coins[a.coin].txfee %}

Withdrawals are subject to network confirmations and network fees. {{ coin_name }} requires {{ coin_confs }} confirmations and a {{ coin_fee_fmt }} fee.

If withdrawal balance above doesn't match your reported tip balance, try waiting for more network confirmations.

>**Tip:** To withdraw everything, use the `ALL` keyword - `+withdraw ADDRESS ALL {{ coin_name }}` - and I'll automatically deduct the required network fee.
{% endif %}

{% include 'footer.tpl' %}
