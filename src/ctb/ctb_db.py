#!/usr/bin/env python

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
