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

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, ForeignKey, Numeric, UnicodeText
from sqlalchemy.pool import SingletonThreadPool

class CointipBotDatabase:

  metadata = MetaData()

  def __init__(self, dsn_url):
    '''Pass a DSN URL conforming to the SQLAlchemy API'''
    self.dsn_url = dsn_url

  def connect(self):
    '''Return a connection object'''
    engine = create_engine(self.dsn_url, echo_pool=True, poolclass=SingletonThreadPool)
    self.metadata.create_all(engine)
    return engine
