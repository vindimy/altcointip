import time, urllib2, json, logging

lg = logging.getLogger('cointipbot')

class CtbBtce(object):
    '''class for info from BTC-e Public API'''
    def __init__(self):
        self.tickerDict = {}
        self.url = 'https://btc-e.com/api/2/' #append pair, method
        self.btc_usd = {}
        self.btc_eur = {}
        self.btc_rur = {}
        self.ltc_btc = {}
        self.ltc_usd = {}
        self.ltc_rur = {}
        self.nmc_btc = {}
        self.usd_rur = {}
        self.eur_usd = {}

    def update(self,pairs):
        '''update pairs, assumes pairs is a dict'''
        for pair in pairs:
            if pairs[pair] == 'True':
                self.updatePair(pair)
        return self.tickerDict

    def parsePublicApi(self,url):
        '''public api parse method, returns dict, sleeps and retries on url/http errors'''
        while True:
            try:
                request = urllib2.Request(url)
                response = json.loads(urllib2.urlopen(request, timeout=3).read())
                return response
                break
            except urllib2.URLError:
                lg.warning("CtbBtce::parsePublicApi(): caught URL error")
                return None
            except urllib2.HTTPError:
                lg.warning("CtbBtce::parsePublicApi(): caught HTTP error")
                return None

    def ticker(self,pair):
        url = self.url + pair + '/ticker' #construct url
        ticker = self.parsePublicApi(url)
        return ticker

    def depth(self,pair):
        url = self.url + pair + '/depth'
        depth = self.parsePublicApi(url)
        return depth

    def trades(self,pair):
        url = self.url + pair + '/trades'
        trades = self.parsePublicApi(url)
        return trades

    def updatePair(self,pair):
        '''modular update pair method'''
        tick = self.ticker(pair)
        if not bool(tick):
            return None
        tick = tick['ticker']
        data = {}
        # uncomment what you need to use
        #data['high'] = tick.get('high',0)
        #data['low'] = tick.get('low',0)
        #data['last'] = tick.get('last',0)
        #data['buy'] = tick.get('buy',0)
        #data['sell'] = tick.get('sell',0)
        #data['vol'] = tick.get('vol',0)
        #data['volCur'] = tick.get('vol_cur',0)
        data['avg'] = tick.get('avg',0)
        # uncomment for gigantic dict
        #data['depth'] = self.depth(pair)
        #data['trades'] = self.trades(pair)
        self.tickerDict[pair] = data
        return data

