#!/usr/bin/env python2.6

import logging
logging.basicConfig(level=logging.INFO)

from collections import defaultdict
import eventlet
from eventlet import wsgi, listen, spawn_n, GreenPool, spawn
from eventlet.green import urllib2, httplib, socket

from itty import get, run_itty, handle_request

import re
import gdbm
import json
import os
import urllib
import urlparse

STREAM_URL = 'http://stream.meetup.com/2/open_events'

DBM_FILE = os.path.join(os.path.dirname(__file__), 'sniperdata.gdbm')

rsvp_pool = GreenPool()

def rsvp_url(**data):
    return 'http://api.meetup.com/rsvp?' + \
        urllib.urlencode(data)


class MupMap(object):
    """Class to store tokens
    """

    def __init__(self, db):
        self._muptokens = defaultdict(set)
        self._db = db
        self._init_from_db()

    def add_token(self, mup, token):
        logging.info("adding token for %s" % mup)
        self._muptokens[str(mup)].add(token)
        self._sync(str(mup))
        return 'OK'

    def del_token(self, mup, token):
        logging.info("deleting token for %s" % mup)
        self._muptokens[str(mup)].remove(token)
        self._sync(str(mup))
        return 'OK'

    def details(self, mup):
        return 'Sniped by %s members' % len(self._muptokens[mup])

    def on_event(self, mup):
        if mup['id'].isdigit():
            logging.info('checking to see if we snipe: %s' % str(mup['group']['id']))
            tokens = self._muptokens.get(str(mup['group']['id']))
            if tokens:
                for token in tokens:
                    rsvp_pool.spawn_n(self.new_rsvp, str(mup['id']), token)
            else:
                logging.info("we don't snipe that group")
        else:
            print 'hmmm'

    def new_rsvp(self, event_id, token):
        try:
            result = json.loads(urllib2.urlopen(
                    rsvp_url(rsvp='yes', event_id=event_id, key=token)).read())
            logging.info('Successfully RSVP for event_id = %s, key = %s' % \
                             (event_id, token))
        except Exception, e:
            logging.error('Failed to RSVP key = %s for event_id = %s: %s' % \
                              (token, event_id, str(e)))

    def _sync(self, mup):
        self._db[mup] = ';'.join(self._muptokens[mup])
        self._db.sync()

    def _init_from_db(self):
        logging.info("loading db")
        key = self._db.firstkey()
        while key != None:
            self._muptokens[key] = set(self._db[key].split(';'))
            key = self._db.nextkey(key)


def get_stream(url):
    """Not sure why, but urllib2 and MU Stream API don't like each other
    """
    bits = urlparse.urlparse(url)
    port = 80
    host = bits[1]
    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    s = socket.socket()
    s.connect((host, port))
    s.send("""GET %s HTTP/1.0\r\nHost: stream.dev.meetup.com\r\n\r\n""" \
               % bits[2])
    # read the response
    req = s.makefile('r')
    line = req.readline()
    while line.strip() != '':
        line = req.readline()

    return req

def listen_to_stream(mupmap):
    req = None
    while True:
        logging.info("Connecting to the stream")
        try:
            req = get_stream(STREAM_URL)
            while True:
                event_chunk = req.readline().strip()
                if event_chunk and event_chunk.startswith('{'):
                    event = json.loads(event_chunk)
                    mupmap.on_event(event)
        except Exception, e:
            logging.error(e)
        finally:
            if req:
                req.close()


MUPMAP = MupMap(gdbm.open(DBM_FILE, 'c'))

# web interface starts here.
@get('/')
def index(request):
    return """<html><head><title>sort of</title></head>
<body>
<h2>We support 2 operations:</h2>
<h3>Add a token</h3>
<pre>/add/<i>chapter_id</i>/<i>key</i>/<i>secret</i></pre>
<h3>Delete a token</h3>
<pre>/del/<i>chapter_id</i>/<i>key</i>/<i>secret</i></pre>
</body></html>"""


@get('/(?P<op>(del|add))/(?P<group_id>\d+)/(?P<token>\w+)/?')
def op(request, op='add', group_id=None, token=None):
    func = getattr(MUPMAP, '%s_token' % op)
    return func(str(group_id), token)

@get('/(?P<group_id>\d+)/?')
def details(request, op='add', group_id=None, token=None):
    return MUPMAP.details(str(group_id))

if __name__ == '__main__':
    spawn_n(listen_to_stream, MUPMAP)
    run_itty(server='eventlet', port=9001)
