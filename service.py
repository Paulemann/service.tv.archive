#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sys
import base64
import json
import codecs
import subprocess
import time
import threading
import platform
import requests
import _strptime

from datetime import datetime, tzinfo, timedelta
from dateutil import tz

import xbmc
import xbmcaddon
import xbmcvfs

import io

try:
    from urllib.request import unquote
except ImportError:
    from urllib2 import unquote

if sys.version_info.major < 3:
    INFO = xbmc.LOGNOTICE
    from xbmc import translatePath, makeLegalFilename, validatePath
else:
    INFO = xbmc.LOGINFO
    from xbmcvfs import translatePath, makeLegalFilename, validatePath
DEBUG = xbmc.LOGDEBUG

KODIrecs = []
SETTING  = {}

__addon__      = xbmcaddon.Addon()
__setting__    = __addon__.getSetting
__addon_id__   = __addon__.getAddonInfo('id')
__localize__   = __addon__.getLocalizedString
__profile__    = __addon__.getAddonInfo('profile')

ffmpeg_exec    = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
ffprobe_exec   = 'ffprobe.exe' if platform.system() == 'Windows' else 'ffprobe'


def py(arg, charset='utf-8'):
    if sys.version_info.major < 3:
        return arg.decode(charset)
    return arg


def readSet(item, default):
    ret = set()
    for element in readVal(item, default).split(','):
        try:
            item = int(element)
        except ValueError:
            item = element.strip()
        ret.add(item)
    return ret


def readVal(item, default):
    try:
        value = int(__setting__(item))
    except ValueError:
        try:
            if __setting__(item).lower() == 'true' or __setting__(item).lower() == 'false':
                value = bool(__setting__(item).lower() == 'true')
            else:
                value = __setting__(item)
        except ValueError:
            value = default

    return value


def loadSettings():
    SETTING['sleepTime']         = readVal('sleep', 300)
    SETTING['tmFormat']          = '%Y-%m-%d %H:%M:%S'
    SETTING['locEncoding']       = sys.getfilesystemencoding()
    SETTING['dstEncoding']       = 'cp1252' if readVal('winencoding', False) else SETTING['locEncoding']
    SETTING['tmpDir']            = py(translatePath(__profile__), charset=SETTING['locEncoding'])
    SETTING['dstDir']            = py(readVal('destdir', '/home/kodi/Videos'), charset=SETTING['dstEncoding'])
    SETTING['pvrPort']           = readVal('pvrport', 34890)
    SETTING['pvrDir']            = py(readVal('recdir', '/home/kodi/Aufnahmen'), charset=SETTING['locEncoding'])
    SETTING['recSort']           = readVal('recsort', 0)
    SETTING['delSource']         = readVal('delsource', False)
    SETTING['convertNew']        = readVal('addnew', False)
    SETTING['addEpisode']        = readVal('addepisode', False)
    SETTING['addChannel']        = readVal('addchannel', True)
    SETTING['addStarttime']      = readVal('addstarttime', True)
    SETTING['createTitle']       = readVal('createtitle', False)
    SETTING['groupShows']        = readVal('groupshows', False)
    SETTING['individualStreams'] = readVal('allstreams', True)
    SETTING['forceSD']           = readVal('forcesd', False)
    SETTING['subtitles']         = readVal('subtitles', False)
    SETTING['deinterlaceVideo']  = readVal('deinterlace', True)
    SETTING['recodeAudio']       = readVal('recode', False)
    SETTING['overwrite']         = readVal('overwrite', True)
    SETTING['notifySuccess']     = readVal('successnote', True)
    SETTING['notifyFailure']     = readVal('failurenote', True)
    SETTING['col2grey']          = False #readVal('col2grey', False)
    SETTING['outputFmt']         = '.' + readVal('outfmt', 'mp4')
    SETTING['convertUmlauts']    = False #readVal('convertUmlauts', True)
    SETTING['useHWaccel']        = False #readVal('useHWaccel', False)
    SETTING['unknown']           = 'unknown'
    SETTING['languages']         = readSet('filter', 'deu, eng')
    SETTING['languagesSub']      = SETTING['languages']

    SETTING['languages'].add(SETTING['unknown'])

    SETTING['username']          = 'kodi'
    SETTING['password']          = 'Lennyboy2003'


