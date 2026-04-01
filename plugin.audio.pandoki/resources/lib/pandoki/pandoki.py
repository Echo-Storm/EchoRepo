import collections, re, socket, sys, threading, time, os
import traceback
import urllib
try:
    import urllib3
    _urllib3 = True
except ImportError:
    _urllib3 = False
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs

import mypithos
from musicbrainzngs import set_useragent, search_recordings

_addon	= xbmcaddon.Addon()
_base	= sys.argv[0]
_id	= _addon.getAddonInfo('id')
_version	= _addon.getAddonInfo('version')
_stamp	= str(time.time())
_debug = _addon.getSetting('debug') == 'true'
_notification = _addon.getSetting('notification') == 'true'
 
# xbmc.LOGDEBUG = 0
# xbmc.LOGERROR = 4
# xbmc.LOGFATAL = 6
# xbmc.LOGINFO = 1
# xbmc.LOGNONE = 7
# xbmc.LOGNOTICE = 2
# xbmc.LOGSEVERE = 5
# xbmc.LOGWARNING = 3

KODIMONITOR = xbmc.Monitor()
CA_CERTS = xbmcvfs.translatePath('special://system/certs/cacert.pem')


# setup the ability to provide notification to the Kodi GUI
iconart = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.pandoki',  'icon.png'))


def log(msg, s = None, level = xbmc.LOGDEBUG):
    if _debug == False and level != xbmc.LOGERROR: return
    if level == xbmc.LOGERROR: msg += ' ,' + traceback.format_exc()
    if s and s.get('artist'): xbmc.log("%s-%s %s %s '%s - %s'" % (_id, _version, msg, s['token'][-4:], s['artist'], s['title']), level) # song
    elif s:                   xbmc.log("%s-%s %s %s '%s'"      % (_id, _version, msg, s['token'][-4:], s['title']), level)              # station
    else:                     xbmc.log("%s-%s %s"              % (_id, _version, msg), level)


def notification(title, message, ms, nart):
    if _notification == False: return
    xbmc.executebuiltin("Notification(" + title + "," + message + "," + ms + "," + nart + ")")


_UNSET = object()  # sentinel so Val() can distinguish "no value given" from falsy values like '' or 0

def Val(key, val = _UNSET):
    if key in [ 'author', 'changelog', 'description', 'disclaimer', 'fanart', 'icon', 'id', 'name', 'path', 'profile', 'stars', 'summary', 'type', 'version' ]:
        return _addon.getAddonInfo(key)

    # FIX: was `if val:` which silently read instead of writing when val was '', 0, or False
    if val is not _UNSET: _addon.setSetting(key, val)
    else:                  return _addon.getSetting(key)


def Prop(key, val = 'get'):
    if val == 'get':
        retVal = xbmcgui.Window(10000).getProperty("%s.%s" % (_id, key))
        log('def Prop %s=%s value=%s' % (key, val, retVal), None, xbmc.LOGDEBUG)
        return retVal
    else:
        log('def Prop %s=%s ' % (key, val), None, xbmc.LOGDEBUG)
        xbmcgui.Window(10000).setProperty("%s.%s" % (_id, key), val)


_maxdownloads=int(Val('maxdownload'))

