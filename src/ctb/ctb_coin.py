"""
    This file is part of ALTcointip.

    ALTcointip is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ALTcointip is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with ALTcointip.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging, re, time
from pifkoin.bitcoind import Bitcoind, BitcoindException
from httplib import CannotSendRequest

lg = logging.getLogger('cointipbot')

class CtbCoin(object):
    """
    Coin class for cointip bot
    """

    conn = None
    conf = None

    def __init__(self, _conf = None):
        """
        Initialize CtbCoin with given parameters. _conf is a coin config dictionary defined in conf/coins.yml
        """

        # verify _conf is a config dictionary
        if not _conf or not hasattr(_conf, 'name') or not hasattr(_conf, 'config_file') or not hasattr(_conf, 'txfee'):
            raise Exception("CtbCoin::__init__(): _conf is empty or invalid")

        self.conf = _conf

        # connect to coin daemon
        try:
            lg.debug("CtbCoin::__init__(): connecting to %s...", self.conf.name)
            self.conn = Bitcoind(self.conf.config_file, rpcserver=self.conf.config_rpcserver)
        except BitcoindException as e:
            lg.error("CtbCoin::__init__(): error connecting to %s using %s: %s", self.conf.name, self.conf.config_file, e)
            raise

        lg.info("CtbCoin::__init__():: connected to %s", self.conf.name)
        time.sleep(0.5)

        # set transaction fee
        lg.info("Setting tx fee of %f", self.conf.txfee)
        self.conn.settxfee(self.conf.txfee)

    def getbalance(self, _user = None, _minconf = None):
        """
        Get user's tip or withdraw balance. _minconf is number of confirmations to use.
        Returns (float) balance
        """
        lg.debug("CtbCoin::getbalance(%s, %s)", _user, _minconf)

        user = self.verify_user(_user=_user)
        minconf = self.verify_minconf(_minconf=_minconf)
        balance = float(0)

        try:
            balance = self.conn.getbalance(user, minconf)
        except BitcoindException as e:
            lg.error("CtbCoin.getbalance(): error getting %s (minconf=%s) balance for %s: %s", self.conf.name, minconf, user, e)
            raise

        time.sleep(0.5)
        return float(balance)

    def sendtouser(self, _userfrom = None, _userto = None, _amount = None, _minconf = 1):
        """
        Transfer (move) coins to user
        Returns (bool)
        """
        lg.debug("CtbCoin::sendtouser(%s, %s, %.9f)", _userfrom, _userto, _amount)

        userfrom = self.verify_user(_user=_userfrom)
        userto = self.verify_user(_user=_userto)
        amount = self.verify_amount(_amount=_amount)

        # send request to coin daemon
        try:
            lg.info("CtbCoin::sendtouser(): moving %.9f %s from %s to %s", amount, self.conf.name, userfrom, userto)
            result = self.conn.move(userfrom, userto, amount)
            time.sleep(0.5)
        except Exception as e:
            lg.error("CtbCoin::sendtouser(): error moving %.9f %s from %s to %s: %s", amount, self.conf.name, userfrom, userto, e)
            return False

        time.sleep(0.5)
        return True

    def sendtoaddr(self, _userfrom = None, _addrto = None, _amount = None):
        """
        Send coins to address
        Returns (string) txid
        """
        lg.debug("CtbCoin::sendtoaddr(%s, %s, %.9f)", _userfrom, _addrto, _amount)

        userfrom = self.verify_user(_user=_userfrom)
        addrto = self.verify_addr(_addr=_addrto)
        amount = self.verify_amount(_amount=_amount)
        minconf = self.verify_minconf(_minconf=self.conf.minconf.withdraw)
        txid = ""

        # send request to coin daemon
        try:
            lg.info("CtbCoin::sendtoaddr(): sending %.9f %s from %s to %s", amount, self.conf.name, userfrom, addrto)

            # Unlock wallet, if applicable
            if hasattr(self.conf, 'walletpassphrase'):
                lg.debug("CtbCoin::sendtoaddr(): unlocking wallet...")
                self.conn.walletpassphrase(self.conf.walletpassphrase, 1)

            # Perform transaction
            lg.debug("CtbCoin::sendtoaddr(): calling sendfrom()...")
            txid = self.conn.sendfrom(userfrom, addrto, amount, minconf)

            # Lock wallet, if applicable
            if hasattr(self.conf, 'walletpassphrase'):
                lg.debug("CtbCoin::sendtoaddr(): locking wallet...")
                self.conn.walletlock()

        except Exception as e:
            lg.error("CtbCoin::sendtoaddr(): error sending %.9f %s from %s to %s: %s", amount, self.conf.name, userfrom, addrto, e)
            raise

        time.sleep(0.5)
        return str(txid)

    def validateaddr(self, _addr = None):
        """
        Verify that _addr is a valid coin address
        Returns (bool)
        """
        lg.debug("CtbCoin::validateaddr(%s)", _addr)

        addr = self.verify_addr(_addr=_addr)
        addr_valid = self.conn.validateaddress(addr)
        time.sleep(0.5)

        if not addr_valid.has_key('isvalid') or not addr_valid['isvalid']:
            lg.debug("CtbCoin::validateaddr(%s): not valid", addr)
            return False
        else:
            lg.debug("CtbCoin::validateaddr(%s): valid", addr)
            return True

    def getnewaddr(self, _user = None):
        """
        Generate a new address for _user
        Returns (string) address
        """

        user = self.verify_user(_user=_user)
        addr = ""
        counter = 0

        while True:
            try:
                # Unlock wallet for keypoolrefill
                if hasattr(self.conf, 'walletpassphrase'):
                    self.conn.walletpassphrase(self.conf.walletpassphrase, 1)

                # Generate new address
                addr = self.conn.getnewaddress(user)

                # Lock wallet
                if hasattr(self.conf, 'walletpassphrase'):
                    self.conn.walletlock()

                if not addr:
                    raise Exception("CtbCoin::getnewaddr(%s): empty addr", user)

                time.sleep(0.1)
                return str(addr)

            except BitcoindException as e:
                lg.error("CtbCoin::getnewaddr(%s): BitcoindException: %s", user, e)
                raise
            except CannotSendRequest as e:
                if counter < 3:
                    lg.warning("CtbCoin::getnewaddr(%s): CannotSendRequest, retrying")
                    counter += 1
                    time.sleep(10)
                    continue
                else:
                    raise
            except Exception as e:
                if str(e) == "timed out" and counter < 3:
                    lg.warning("CtbCoin::getnewaddr(%s): timed out, retrying")
                    counter += 1
                    time.sleep(10)
                    continue
                else:
                    lg.error("CtbCoin::getnewaddr(%s): Exception: %s", user, e)
                    raise


    def verify_user(self, _user = None):
        """
        Verify and return a username
        """

        if not _user or not type(_user) in [str, unicode]:
            raise Exception("CtbCoin::verify_user(): _user wrong type (%s) or empty (%s)", type(_user), _user)

        return str(_user.lower())

    def verify_addr(self, _addr = None):
        """
        Verify and return coin address
        """

        if not _addr or not type(_addr) in [str, unicode]:
            raise Exception("CtbCoin::verify_addr(): _addr wrong type (%s) or empty (%s)", type(_addr),_addr)

        return re.escape(str(_addr))

    def verify_amount(self, _amount = None):
        """
        Verify and return amount
        """

        if not _amount or not type(_amount) in [int, float] or not _amount > 0:
            raise Exception("CtbCoin::verify_amount(): _amount wrong type (%s), empty, or negative (%s)", type(_amount), _amount)

        return _amount

    def verify_minconf(self, _minconf = None):
        """
        Verify and return minimum number of confirmations
        """

        if not _minconf or not type(_minconf) == int or not _minconf >= 0:
            raise Exception("CtbCoin::verify_minconf(): _minconf wrong type (%s), empty, or negative (%s)", type(_minconf), _minconf)

        return _minconf