def utc2local(t_str, t_fmt):
    tz_utc = tz.tzutc()
    tz_local = tz.tzlocal()

    try:
        t = datetime.strptime(t_str, t_fmt)
    except TypeError:
        t = datetime(*(time.strptime(t_str, t_fmt)[0:6]))

    t = t.replace(tzinfo=tz_utc)
    t = t.astimezone(tz_local)

    return t.strftime(t_fmt)


def local2mk(t_str, t_fmt):
    return int(time.mktime(time.strptime(t_str, t_fmt)))


def utfy_dict(dic):
    if not sys.version_info.major < 3:
       return dic

    if isinstance(dic,unicode):
        return dic.encode("utf-8")
    elif isinstance(dic,dict):
        for key in dic:
            dic[key] = utfy_dict(dic[key])
        return dic
    elif isinstance(dic,list):
        new_l = []
        for e in dic:
            new_l.append(utfy_dict(e))
        return new_l
    else:
        return dic


#def mixed_decoder(error: UnicodeError) -> (str, int):
#     bs: bytes = error.object[error.start: error.end]
#     return bs.decode("cp1252"), error.start + 1

def mixed_decoder(unicode_error):
    err_str = unicode_error[1]
    err_len = unicode_error.end - unicode_error.start
    next_position = unicode_error.start + err_len
    replacement = err_str[unicode_error.start:unicode_error.end].decode('cp1252')

    if sys.version_info.major < 3:
        return u'%s' % replacement, next_position
    else:
        return '%s' % replacement, next_position

codecs.register_error('mixed', mixed_decoder)


def jsonrpc_request(method, host='localhost', params=None, port=8080, username=None, password=None):
    url     =    'http://{}:{}/jsonrpc'.format(host, port)
    headers =    {'Content-Type': 'application/json'}

    xbmc.log(msg='[{}] Initializing RPC request to host {} with method \'{}\'.'.format(__addon_id__, host, method), level=DEBUG)

    jsondata = {
        'jsonrpc': '2.0',
        'method': method,
        'id': method}

    if params:
        jsondata['params'] = params

    if username and password:
        auth_str = '{}:{}'.format(username, password)
        try:
            base64str = base64.encodestring(auth_str)[:-1]
        except:
            base64str = base64.b64encode(auth_str.encode()).decode()
        headers['Authorization'] = 'Basic {}'.format(base64str)

    try:
        if host in ['localhost', '127.0.0.1']:
            response = xbmc.executeJSONRPC(json.dumps(jsondata))
            if sys.version_info.major < 3:
                data = json.loads(response.decode('utf-8', 'mixed'))
            else:
                data = json.loads(response)
        else:
            response = requests.post(url, data=json.dumps(jsondata), headers=headers)
            if not response.ok:
                xbmc.log(msg='[{}] RPC request to host {} failed with status \'{}\'.'.format(__addon_id__, host, response.status_code), level=INFO)
                return None

            if sys.version_info.major < 3:
                data = json.loads(response.content.decode('utf-8', 'mixed'))
            else:
                data = json.loads(response.text)

        if data['id'] == method and 'result' in data:
            xbmc.log(msg='[{}] RPC request to host {} returns data \'{}\'.'.format(__addon_id__, host, data['result']), level=DEBUG)
            return utfy_dict(data['result'])

    except Exception as e:
        xbmc.log(msg='[{}] RPC request to host {} failed with error \'{}\'.'.format(__addon_id__, host, str(e)), level=INFO)
        pass

    return None


def getChannel(channelid):
    pvrdetails = jsonrpc_request('PVR.GetChannelDetails', params={'channelid': channelid})
    if pvrdetails and 'channeldetails' in pvrdetails:
        if pvrdetails['channeldetails']['channelid'] == channelid:
            return pvrdetails['channeldetails']['label']

    return ''