class Pandoki(object):
    def __init__(self):
        run = Prop('run')
        if run and time.time() < float(run) + 3: return

        Prop('run', str(time.time()))
        Prop('stamp', _stamp)

        self.once	= True
        self.downloading = 0  # number of files currently being downloaded
        self.abort	= False
        self.mesg	= None
        self.station	= None
        self.stations	= None
        self.songs	= { }
        self.pithos	= mypithos.Pithos()
        self.player	= xbmc.Player()
        self.playlist	= xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        self.ahead	= { }
        self.queue	= collections.deque()
        self.prof	= Val('prof')
        self.wait	= { 'auth' : 0, 'stations' : 0, 'flush' : 0, 'scan' : 0, 'next' : 0 }
        self.silent	= xbmcvfs.translatePath("special://home/addons/%s/resources/media/silent.m4a" % _id)

        set_useragent("kodi.%s" % _id, Val('version'))
        xbmcvfs.mkdirs(xbmcvfs.translatePath(Val('cache')))
        xbmcvfs.mkdirs(xbmcvfs.translatePath(Val('library')))

    def Proxy(self):
        log('def Proxy')
        proxy = Val('proxy')

        if proxy == '1':	# None
            hand = urllib.request.ProxyHandler({})
            return urllib.request.build_opener(hand)

        elif proxy == '0':	# Global
            if Val('sni') == 'true' and _urllib3:
                return urllib3.PoolManager(
                    cert_reqs='CERT_REQUIRED',
                    ca_certs=CA_CERTS
                )
            else:
                return urllib.request.build_opener()

        elif proxy == '2':	# Custom
            if Val('sni') == 'true' and _urllib3:
                auth_header = urllib3.make_headers(proxy_basic_auth='%s:%s' % (Val('proxy_user'), Val('proxy_pass')))
                return urllib3.ProxyManager('http://%s:%s/' % (Val('proxy_host'), Val('proxy_port')), proxy_headers=auth_header)
            else:
                http = 'http://%s:%s@%s:%s' % (Val('proxy_user'), Val('proxy_pass'), Val('proxy_host'), Val('proxy_port'))
                hand = urllib.request.ProxyHandler({ 'http' : http, 'https' : http })
                return urllib.request.build_opener(hand)


    def Auth(self):
        log('def Auth')
        p = Val('prof')
        if self.prof != p:
            self.wait['auth'] = 0
            self.stations = None
            self.prof = p

        if time.time() < self.wait['auth']: return True

        self.pithos.set_url_opener(self.Proxy(), (Val('sni') == 'true'))

        try: self.pithos.connect(Val('one' + p), Val('username' + p), Val('password' + p))
        except mypithos.PithosError:
            log('Auth  Failed')
            return False

        self.wait['auth'] = time.time() + (60 * 60)	# Auth every hour
        log('Auth  OK')
        return True


    def Login(self):
        log('def Login')
        # if (Val('sni') == 'true') and (not _urllib3):
        #     if xbmcgui.Dialog().yesno(Val('name'), 'SNI Support not found', 'Please install: pyOpenSSL/ndg-httpsclient/pyasn1', 'Check Settings?'):
        #         xbmcaddon.Addon().openSettings()
        #     else:
        #         exit()

        while not self.Auth():
            prof_label = 'Account%s' % (int(Val('prof')) + 1)
            if xbmcgui.Dialog().yesno(Val('name'), 'Login Failed for %s' % prof_label, 'Check username, password, and One/Free account toggle', 'Open Settings?'):
                xbmcaddon.Addon().openSettings()
            else:
                exit()


    def Stations(self):
        log('def Stations')
        if (self.stations) and (time.time() < self.wait['stations']):
            return self.stations

        if not self.Auth(): return None
        self.stations = self.pithos.get_stations()

        self.wait['stations'] = time.time() + (60 * 2)				# IMPROVEMENT: reduced from 5min to 2min - reflects station edits sooner
        return self.stations


    def Sorted(self):
        log('def Sorted')
        sort = Val('sort')
        stations = list(self.Stations())
        quickmix = stations.pop(0)						# Quickmix

        if   sort == '0': stations = stations					# Normal
        elif sort == '2': stations = stations[::-1]				# Reverse
        elif sort == '1': stations = sorted(stations, key=lambda s: s['title'])	# A-Z
        # IMPROVEMENT: random shuffle option for discovery
        elif sort == '3':
            import random
            random.shuffle(stations)

        stations.insert(0, quickmix)						# Quickmix back on top
        return stations


    def Dir(self, handle):
        log('def Dir')
        self.Login()

        # Read virtualizer state once here so the label reflects current state
        # for every station item without making a JSON-RPC call per item.
        try:
            import json
            _virt_result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Settings.GetSettingValue","params":{"setting":"audiooutput.stereoupmix"}}')
            _virt_on = json.loads(_virt_result).get('result', {}).get('value', False)
        except Exception:
            _virt_on = None  # couldn't read state - fall back to neutral label

        if   _virt_on is True:  virt_label = 'Music Virtualizer: ON  [toggle off]'
        elif _virt_on is False: virt_label = 'Music Virtualizer: OFF [toggle on]'
        else:                   virt_label = 'Toggle Music Virtualizer'

        ic = Val('icon')
        li = xbmcgui.ListItem('New Station ...')
        li.setArt({'icon': ic, 'thumb': ic})
        xbmcplugin.addDirectoryItem(int(handle), "%s?search=hcraes" % _base, li, True)

        for s in self.Sorted():
            li = xbmcgui.ListItem(s['title'], s['token'])
            if self.station == s: li.select(True)

            art = Val("art-%s" % s['token'])
            if not art: art = s.get('art', ic)

            li.setArt({'icon': art, 'thumb': art})

            title = s['title']
            rurl = "RunPlugin(plugin://%s/?%s)" % (_id, urllib.parse.urlencode({ 'rename' : s['token'], 'title' : title }))
            durl = "RunPlugin(plugin://%s/?%s)" % (_id, urllib.parse.urlencode({ 'delete' : s['token'], 'title' : title }))
            surl = "RunPlugin(plugin://%s/?%s)" % (_id, urllib.parse.urlencode({  'thumb' : s['token'], 'title' : title }))
            vurl = "RunPlugin(plugin://%s/?%s)" % (_id, urllib.parse.urlencode({ 'virtualizer' : '1' }))
            visurl = "RunPlugin(plugin://%s/?%s)" % (_id, urllib.parse.urlencode({ 'visualizer' : '1' }))

            li.addContextMenuItems([('Rename Station',  rurl),
                                    ('Delete Station',  durl),
                                    ('Select Thumb',    surl),
                                    (virt_label,        vurl),
                                    ('Toggle Visualizer',  visurl), ])

            burl = "%s?%s" % (_base, urllib.parse.urlencode({ 'play' : s['token'] }))
            xbmcplugin.addDirectoryItem(int(handle), burl, li)

        xbmcplugin.endOfDirectory(int(handle), cacheToDisc = False)
        # wait for the window to appear in Kodi before continuing
        KODIMONITOR.waitForAbort(3)
        log("Dir   OK %4s" % handle)


    def Search(self, handle, query):
        log('def Search %s ' % query)
        self.Login()

        # FIX: pithos.search() raises PithosError when Pandora's API returns an error
        # (e.g. auth lapse, rate limit, or server hiccup). Previously this propagated
        # uncaught all the way up through Loop() and crashed the plugin instance.
        # Now we catch it, show a notification, and close the directory cleanly.
        try:
            results = self.pithos.search(query, True)
        except mypithos.PithosError as e:
            log('Search failed: %s' % str(e), None, xbmc.LOGERROR)
            notification('Search Failed', 'Pandora returned an error. Try again.', '4000', iconart)
            xbmcplugin.endOfDirectory(int(handle), succeeded = False, cacheToDisc = False)
            return

        for s in results:
            title = s['artist']
            title += (' - %s' % s['title']) if s.get('title') else ''

            li = xbmcgui.ListItem(title, s['token'])
            xbmcplugin.addDirectoryItem(int(handle), "%s?create=%s" % (_base, s['token']), li)

        xbmcplugin.endOfDirectory(int(handle), cacheToDisc = False)
        log("Search   %4s '%s'" % (handle, query))


    def Info(self, s):
        log('def Info')
        info = { 'artist' : s['artist'], 'album' : s['album'], 'title' : s['title'], 'rating' : s['rating'], 'mediatype':'song' }

        if s.get('duration'):
            info['duration'] = s['duration']

        return info


    def Add(self, song):
        log('def Add ', song)
        if song['token'] != 'mesg':
            self.songs[song['token']] = song

        li = xbmcgui.ListItem(song['artist'], song['title'])
        li.setArt({'icon': song['art'], 'thumb': song['art']})
        li.setProperty("%s.token" % _id, song['token'])

        # FIX: li.setInfo('music', ...) is deprecated in Kodi 21 and logs warnings.
        # Using InfoTagMusic setters instead - same data, no deprecation noise.
        tag = li.getMusicInfoTag()
        tag.setArtist(song['artist'])
        tag.setAlbum(song['album'])
        tag.setTitle(song['title'])
        tag.setRating(float(song['rating']) if song.get('rating') else 0.0)
        tag.setMediaType('song')
        if song.get('duration'):
            tag.setDuration(int(song['duration']))

        if song.get('encoding') == 'm4a': li.setProperty('mimetype', 'audio/aac')
        if song.get('encoding') == 'mp3': li.setProperty('mimetype', 'audio/mpeg')

        log('def Add  adding %s' % song['path'], song)
        self.playlist.add(song['path'], li)
        self.Scan(False)
        log('Add   OK', song)


    def Queue(self, song):
        log('def Queue ', song)
        self.queue.append(song)


    def Msg(self, msg):
        log('def Msg %s ' % msg, None, xbmc.LOGDEBUG)
        if self.mesg == msg: return
        else: self.mesg = msg
        
        # added ready (true if file is ready to play and starttime to know how
        # long it has been taking to download file
        song = { 'starttime' : time.time(), 'ready' : False, 'token' : 'mesg', 'title' : msg, 'path' : self.silent, 'artist' : Val('name'),  'album' : Val('description'), 'art' : Val('icon'), 'rating' : '' }
        self.Queue(song)


    def Tag(self, song):
        log('def Tag', song)
        try:
            res = search_recordings(limit = 1, query = song['title'], artist = song['artist'], release = song['album'], qdur = str(song['duration'] * 1000))['recording-list'][0]
            # FIX: was hardcoded medium-list[1] which crashed on single-disc releases (IndexError).
            # Now tries index 1 first (multi-disc), falls back to index 0 (standard single disc).
            medium_list = res['release-list'][0].get('medium-list', [])
            medium = medium_list[1] if len(medium_list) > 1 else medium_list[0] if medium_list else None
            if medium:
                song['number'] = int(medium['track-list'][0]['number'])
                song['count']  =     medium['track-count']
            else:
                song['number'] = 0
                song['count']  = 0
            song['score']  =     res['ext:score']
            song['brain']  =     res['id']

        except Exception:
            # FIX: was bare except which swallowed KeyboardInterrupt and SystemExit
            song['score']  = '0'

        log("Tag%4s%%" % song['score'], song, xbmc.LOGINFO)
        return song['score'] == '100'


    def Save(self, song):
        log('def Save ', song)
        if song['title'] == 'Advertisement' or song.get('saved') or not song.get('cached', False): return
        if Val('mode') in ('0', '1') or (Val('mode') == '3' and song.get('voted') != 'up'): return
        if not self.Tag(song): return

        tmp = "%s.%s" % (song['path'], song['encoding'])
        if not xbmcvfs.copy(song['path_cch'], tmp):
            log('Save Failed', song, xbmc.LOGINFO)
            return

        if   song['encoding'] == 'm4a': tag = EasyMP4(tmp)
        elif song['encoding'] == 'mp3': tag = MP3(tmp, ID3 = EasyID3)

        if tag == None:
            log('Save Failed', song, xbmc.LOGINFO)
            xbmcvfs.delete(tmp)
            return

        tag['tracknumber']         = "%d/%d" % (song['number'], song['count'])
        tag['musicbrainz_trackid'] = song['brain']
        tag['artist']              = song['artist']
        tag['album']               = song['album']
        tag['title']               = song['title']
        log("Save: metadata %s %s %s %s %s" % (song['brain'], song['artist'], song['album'], song['title']), song)

        if song['encoding'] == 'mp3':
            tag.save(v2_version = 3)
        else:
            tag.save()

        xbmcvfs.mkdirs(song['path_dir'])
        xbmcvfs.copy(tmp, song['path_lib'])
        xbmcvfs.delete(tmp)
        log('Save: Song Cached ', song)

        song['saved'] = True

        if song.get('art', False) and not xbmcvfs.exists(song['path_alb']) or not xbmcvfs.exists(song['path_art']):
            try:
                strm = self.Proxy().open(song['art'])
                data = strm.read()
            except ValueError:
                log("Save ART      '%s'" % song['art'], None, xbmc.LOGINFO)
                return

            for jpg in [ song['path_alb'], song['path_art'] ]:
                if not xbmcvfs.exists(jpg):
                    file = xbmcvfs.File(jpg, 'wb')
                    file.write(data)
                    file.close()

        log('Save  OK', song)


    def Hook(self, song, size, totl):
        log('def Hook ', song)
        if totl in (341980, 340554, 173310):	# empty song cause requesting to fast
            self.Msg('Too Many Songs Requested')
            log('Cache MT', song, xbmc.LOGINFO)
            return False

        if song['title'] != 'Advertisement' and totl <= int(Val('adsize')) * 1024:
            log('Cache AD', song, xbmc.LOGINFO)

            song['artist'] = Val('name')
            song['album']  = Val('description')
            song['art']    = Val('icon')
            song['title']  = 'Advertisement'

            if Val('skip') == 'true':
                song['qued'] = True
                self.Msg('Skipping Small Songs')

        log('Cache QU: ready=%s size=%8d bitrate:%8d' % (song.get('ready'), size, song['bitrate']), song)
        if song.get('ready',False) and not song.get('qued') and size >= (song['bitrate'] / 8 * 1024 * int(Val('delay'))):
            song['qued'] = True
            self.Queue(song)

        return True


    def Cache(self, song):
        log('def Cache ', song)
        try:
            strm = self.Proxy().open(song['url'], timeout = 10)
        except Exception: # FIX: was bare except - now catches Exception only, lets SystemExit/KeyboardInterrupt propagate
            self.wait['auth'] = 0
            if not self.Auth():
                log("Cache ER", song, xbmc.LOGINFO)
                return
            strm = self.Proxy().open(song['url'], timeout = 10)

        totl = int(strm.headers['Content-Length'])
        size = 0
        lastsize = -1

        log("Expecting %8d bytes " % totl, song, xbmc.LOGINFO)

        cont = self.Hook(song, size, totl)
        if not cont: return

        file = xbmcvfs.File(song['path_cch'], 'wb')
        self.downloading = self.downloading + 1
        song['starttime'] = time.time()
        lastnotify = time.time()
        notification('Caching', '[COLOR lime]' + song['title'] + ' [/COLOR]' , '3000', iconart)
        while (cont) and (size < totl) and (not KODIMONITOR.abortRequested()) and (not self.abort):
            log("Downloading %8d bytes, currently %8d bytes " % (totl, size), song)
            try: data = strm.read(min(8192, totl - size))
            except socket.timeout:
                log('Socket Timeout: Bytes Received %8d: Cache TO' % size, song)
                song['ready'] = True
                break

            file.write(data)
            size += len(data)
            if lastnotify + 60 < time.time():
                if size == lastsize:
                    log('Aborting Song, Song Stopped Buffering: %d out of %d downloaded' % (size, totl), song)
                    # FIX: was missing comma after first arg (string literal concatenation bug), also only had 3 args instead of 4
                    notification('Song Stopped Buffering', '[COLOR lime] %d' % (size * 100 / totl ) + '% ' + song['title'] + ' [/COLOR]' , '5000', iconart)
                    break
                lastnotify = time.time()
                lastsize = size
                notification('Song Buffering', '[COLOR lime] %d' % (size * 100 / totl ) + '% ' + song['title'] + ' [/COLOR]' , '5000', iconart)
            if size >= totl:
                log('Setting song to ready ', song)
                song['ready'] = True
            cont = self.Hook(song, size, totl)

        file.close()
        strm.close()
        self.downloading = self.downloading - 1

        if not cont or size != totl:
            xbmcvfs.delete(song['path_cch'])
            log('Cache RM', song)

        else:
            song['cached'] = True
            self.Save(song)

        log('Cache Download Complete, Still Downloading:%d' % self.downloading, song, xbmc.LOGINFO)


    def Fetch(self, song):
        log('def Fetch ', song)
        if xbmcvfs.exists(song['path_mp3']):	# Found MP3 in Library
            log('Song MP3', song, xbmc.LOGINFO)
            song['path_lib'] = song['path_mp3']
            song['path'] = song['path_lib']
            song['saved'] = True

        elif xbmcvfs.exists(song['path_m4a']):	# Found M4A in Library
            log('Song M4A', song, xbmc.LOGINFO)
            song['path_lib'] = song['path_m4a']
            song['path'] = song['path_lib']
            song['saved'] = True

        elif xbmcvfs.exists(song['path_cch']):	# Found in Cache
            log('Song CCH', song, xbmc.LOGINFO)
            song['path'] = song['path_cch']

        elif Val('mode') == '0':		# Stream Only
            log('Song PAN', song, xbmc.LOGINFO)
            song['path'] = song['url']

        else:					# Cache / Save
            log('Song GET', song, xbmc.LOGINFO)
            song['path'] = song['path_cch']
            self.Cache(song)
            return

        self.Queue(song)



    def Seed(self, song):
        log('def Seed')
        if not self.Stations(): return
        result = self.pithos.search("%s by %s" % (song['title'], song['artist']))[0]

        if result['title'] == song['title'] and result['artist'] == song['artist']:
            self.pithos.seed_station(song['station'], result['token'])
        else:
            log('Seed BAD', song)


    def Branch(self, song):
        log('def Branch')
        if not self.Stations(): return
        station = self.pithos.branch_station(song['token'])

        Prop('play', station['token'])
        Prop('action', 'play')

        log('Branch  ', song, xbmc.LOGINFO)


