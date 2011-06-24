#!/usr/bin/env python2.6

import os
import cgi
import json
import functools

from eventlet.green import urllib2
from itty import get, post, run_itty, serve_static_file

STATIC_ROOT = os.path.join(os.path.dirname(__file__), 'static')
IMG_ROOT = os.path.join(STATIC_ROOT, 'img')
JS_ROOT = os.path.join(STATIC_ROOT, 'js')

SNIPERS_NEST = 'http://127.0.0.1:9001/%(op)s/%(group_id)s/%(token)s'

MEETUP_TOKEN_AUTH_URL = "http://api.dev.meetup.com/members/?relation=self&key=%(token)s"
MEETUP_GROUPS_URL = "http://api.dev.meetup.com/groups/?member_id=%(member_id)s&key=%(token)s"


TEMPLATE_TOP = """<html>
<head><title>Meetup Sniper</title>
<style type="text/css">
body {
 color: #000;
 background: #fff;
 font-family: Helvetica, sans;
 text-align: center;
}
#wrapper {
 width: 400px;
 margin: 0 auto;
}
#logo {
 display: block;
 background: #ffffff url('img/logo.png') no-repeat center top;
 height: 145px;
 text-indent: -9999em;
}
#subheader {
 margin: 0;
 padding: 0;
 text-align: center;
}
#content {
 text-align: left;
}
</style>
</head>
<body>
<div id="wrapper">
   <div id="header">
     <h1 id="logo">Meetup Sniper</h1>
     <h2 id="subheader">One group, automatic RSVPs</h2>
   </div>
   <div id="content">
"""

TEMPLATE_BOTTOM = """</div>
</div>
</body>
</html>"""


def snipe(token=None, group_id=None, op='add'):
    url = SNIPERS_NEST % {'token': token,
                          'group_id': group_id,
                          'op': op}
    return urllib2.urlopen(url).read()

snipe_on = functools.partial(snipe, op='add')
snipe_off = functools.partial(snipe, op='del')

def authorized_token(token):
    url = MEETUP_TOKEN_AUTH_URL % {'token': token}
    try:
        data = json.loads(urllib2.urlopen(url).read())
        return data['results'][0]['id']
    except Exception, e:
        return None

def get_groups(token, member_id):
    url = MEETUP_GROUPS_URL % {'member_id': member_id,
                               'token': token}
    try:
        # this is as dirty as it comes, but FU unicode errors!
        raw = [chr(ord(x)) for x in urllib2.urlopen(url).read() if ord(x) < 127]
        data = json.loads(''.join(raw))
        return data['results']
    except:
        return None

def template(content, **kwargs):
    return TEMPLATE_TOP + content % kwargs + TEMPLATE_BOTTOM


@get('/')
def index(request):
    return template("""
<h2>Give me your API token</h2>
<form method="get" action="/add">
  <input type="text" name="token" /> <input type="submit" value="Snipe My Meetups" />
</form>
""")

@get('/add/?')
def add(request):
    """Presents a form to check off meetups to snipe
    """
    token = request.GET.get('token', '')
    member_id = authorized_token(token)
    if member_id:
        rendered_groups = ''
        groups = get_groups(token, member_id)
        print groups
        if groups:
            g = []
            for group in groups:
                g.append("""<p><input type="checkbox" name="group_id" value="%(group_id)s" />
<strong>%(name)s</strong>
</p>""" % {'group_id': group['id'],
           'name': cgi.escape(group['name'])})

            rendered_groups = ''.join(g)

        return template("""
<h2>Pick some groups to snipe...</h2>
<form method="post" action="/add">
  <input type="hidden" name="token" value="%(token)s" />
  <input type="hidden" name="member_id" value="%(member_id)s" />
  %(groups)s
  <p>
    <input type="submit" value="Boom!" />
  </p>
</form>
""" % {'token': token, 'member_id': member_id, 'groups': rendered_groups})

    else:
        return template("""<p>Well, that's not a valid token.</p>""")


@post('/add/?')
def add(request):
    """Sets up the sniper to snipe stuff"""
    groups = request.POST.get('group_id', [])
    if not isinstance(groups, list):
        groups = [groups]

    for group in groups:
        snipe_on(token=request.POST.get('token'), group_id=group)

    return template("<h2>Consider yourself RSVPed for the next scheduled Meetup.</h2>")


@get('/img/(?P<file>.+)')
def img(request, file):
    return serve_static_file(request, file, root=IMG_ROOT)


@get('/js/(?P<file>.+)')
def js(request, file):
    return serve_static_file(request, file, root=IMG_ROOT)


if __name__ == '__main__':
    run_itty(server='eventlet', host='', port=9000)