def getTimers():
    timers = []

    pvrtimers = jsonrpc_request('PVR.GetTimers', params={'properties': ['title', 'starttime', 'endtime', 'state', 'channelid', 'summary', 'directory', 'startmargin', 'endmargin']})
    if pvrtimers and 'timers' in pvrtimers:
        for timer in pvrtimers['timers']:
            t = {
                'id':        timer['timerid'],
                'title':     timer['title'],
                'channel':   getChannel(timer['channelid']),
                'starttime': utc2local(timer['starttime'], SETTING['tmFormat']),
                'endtime':   utc2local(timer['endtime'], SETTING['tmFormat']),
                'state':     timer['state']
                }
            timers.append(t)

    timers = sorted(timers, key=lambda k: k['endtime'])

    return timers


def isRecording(timers, title, channel, starttime, endtime):
    rStart   = local2mk(starttime, SETTING['tmFormat'])
    rEnd     = local2mk(endtime, SETTING['tmFormat'])

    for timer in timers:
        if timer and 'state' in timer:
            if timer['state'] == 'recording':
                tStart = local2mk(timer['starttime'], SETTING['tmFormat'])
                tEnd   = local2mk(timer['endtime'], SETTING['tmFormat'])

                if timer['title'] != title or timer['channel'] != channel:
                    continue

                if rEnd <= tEnd and rEnd >= tStart:
                    return True

    return False


def getClients(port):
    clients = set()

    my_env = os.environ.copy()
    my_env['LC_ALL'] = 'en_EN'

    columns = 4 if platform.system() == 'Windows' else 6

    netstat = subprocess.check_output(['netstat', '-n'], universal_newlines=True, env=my_env)

    for line in netstat.split('\n'):
        items = line.split()
        if len(items) < columns or items[0][:3].lower() != 'tcp' or items[-1].lower() != 'established':
            continue

        remoteAddr, remotePort = items[-2].rsplit(':', 1)
        localAddr, localPort = items[-3].rsplit(':', 1)

        if localPort == str(port):
            clients.add(remoteAddr)

    return clients


def isPlaying(clients, video):
    ActivePlayer = ''

    for client in clients:
        players = jsonrpc_request('Player.GetActivePlayers', host=client, username=SETTING['username'], password=SETTING['password'])
        if players and len(players) > 0 and players[0]['type'] == 'video':
            playerid = players[0]['playerid']
            playeritem = jsonrpc_request('Player.GetItem', host=client, params={'properties': ['title', 'file'], 'playerid': playerid}, username=SETTING['username'], password=SETTING['password'])
            if playeritem and playeritem['item']['type'] != 'channel':
                if video == unquote(playeritem['item']['file']):
                    ActivePlayer = client
                    break

    return ActivePlayer


def scrub(text, convUmlaut=False, convSpecial=True):
    # make output windows-friendly
    umlautDictionary = {
                u'Ä': 'Ae',
                u'Ö': 'Oe',
                u'Ü': 'Ue',
                u'ä': 'ae',
                u'ö': 'oe',
                u'ü': 'ue',
                u'ß': 'ss'
                }

    specialDictionary = {
                u':': ' -',
                u'?': '',
                u'"': '\'',
                u'*': '',
                u'<': '-',
                u'>': '-',
                u'/': ', '
                }

    #try:              # Python 2
    if sys.version_info.major < 3:
        umap = {ord(key):unicode(val) for key, val in umlautDictionary.items()}
        smap = {ord(key):unicode(val) for key, val in specialDictionary.items()}
    #except NameError: # Python 3
    else:
        umap = {ord(key):val for key, val in umlautDictionary.items()}
        smap = {ord(key):val for key, val in specialDictionary.items()}

    if convUmlaut:
        text = text.translate(umap)

    if convSpecial:
        text = text.translate(smap)

    return text


def _scrub(str):
    return scrub(str.lower(), convUmlaut=True, convSpecial=False)


#def getTVHdata(logdir, title, episode, channel, starttime):
#    logfiles = []

#    for path, dirs, files in os.walk(logdir, followlinks=True):
#        logfiles.extend(files)
#        break

#    TVHpath = ''
#    TVHfiles = []