#    def Del(self, song):
#        xbmcvfs.delete(song['path_lib'])


    def Rate(self, mode):
        log('def Rate')
        pos  = self.playlist.getposition()
        item = self.playlist[pos]
        tokn = item.getProperty("%s.token" % _id)
        song = self.songs.get(tokn)

        if not song:
            return

        elif mode == 'branch':
            self.Branch(song)
            return

        elif mode == 'seed':
            self.Seed(song)

        elif mode == 'up':
            song['voted'] = 'up'
            Prop('voted', 'up')
            self.pithos.add_feedback(song['token'], True)
            notification('Thumb UP', song['title'], '3000', iconart)
            self.Save(song)

        elif mode == 'tired':
            self.player.playnext()
            self.pithos.set_tired(song['token'])

        elif mode == 'down':
            song['voted'] = 'down'
            Prop('voted', 'down')
            self.player.playnext()
            self.pithos.add_feedback(song['token'], False)
            notification('Thumb DOWN', song['title'], '3000', iconart)

        elif mode == 'clear':
            song['voted'] = ''
            Prop('voted', '')
            feedback = self.pithos.add_feedback(song['token'], True)
            self.pithos.del_feedback(song['station'], feedback)
            notification('Thumb CLEARED', song['title'], '3000', iconart)

        else: return

        log("%-8s" % mode.title(), song, xbmc.LOGINFO)


    def Rated(self, song, rating):
        log("Rate %1s>%1s" % (song['rating'], rating), song, xbmc.LOGINFO)

        expert = (Val('rating') == '1')
        song['rating'] = rating
        song['rated'] = rating

        if rating == '5':
            if expert:
                self.Branch(song)
            else:
                self.pithos.add_feedback(song['token'], True)
                notification('Thumb UP', song['title'], '3000', iconart)
            self.Save(song)

        elif rating == '4':
            if expert:
                self.Seed(song)
            else:
                self.pithos.add_feedback(song['token'], True)
                notification('Thumb UP', song['title'], '3000', iconart)
            self.Save(song)

        elif rating == '3':
            self.pithos.add_feedback(song['token'], True)
            notification('Thumb UP', song['title'], '3000', iconart)
            self.Save(song)

        elif rating == '2':
            if expert:
                self.pithos.set_tired(song['token'])
            else:
                self.pithos.add_feedback(song['token'], False)
                notification('Thumb DOWN', song['title'], '3000', iconart)
            self.player.playnext()

        elif rating == '1':
            self.pithos.add_feedback(song['token'], False)
            notification('Thumb DOWN', song['title'], '3000', iconart)
            self.player.playnext()

        elif rating == '':
            feedback = self.pithos.add_feedback(song['token'], True)
            self.pithos.del_feedback(song['station'], feedback)
            notification('Thumb CLEARED', song['title'], '3000', iconart)


    def Scan(self, rate = False):
        log('def Scan')
        if (rate and time.time() < self.wait['scan']) or xbmcgui.getCurrentWindowDialogId() == 10135: return
        self.wait['scan'] = time.time() + 15

        songs = dict()
        for pos in range(0, self.playlist.size()):
            tk = self.playlist[pos].getProperty("%s.token" % _id)
            rt = xbmc.getInfoLabel("MusicPlayer.Position(%d).Rating" % pos)
            if rt == '': rt = '0'

            if tk in self.songs:
                song = self.songs[tk]
                del self.songs[tk]
                songs[tk] = song

                if rate and song.get('rating', rt) != rt:
                    self.Rated(song, rt)
                elif not song.get('rating'):
                    song['rating'] = rt

        for s in self.songs:
            if not self.songs[s].get('keep', False) and xbmcvfs.exists(self.songs[s].get('path_cch')):
                xbmcvfs.delete(self.songs[s]['path_cch'])
                log('Scan  RM', self.songs[s], xbmc.LOGINFO)

        self.songs = songs


    def Path(self, s):
        log('def Path')
        lib  = Val('library')
        badc = '\\/?%*:|"<>'		# FIX: removed '.' - period is valid in filenames and was mangling names like "Jr." or "Vol. 1"

        s['artist'] = ''.join(c for c in s['artist'] if c not in badc)
        s['album']  = ''.join(c for c in s['album']  if c not in badc)
        s['title']  = ''.join(c for c in s['title']  if c not in badc)

        s['path_cch'] = xbmcvfs.translatePath("%s/%s - %s.%s"            % (Val('cache'), s['artist'], s['title'],  s['encoding']))
        s['path_dir'] = xbmcvfs.translatePath("%s/%s/%s - %s"            % (lib,          s['artist'], s['artist'], s['album']))
        s['path_m4a'] = xbmcvfs.translatePath("%s/%s/%s - %s/%s - %s.%s" % (lib,          s['artist'], s['artist'], s['album'], s['artist'], s['title'], 'm4a')) #s['encoding']))
        s['path_mp3'] = xbmcvfs.translatePath("%s/%s/%s - %s/%s - %s.%s" % (lib,          s['artist'], s['artist'], s['album'], s['artist'], s['title'], 'mp3')) #s['encoding']))
        s['path_lib'] = xbmcvfs.translatePath("%s/%s/%s - %s/%s - %s.%s" % (lib,          s['artist'], s['artist'], s['album'], s['artist'], s['title'], s['encoding']))
        s['path_alb'] = xbmcvfs.translatePath("%s/%s/%s - %s/folder.jpg" % (lib,          s['artist'], s['artist'], s['album']))
        s['path_art'] = xbmcvfs.translatePath("%s/%s/folder.jpg"         % (lib,          s['artist'])) #.decode("utf-8"

        title = ''.join(c for c in self.station['title'] if c not in badc)
        s['path_m3u'] = xbmcvfs.translatePath("%s/%s.m3u"                % (lib, title))
        s['path_rel'] = xbmcvfs.translatePath(   "%s/%s - %s/%s - %s.%s" % (     s['artist'], s['artist'], s['album'], s['artist'], s['title'], s['encoding']))


    def Fill(self):
        log('def Fill')
        token = self.station['token']
        if len(self.ahead.get(token, '')) > 0: return

        if not self.Auth():
            self.Msg('Login Failed. Check Settings')
            self.abort = True
            return

        try: songs = self.pithos.get_playlist(token, int(Val('quality')))
        except (mypithos.PithosTimeout, mypithos.PithosNetError): pass
        except (mypithos.PithosAuthTokenInvalid, mypithos.PithosAPIVersionError, mypithos.PithosError) as e:
            log("%s, %s" % (e.message, e.submsg))
            self.Msg(e.message)
            self.abort = True
            return

        for song in songs:
            self.Path(song)

        self.ahead[token] = collections.deque(songs)

        log('Fill  OK', self.station, xbmc.LOGINFO)


    def Next(self):
        log('def Next %s %s' % (time.time(), self.wait['next']))
        # keeps the number of downloads clamped to _maxdownloads
        if time.time() < self.wait['next'] or self.downloading >= _maxdownloads: return
        self.wait['next'] = time.time() + float(Val('delay')) + 1

        self.Fill()

        token = self.station['token']
        if len(self.ahead.get(token, '')) > 0:
            song = self.ahead[token].popleft()
            threading.Timer(0, self.Fetch, (song,)).start()


    def List(self):
        log('def List')
        if not self.station or not self.player.isPlayingAudio(): return

        len1  = self.playlist.size()
        pos  = self.playlist.getposition()
        item = self.playlist[pos]
        tokn = item.getProperty("%s.token" % _id)

        if tokn in self.songs:
            Prop('voted', self.songs[tokn].get('voted', ''))

