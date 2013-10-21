{% set user_from = a.u_from.name %}
{% set balance_fmt = "%.6g %s" % (balance, a.coin.upper()) %}
I'm sorry {{ user_from | replace('_', '\_') }}, your _{{ action_name }}_ balance of _{{ balance_fmt }}_ is insufficient for this {{ action_name }}.
{% if action_name == 'withdraw' %}
{%   set coin_name = ctb.conf.coins[a.coin].name %}
{%   set coin_confs = ctb.conf.coins[a.coin].minconf.withdraw %}
{%   set coin_fee_fmt = "%.6g" % ctb.conf.coins[a.coin].txfee %}

Withdrawals are subject to network confirmation times and network fees ({{ coin_name }} requires at least {{ coin_confs }} confirmations and a {{ coin_fee_fmt }} fee).

_Tip:_ To withdraw entire {{ coin_name }} balance, use `ALL` keyword in place of amount (such as `+withdraw ADDRESS ALL {{ coin_name }}`).
{% endif %}

{% include 'footer.tpl' %}