#    for logfile in logfiles:
#        with open(os.path.join(logdir, logfile)) as log:
#            data = json.load(log)

#            if data['title'].values()[0] == title and
#                data['subtitle'].values()[0] and
#                data['channel'] == channel and
#                time.strftime(SETTING['tmFormat'], time.localtime(data['start'])) == starttime:
#                files = [file['filename'] for file in data['files']]

#                TVHpath = os.path.dirname(files[0])
#                TVHfiles = [os.path.basename(file) for file in sorted(files)]

#                break

#    return TVHpath, TVHfiles


def updateVDRrecs(vdrdir):
    VDRrecs = []

    for path, dirs, files in os.walk(vdrdir, followlinks=True):
        if path.endswith('.rec'):
            if not files:
                continue
        if 'info' in files and '00001.ts' in files:
            VDRrec = {
                'title':     '',
                'episode':   '',
                'channel':   '',
                'starttime': '',
                'endtime':   '',
                'genre':     ''
                }
            infofile = open(os.path.join(path, 'info'))
            try:
                lines = infofile.read().split('\n')
                for line in lines:
                    if line[:2] == 'T ':
                        VDRrec['title'] = line[2:].rstrip('\n')
                    if line[:2] == 'S ':
                        VDRrec['episode'] = line[2:].rstrip('\n')
                    if line[:2] == 'C ':
                        VDRrec['channel'] =  line[2:].split(' ', 1)[1].rstrip('\n')
                    if line[:2] == 'E ':
                        start  = int(line[2:].split(' ')[1])
                        length = int(line[2:].split(' ')[2])
                        VDRrec['starttime'] = time.strftime(SETTING['tmFormat'], time.localtime(start))
                        VDRrec['endtime']   = time.strftime(SETTING['tmFormat'], time.localtime(start + length))
                    if line[:2] == 'G ':
                        VDRrec['genre'] = line[2:].split()
                if VDRrec:
                    VDRrec['path'] = path
                    VDRrecs.append(VDRrec)
            except:
                continue
            finally:
                infofile.close()

    return VDRrecs


def matchPVRdata(PVRrecs, title, episode, channel, starttime):
    path  = ''
    files = []

    for rec in PVRrecs:
        #if _scrub(rec['title']) == _scrub(title) and _scrub(rec['episode']) == _scrub(episode) and rec['channel'] == channel and rec['starttime'] == starttime:
        if rec['title'] == title and rec['episode'] == episode and rec['channel'] == channel and rec['starttime'] == starttime:
            path = rec['path']
            if rec['starttime'] and rec['endtime']:
                start = local2mk(rec['starttime'], SETTING['tmFormat'])
                end   = local2mk(rec['endtime'], SETTING['tmFormat'])

                tsfiles = [os.path.join(path, file) for file in sorted(os.listdir(path)) if file.endswith('.ts')]

                # Get Modification date of ts file and cut seconds
                for file in tsfiles:
                    mtime = int(os.path.getmtime(file)/10)*10
                    # Add only files with mtime > start
                    if mtime > start:
                        files.append(file.split(os.path.sep)[-1])
                    # Stop if file was added with with mtime > end
                    if mtime > end:
                        break
            else:
                files = [file for file in sorted(os.listdir(path)) if file.endswith('.ts')]
            break

    return path, files


def getShowDetails(plot):
    showSeason  = 1
    showEpisode = 0

    season = re.search(r'.*([0-9]+)\. Staffel.*', plot)
    if not season:
        season = re.search(r'.*[sS]eason ([0-9]+).*', plot)
    if season:
        showSeason = int(season.group(1))

    episode = re.search(r'.*Folge ([0-9]+).*', plot)
    if not episode:
        episode = re.search(r'.*[eE]pisode ([0-9]+).*', plot)
    if episode:
        showEpisode = int(episode.group(1))

    return showSeason, showEpisode