#        skip = xbmc.getInfoLabel("MusicPlayer.Position(%d).Rating" % pos)
#        skip = ((tokn == 'mesg') or (skip == '1') or (skip == '2')) and (xbmcgui.getCurrentWindowDialogId() != 10135)
        
        # keep adding until number of max downloads is in list not played
        if (len1 - pos) < 2 or (len1 - pos + self.downloading) < (_maxdownloads + 1):
            self.Next()

        log('###################22222222 PLAYLIST INFO: %s %s %s' % ( len1, pos, tokn))
        if ((len1 - pos) > 1) and (tokn == 'mesg'):
            self.player.playnext()


    def Deque(self):
        log('def Deque %2d' % len(self.queue))
        if len(self.queue) == 0: return
        elif self.once:
            self.playlist.clear()
            self.Flush()

        while len(self.queue) > 0:
            song = self.queue.popleft()
            self.Add(song)

        if self.once:
            # this will start the  playlist playing
            self.player.play(self.playlist)
            log('def Deque setting once to False')
            self.once = False

        max = int(Val('history'))
        while self.playlist.size() > max and self.playlist.getposition() > 0:
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Playlist.Remove", "params":{"playlistid":' + str(xbmc.PLAYLIST_MUSIC) + ', "position":0}}')
            KODIMONITOR.waitForAbort(0.1)

        if xbmcgui.getCurrentWindowId() == 10500:
            xbmc.executebuiltin("Container.Refresh")


    def Tune(self, token):
        log('def Tune %s' % token)
        for s in self.Stations():
            if token == s['token'] or token == s['token'][-4:]:
                if self.station == s: return False

                self.station = s
                Val('station' + self.prof, token)
                return True

        return False


    def Play(self, token):
        log('Play  ??', self.station, xbmc.LOGINFO)
        last = self.station

        if self.Tune(token):
            self.Fill()

            while True:
                len = self.playlist.size() - 1
                pos = self.playlist.getposition()
                if len > pos:
                    item = self.playlist[len]
                    tokn = item.getProperty("%s.token" % _id)

                    if last and tokn in self.songs:
                        self.songs[tokn]['keep'] = True
                        self.ahead[last['token']].appendleft(self.songs[tokn])

                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Playlist.Remove", "params":{"playlistid":' + str(xbmc.PLAYLIST_MUSIC) + ', "position":' + str(len) + '}}')
                else: break

            self.Msg("%s" % self.station['title'])
            log('Play  OK', self.station)

        xbmc.executebuiltin('ActivateWindow(10500)')


    def Create(self, token):
        log('%s' % token, None, xbmc.LOGINFO)
        self.Stations()
