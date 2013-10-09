{% set user_from = a._FROM_USER._NAME %}
{% set user_to = a._TO_USER._NAME %}
{% set coin_name = a._COIN.upper() %}
I'm sorry {{ user_from }}, /u/{{ user_to }} already has a pending {{ coin_name }} tip from you. Please wait until it's accepted, declined, or expired.