class Recording():
    def __init__(self, recording):

        for k, v in recording.items():
            setattr(self, k, v)

        self.state = 'archived' if self.isArchived() else ''

        self.CONV_SUCCESS      = 0
        self.ERR_NO_TARGET     = 1
        self.ERR_TARGET_EXISTS = 2
        self.ERR_NO_DESTDIR    = 3
        self.ERR_NO_PVRDATA    = 4
        self.ERR_EXCEPTION     = 5


    def _isState(self, indicator, set):
        if not self.pvrpath: # or not self.pvrfiles:
            return False

        semaphore = os.path.join(self.pvrpath, indicator)

        if set is not None:
            if set:
                if os.path.exists(semaphore):
                    os.utime(semaphore, None)
                else:
                    open(semaphore, 'a').close()
            else:
                if os.path.exists(semaphore):
                    os.remove(semaphore)

        return os.path.exists(semaphore)


    def isScheduled(self, set=None):
        return self._isState('.scheduled', set)


    def isArchived(self, set=None):
        return self._isState('.archived', set)


    def isPlaying(self, clients=None):
        if not clients:
            clients = getClients(SETTING['pvrPort'])

        return isPlaying(clients, self.file)


    def isRecording(self, timers=None):
        if not timers:
            timers = getTimers()

        return isRecording(timers, self.title, self.channel, self.starttime, self.endtime)


    def isShow(self):
        return self.directory != ''


    def _analyze(self, videofile):
        try:
            data = subprocess.check_output([ffprobe_exec, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', videofile,])
            output = json.loads(data)
        except subprocess.CalledProcessError as e:
            output = None

        return output


    def _buildCmd(self):
        files = [os.path.join(self.pvrpath, file) for file in self.pvrfiles]

        if len(self.pvrfiles) == 1:
            input = files[0]
        else:
            input= '|'.join(files)
            input = 'concat:' + input

        data = self._analyze(files[0])

        if not data or 'streams' not in data:
            return ''

        if SETTING['useHWaccel']:
            cmdPre   = [ffmpeg_exec, '-hwaccel', 'auto', '-v', '10', '-i', input]
        else:
            cmdPre   = [ffmpeg_exec, '-v', '10', '-i', input]

        cmdAudio = ['-c:a', 'copy'] if not SETTING['individualStreams'] else []
        cmdVideo = ['-c:v', 'copy']
        cmdSub   = ['-c:s', 'dvdsub'] if SETTING['subtitles'] and not SETTING['individualStreams'] else []

        idxAudio = 0
        idxSub = 0

        for stream in data['streams']:
            type = stream['codec_type']
            codec = stream['codec_name']
            index = int(stream['index'])

            if 'tags' in stream and 'language' in stream['tags']:
                lang = stream['tags']['language']
            else:
                lang = SETTING['unknown']

            if type == 'audio':
                if SETTING['individualStreams']:
                    if SETTING['languages'] and lang not in SETTING['languages']:
                        continue

                    channelLayout = 'n/a'
                    bitRate       = 0
                    sampleRate    = 0

                    if 'channel_layout' in stream:
                        channelLayout = stream['channel_layout']

                    if 'bit_rate' in stream:
                        bitRate = int(float(stream['bit_rate'])/1000)

                    if 'sample_rate' in stream:
                        sampleRate = int(stream['sample_rate'])

                    if not sampleRate:
                        continue

                    cmdPre.extend(['-map', '0:' + str(index)])

                    if SETTING['recodeAudio'] and codec == 'mp2' and channelLayout == 'stereo':
                        cmdAudio.extend(['-c:a:' + str(idxAudio), 'aac', '-ac:a:' + str(idxAudio), '2', '-b:a:' + str(idxAudio)])
                        if bitRate < 160:
                            cmdAudio.append('96k')
                        elif bitRate > 192:
                            cmdAudio.append('192k')
                        else:
                            cmdAudio.append('128k')
                    else:
                        cmdAudio.extend(['-c:a:' + str(idxAudio), 'copy'])

                    cmdAudio.extend(['-metadata:s:a:' + str(idxAudio), 'language=' + lang])

                    idxAudio += 1

            if type == 'subtitle':
                if SETTING['subtitles'] and SETTING['individualStreams']:
                    if SETTING['languagesSub'] and lang not in SETTING['languagesSub']:
                        continue

                    cmdPre.extend(['-map', '0:' + str(index)])

                    cmdSub.extend(['-c:s:' + str(idxSub), 'dvdsub'])
                    cmdSub.extend(['-metadata:s:s:' + str(idxSub), 'language=' + lang])

                    idxSub += 1

            if type == 'video':
                width     = int(stream['width'])
                height    = int(stream['height'])
                # Comment out the follwing 4 lines if they don't work:
                try:
                    frameRate = int(eval(stream['avg_frame_rate']))
                except:
                    continue

                if SETTING['individualStreams']:
                            cmdPre.extend(['-map', '0:' + str(index)])

                #if SETTING['copyVideo']:
                #    cmdVideo = ['-c:v', 'copy']
                #else
                if codec != 'h264' or SETTING['deinterlaceVideo']:
                    cmdVideo = ['-c:v', 'libx264']
                    if SETTING['deinterlaceVideo']:
                        cmdVideo.extend(['-filter:v', 'yadif'])

                if SETTING['forceSD'] and width > 720:
                    cmdVideo.extend(['-vf', 'scale=720:576'])

                if SETTING['col2grey']:
                    if '-vf' in cmdVideo:
                        cmdVideo[cmdVideo.index('-vf') + 1] += ',hue=s=0'
                    else:
                        cmdVideo.extend('-vf', 'hue=s=0')

        # insert canvas_size for subtitle before inputfile only if cmdSub is not [] (meaning subtitles
        # is True and at least one matching subtitle was found), and after we learned actual video size
        if cmdSub:
            if SETTING['useHWaccel']:
            #if '-hwaccel' in cmdPre:
                cmdPre[5:5] = ['-canvas_size', str(width - 16) + 'x' + str(height)]
            else:
                #cmdPre[3:3] = ['-canvas_size', '704x576']
                cmdPre[3:3] = ['-canvas_size', str(width - 16) + 'x' + str(height)]


        cmd = cmdPre + cmdAudio + cmdVideo + cmdSub

        return cmd


    def _makeDestdir(self):
        dirname = ''

        if self.isShow() and SETTING['groupShows']:
            dirname = scrub(self.directory, convUmlaut=SETTING['convertUmlauts']) #--> makeLegalFilename?
        elif SETTING['createTitle']:
            dirname = scrub(self.title, convUmlaut=SETTING['convertUmlauts']) #--> makeLegalFilename?

        if dirname:
            outdir = os.path.join(SETTING['dstDir'], dirname)
        else:
            outdir = SETTING['dstDir']
        if outdir[-1] != os.sep:
            outdir += os.sep

        # validatePath?
        outdir = validatePath(outdir)
        # Debug:
        xbmc.log(msg='[{}] Destination Directory: \'{}\''.format(__addon_id__, outdir), level=INFO)

        if not xbmcvfs.exists(outdir.encode(SETTING['dstEncoding'])):
            xbmcvfs.mkdir(outdir.encode(SETTING['dstEncoding']))

        return outdir if xbmcvfs.exists(outdir.encode(SETTING['dstEncoding'])) else None


    def _constructName(self):
        name = self.title

        if SETTING['addEpisode'] and self.episode > 0:
            name = '{} {}x{:02d}'.format(name, self.season, self.episode)
        if self.title2:
            name = '{} - {}'.format(name, self.title2)
        if SETTING['addChannel'] and self.channel:
            name = '{}_{}'.format(name, self.channel)
        if SETTING['addStarttime'] and self.starttime:
            name = name + '_' + self.starttime
            name = '{}_{}'.format(name, self.starttime)

        return scrub(name, convUmlaut=SETTING['convertUmlauts']) #--> makeLegalFilename?


    def convert(self, event):
        if self.isPlaying() or self.isRecording():
            return

        thread = threading.Thread(target=self._convert, args=(event,))
        thread.start()

        return thread


    def _convert(self, event):
        outPath = None
        tmpPath = None

        status = -1

        if not lock.acquire(False):
            return

        try:
            if self.title2:
                title = '{} ({})'.format(self.title, self.title2).strip()
            else:
                title = self.title
            xbmc.log(msg='[{}] Archiving process started for title \'{}\''.format(__addon_id__, title), level=INFO)

            if SETTING['notifySuccess'] or SETTING['notifyFailure']:
                xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30043), title))

            if not self.pvrpath or not self.pvrfiles:
                status = self.ERR_NO_PVRDATA
                self.state = 'missing PVR data'
                return
            else:
                self.state = 'archiving'
                status = ''

            destDir = self._makeDestdir()
            if not destDir:
                status = self.ERR_NO_DESTDIR
                self.state = 'destination not accessible'
                return

            outFile = self._constructName() + SETTING['outputFmt']

            outPath = os.path.join(destDir, outFile)
            outPath = validatePath(outPath)

            if xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                if SETTING['overwrite']:
                    xbmcvfs.delete(outPath.encode(SETTING['dstEncoding']))
                    self.isArchived(set=False)
                else:
                    status = self.ERR_TARGET_EXISTS
                    self.state = 'archive already exists'
                    return

            tmpPath = os.path.join(SETTING['tmpDir'], outFile)

            if os.path.exists(tmpPath): #--> xbmcvfs.exists?
                os.remove(tmpPath) #--> xbmcvfs.delete?

            cmd = self._buildCmd()

            # Test with os.path.exists if destDir is locally accessible
            cmd.append(outPath if os.path.exists(destDir) else tmpPath )

            # Debug:
            #xbmc.log(msg='[{}] Archiving process started with cmd \'{}\''.format(__addon_id__, ' '.join(cmd)), level=INFO)

            with subprocess.Popen(cmd) as proc:
                while proc.poll() is None:
                    if not self.isScheduled() or event.is_set():
                        proc.kill()
                    time.sleep(2)

            if event.is_set():
                raise Exception('archiving cancelled on exit')

            if not self.isScheduled():
                raise Exception('archiving cancelled by user')

            if proc.returncode != 0:
                raise Exception('transcoding failed')

            # Debug:
            xbmc.log(msg='[{}] Transcoding process completed. Copying file to \'{}\''.format(__addon_id__, outPath), level=INFO)

            if os.path.exists(tmpPath) and not xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])): #--> xbmcvfs.exsits?
                xbmcvfs.copy(tmpPath.encode(SETTING['locEncoding']), outPath.encode(SETTING['dstEncoding']))

            if xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                status = self.CONV_SUCCESS
                self.state = 'archived'

                self.isArchived(set=True)

                if SETTING['delSource']:
                    self._cleanupSource()
            else:
                status = self.ERR_NO_TARGET
                self.state = 'couldn\'t create archive'

        except Exception as e:
            status = self.ERR_EXCEPTION
            self.state = str(e)

            if outPath and xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                # Debug:
                xbmc.log(msg='[{}] Removing target file \'{}\''.format(__addon_id__, outPath), level=INFO)

                xbmcvfs.delete(outPath.encode(SETTING['dstEncoding']))
                if not xbmcvfs.listdir(destDir.encode(SETTING['dstEncoding'])):
                    xbmcvfs.rmdir(destDir.encode(SETTING['dstEncoding']))

        finally:
            if status != self.CONV_SUCCESS:
                if SETTING['notifyFailure']:
                    xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30041), title))
                xbmc.log(msg='[{}] Archiving process for title \'{}\' aborted with status \'{}\''.format(__addon_id__, title, self.state), level=INFO)
            else:
                if SETTING['notifySuccess']:
                    xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30040), title))
                xbmc.log(msg='[{}] Archiving process for title \'{}\' completed successfully'.format(__addon_id__, title), level=INFO)

            self.isScheduled(set=False)

            if tmpPath and os.path.exists(tmpPath): #--> xbmcvfs.exists?
                # Debug:
                xbmc.log(msg='[{}] Removing temporary file \'{}\''.format(__addon_id__, tmpPath), level=INFO)

                os.remove(tmpPath) #--> xbmcvfs.delete?

            lock.release()


    def _cleanupSource(self):
        home = os.path.realpath(self.pvrpath)

        if os.access(home, os.W_OK):
            try:
                for file in os.listdir(home):
                    os.remove(os.path.join(home, file))
                if not os.listdir(home):
                    os.rmdir(home)
                if not os.listdir(os.path.dirname(home)) and os.access(os.path.dirname(home), os.W_OK):
                    os.rmdir(os.path.dirname(home))
                return True

            except OSError:
                return False