#        self.Auth()
        station = self.pithos.create_station(token)

        log('Create  ', station, xbmc.LOGINFO)
        self.Play(station['token'])


    def Delete(self, token):
        if self.station and self.station['token'] == token: self.station = None

        self.Stations()
        station = self.pithos.delete_station(token)

        log('Delete  ', station, xbmc.LOGINFO)
        xbmc.executebuiltin("Container.Refresh")


    def Rename(self, token, title):
        self.Stations()
        station = self.pithos.rename_station(token, title)

        log('Rename  ', station, xbmc.LOGINFO)
        xbmc.executebuiltin("Container.Refresh")


    def Visualizer(self):
        # Proper toggle: checks if visualizer window is already active.
        # If open, sends Back to close it. If closed, opens it.
        # This matches the correct pattern used in plugin.audio.m3sr2019.
        if xbmc.getCondVisibility('Window.IsActive(visualisation)'):
            xbmc.executebuiltin('Action(Back)')
            log('Visualizer closed', None, xbmc.LOGINFO)
        else:
            xbmc.executebuiltin('ActivateWindow(Visualisation)')
            log('Visualizer opened', None, xbmc.LOGINFO)


    def Virtualizer(self):
        # Toggles Kodi's audio virtualizer (DSP/headphone surround) on and off.
        # Uses JSON-RPC to read the current state, flips it, writes it back,
        # then shows a notification confirming the new state.
        # The setting path is Settings.System.Audio.audiodevices.stereoupmix (bool).
        try:
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Settings.GetSettingValue","params":{"setting":"audiooutput.stereoupmix"}}')
            import json
            data = json.loads(result)
            current = data.get('result', {}).get('value', False)
            new_val = not current
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Settings.SetSettingValue","params":{"setting":"audiooutput.stereoupmix","value":%s}}' % ('true' if new_val else 'false'))
            state_label = '[COLOR lime]ON[/COLOR]' if new_val else '[COLOR red]OFF[/COLOR]'
            notification('Music Virtualizer', state_label, '3000', iconart)
            log('Music Virtualizer toggled to %s' % state_label, None, xbmc.LOGINFO)
        except Exception as e:
            log('Music Virtualizer toggle failed: %s' % str(e), None, xbmc.LOGERROR)
            notification('Music Virtualizer', 'Toggle failed - check log', '3000', iconart)


    def Action(self):
        act = Prop('action')
        log('def Action action=%s' % act, None, level = xbmc.LOGDEBUG)

        if _stamp != Prop('stamp'):
            self.abort = True
            self.station = None
            return

        elif act == '':
            Prop('run', str(time.time()))
            return

        elif act == 'search':
            self.Search(Prop('handle'), Prop('search'))
 
        elif act == 'create':
            self.Create(Prop('create'))

        elif act == 'rename':
            self.Rename(Prop('rename'), Prop('title'))

        elif act == 'delete':
            self.Delete(Prop('delete'))

        elif act == 'rate':
            self.Rate(Prop('rate'))

        elif act == 'virtualizer':
            self.Virtualizer()

        elif act == 'visualizer':
            self.Visualizer()

        act = Prop('action')

        if   act == 'play':
            self.Play(Prop('play'))

        elif act == 'dir':
            self.Dir(Prop('handle'))
            if (self.once or not self.player.isPlayingAudio()) and Val('autoplay') == 'true' and Val('station' + self.prof):
                self.Play(Val('station' + self.prof))

        Prop('action', '')
        Prop('run', str(time.time()))


    def Flush(self):
        log('def Flush')
        cch = xbmcvfs.translatePath(Val('cache'))
        reg = re.compile(r'^.*\.(m4a|mp3)')

        (dirs, list) = xbmcvfs.listdir(cch)

        for file in list:
            if reg.match(file):
                xbmcvfs.delete("%s/%s" % (cch, file))
                log("Flush OK      '%s'" % file)


    def Loop(self):
        log('def Loop')
        while not KODIMONITOR.abortRequested() and not self.abort and (self.once or self.player.isPlayingAudio()):

            self.Action()
            self.Deque()
            self.List()
            self.Scan()

            KODIMONITOR.waitForAbort(0.5)  # IMPROVEMENT: was 0.2s (5 polls/sec) - music player needs no faster than 2 polls/sec
                
        if self.player.isPlayingAudio():
            notification('Exiting', '[COLOR lime]No longer queuing new songs[/COLOR]' , '5000', iconart)
        log('Pankodi Exiting XBMCAbort?=%s PandokiAbort?=%s ' % (KODIMONITOR.abortRequested(), self.abort), None, level = xbmc.LOGINFO)
        Prop('run', '0')