class MyMonitor( xbmc.Monitor ):
    def __init__( self, *args, **kwargs ):
        xbmc.Monitor.__init__( self )

    def onSettingsChanged( self ):
        loadSettings()


def addRecording(id, details, PVRrecs):
    if details['directory']:
        season, episode = getShowDetails(details['plot'])
    r = {
        'id':          id,
        'title':       details['title'],
        'title2':      details['plotoutline'],
        'plot':        details['plot'],
        'channel':     details['channel'],
        'starttime':   utc2local(details['starttime'], SETTING['tmFormat']),
        'endtime':     utc2local(details['endtime'], SETTING['tmFormat']),
        'directory':   details['directory'][1:],
        'season':      1 if not details['directory'] else season,
        'episode':     0 if not details['directory'] else episode,
        'file':        unquote(details['file'])
        }
    r['pvrpath'], r['pvrfiles'] = matchPVRdata(PVRrecs, r['title'], r['title2'], r['channel'], r['starttime'])

    # Debug:
    #xbmc.log(msg='[{}] Add recording for title \'{}\', path: {}, files: {}'.format(__addon_id__, r['title'], r['pvrpath'], ', '.join(r['pvrfiles'])), level=INFO)

    rec  = Recording(r)

    return rec


def updateRecordings(recList, sort=None, convertNew=False): # --> getRecordings()
    idList = [rec.id for rec in recList]

    VDRrecs = updateVDRrecs(SETTING['pvrDir'])

    result = jsonrpc_request('PVR.GetRecordings', params={'properties': ['isdeleted']})
    if result and 'recordings' in result:
        for recording in result['recordings']:
            if recording['isdeleted']:
                continue
            if recording['recordingid'] not in idList:
                res = jsonrpc_request('PVR.GetRecordingDetails', params={'properties': ['title', 'plotoutline', 'plot', 'channel', 'starttime', 'endtime', 'directory', 'file'], 'recordingid': recording['recordingid']})
                if res and 'recordingdetails' in res:
                    details = res['recordingdetails']
                    rec = addRecording(recording['recordingid'], details, VDRrecs)
                    if convertNew and not rec.isArchived():
                        rec.isScheduled(set=True)
                    recList.append(rec)
            else:
                idList.remove(recording['recordingid'])

    for id in idList:
        for rec in recList:
            if id == rec.id:
                recList.remove(rec)

    if sort is not None:
        if sort == 0:
            # sort by date (ascending)
            recList.sort(key=lambda r: r.starttime)
        if sort == 1:
            # sort by date (descending)
            recList.sort(key=lambda r: r.starttime, reverse=True)
        if sort == 2:
            # sort by title (case-insensitive, ascending)
            recList.sort(key=lambda r: r.title.lower())
        if sort == 3:
            # sort by title (case-insensitive, descending)
            recList.sort(key=lambda r: r.title.lower(), reverse=True)

    return recList


if __name__ == '__main__':
    lock = threading.Lock()
    stopEvent = threading.Event()
    thread = None

    monitor = MyMonitor()
    xbmc.log(msg='[{}] Addon started.'.format(__addon_id__), level=INFO)
    loadSettings()

    os.nice(19)

    while not monitor.abortRequested():
        #KODIrecs = updateRecordings(KODIrecs, sort=SETTING['recSort'], convertNew=SETTING['convertNew'])
        updateRecordings(KODIrecs, sort=SETTING['recSort'], convertNew=SETTING['convertNew'])

        for rec in KODIrecs:
            if rec.isScheduled():
                thread = rec.convert(stopEvent)
                break

        if monitor.waitForAbort(float(SETTING['sleepTime'])):
            xbmc.log(msg='[{}] Addon abort requested.'.format(__addon_id__), level=INFO)

            stopEvent.set()
            thread.join()

            break
else:
    loadSettings()
