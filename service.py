#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import urllib2
import codecs
import subprocess
import time
import threading
import platform
import _strptime

from contextlib import closing
from datetime import datetime, tzinfo, timedelta
from dateutil import tz

import xbmc
import xbmcaddon
import xbmcvfs


Recs    = []
SETTING = {}

__addon__    = xbmcaddon.Addon()
__setting__  = __addon__.getSetting
__addon_id__ = __addon__.getAddonInfo('id')
__localize__ = __addon__.getLocalizedString
__profile__  = __addon__.getAddonInfo('profile')


ffmpeg_exec      = 'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg'
ffprobe_exec     = 'ffprobe.exe' if platform.system() == 'Windows' else 'ffprobe'


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
    SETTING['tmpDir']            = xbmc.translatePath(__profile__).decode(SETTING['locEncoding'])
    SETTING['dstDir']            = readVal('destdir', '/home/kodi/Videos').decode(SETTING['dstEncoding'])
    SETTING['pvrPort']           = readVal('pvrport', 34890)
    SETTING['pvrDir']            = readVal('recdir', '/home/kodi/Aufnahmen').decode(SETTING['locEncoding'])
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
    SETTING['unknown']           = 'unknown'
    SETTING['languages']         = readSet('filter', 'deu, eng')
    SETTING['languagesSub']      = SETTING['languages']

    SETTING['languages'].add(SETTING['unknown'])


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


def mixedDecoder(unicode_error):
    err_str = unicode_error[1]
    err_len = unicode_error.end - unicode_error.start
    next_position = unicode_error.start + err_len
    replacement = err_str[unicode_error.start:unicode_error.end].decode('cp1252')

    return u'%s' % replacement, next_position


codecs.register_error('mixed', mixedDecoder)


def jsonRequest(method, params=None, host='localhost', port=8080, username=None, password=None):
    # e.g. KodiJRPC_Get("PVR.GetProperties", {"properties": ["recording"]})

    url = 'http://{}:{}/jsonrpc'.format(host, port)
    header = {'Content-Type': 'application/json'}

    jsondata = {
        'jsonrpc': '2.0',
        'method': method,
        'id': method}

    if params:
        jsondata['params'] = params

    if username and password:
        base64str = base64.encodestring('{}:{}'.format(username, password))[:-1]
        header['Authorization'] = 'Basic {}'.format(base64str)

    try:
        if host == 'localhost':
            response = xbmc.executeJSONRPC(json.dumps(jsondata))
            data = json.loads(response.decode(SETTING['locEncoding'], 'mixed'))

            if data['id'] == method and 'result' in data:
                return data['result']
        else:
            request = urllib2.Request(url, json.dumps(jsondata), header)
            with closing(urllib2.urlopen(request)) as response:
                data = json.loads(response.read().decode(SETTING['locEncoding'], 'mixed'))

                if data['id'] == method and 'result' in data:
                    return data['result']
    except:
        pass

    return False


def getChannel(channelid):
    pvrdetails = jsonRequest('PVR.GetChannelDetails', params={'channelid': channelid})
    if pvrdetails and 'channeldetails' in pvrdetails:
        if pvrdetails['channeldetails']['channelid'] == channelid:
            return pvrdetails['channeldetails']['label']

    return ''


def getTimers():
    timers = []

    pvrtimers = jsonRequest('PVR.GetTimers', params={'properties': ['title', 'starttime', 'endtime', 'state', 'channelid', 'summary', 'directory', 'startmargin', 'endmargin']})
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
                #if  tStart <= rStart and tEnd >= rEnd:
                    return True

    return False


def getClients(port):
    clients = set()

    my_env = os.environ.copy()
    my_env['LC_ALL'] = 'en_EN'

    columns = 4 if platform.system() == 'Windows' else 6

    #netstat = subprocess.check_output(['netstat', '-t', '-n'], universal_newlines=True, env=my_env)
    netstat = subprocess.check_output(['netstat', '-n'], universal_newlines=True, env=my_env)

    #for line in netstat.split('\n')[2:]:
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
        players = jsonRequest('Player.GetActivePlayers', host=client)
        if players and len(players) > 0 and players[0]['type'] == 'video':
            playerid = players[0]['playerid']
            playeritem = jsonRequest('Player.GetItem', params={'properties': ['title', 'file'], 'playerid': playerid}, host=client)
            if playeritem and playeritem['item']['type'] != 'channel':
                if video == urllib2.unquote(playeritem['item']['file']):
                    ActivePlayer = client
                    break

    return ActivePlayer


def conv(str):
    s = str.lower()
    s = s.replace(u'ä', 'ae')
    s = s.replace(u'ü', 'ue')
    s = s.replace(u'ö', 'oe')
    s = s.replace(u'ß', 'ss')

    return s


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


def getVDRdata(vdrdir, title, episode, channel, starttime):
    VDRpath  = ''
    VDRfiles = []

    for path, dirs, files in os.walk(vdrdir, followlinks=True):
        if path.endswith('.rec'):
            if not files:
                continue
        if 'info' in files and '00001.ts' in files:
            VDRtitle = VDRepisode = VDRchannel = VDRstarttime = VDRendtime = VDRgenre = ''
            with codecs.open(os.path.join(path, 'info'), 'r', encoding=SETTING['locEncoding']) as f:
                for line in f.readlines():
                    if line[:2] == 'T ':
                        VDRtitle = line[2:].rstrip('\n')
                    if line[:2] == 'S ':
                        VDRepisode = line[2:].rstrip('\n')
                    if line[:2] == 'C ':
                        VDRchannel =  line[2:].split(' ', 1)[1].rstrip('\n')
                    if line[:2] == 'E ':
                        start  = int(line[2:].split(' ')[1])
                        length = int(line[2:].split(' ')[2])
                        VDRstarttime = time.strftime(SETTING['tmFormat'], time.localtime(start))
                        VDRendtime   = time.strftime(SETTING['tmFormat'], time.localtime(start + length))
                    if line[:2] == 'G ':
                        VDRgenre = line[2:].split()
            if conv(VDRtitle) == conv(title) and conv(VDRepisode) == conv(episode) and VDRchannel == channel and VDRstarttime == starttime:
                VDRpath = path
                if VDRstarttime and VDRendtime:
                    start = local2mk(VDRstarttime, SETTING['tmFormat'])
                    end   = local2mk(VDRendtime, SETTING['tmFormat'])

                    tsfiles = [os.path.join(path, file) for file in sorted(files) if file.endswith('.ts')]
                    # Get Modification date of ts file and cut seconds
                    #   date = int(os.path.getmtime(file)/10)*10
                    #   mtime = time.strftime(SETTING['tmFormat'], time.localtime(date))
                    # Add only files with mtime > start
                    # Stop if file with mtime > end was added
                    for file in tsfiles:
                        mtime = int(os.path.getmtime(file)/10)*10
                        if mtime > start:
                            VDRfiles.append(file.split(os.path.sep)[-1])
                        if mtime > end:
                            break
                else:
                    VDRfiles = [file for file in sorted(files) if file.endswith('.ts')]
                break

    return VDRpath, VDRfiles


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
    def __init__(self, recording, getPVRdata):

        for k, v in recording.items():
            setattr(self, k, v)

        self.pvrpath, self.pvrfiles = getPVRdata(SETTING['pvrDir'], self.title, self.title2, self.channel, self.starttime)

        self.state = 'archived' if self.isArchived() else ''

        self.CONV_SUCCESS   = 0
        self.CONV_FAILED    = 1
        self.ERR_FILE_EXIST = 2
        self.ERR_NO_DESTDIR = 3
        self.ERR_NO_PVRDATA = 4


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
            output = json.loads(data.decode(SETTING['locEncoding']))
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
                lang = stream['tags']['language'] #.encode(SETTING['locEncoding']) ?
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
                # Put the follwing 4 lines with in comment if they don't work:
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
            #cmdPre[3:3] = ['-canvas_size', '704x576']
            cmdPre[3:3] = ['-canvas_size', str(width - 16) + 'x' + str(height)]

        cmd = cmdPre + cmdAudio + cmdVideo + cmdSub

        return cmd


    def _makeDestdir(self):
        dirname = ''

        if self.isShow() and SETTING['groupShows']:
            dirname = self._friendly(self.directory)
        elif SETTING['createTitle']:
            dirname = self._friendly(self.title)

        if dirname:
            outdir = os.path.join(SETTING['dstDir'], dirname)
            if not xbmcvfs.exists(outdir.encode(SETTING['dstEncoding'])):
                xbmcvfs.mkdir(outdir.encode(SETTING['dstEncoding']))
        else:
            outdir = SETTING['dstDir']

        return outdir if xbmcvfs.exists(outdir.encode(SETTING['dstEncoding'])) else None


    def _friendly(self, text):
        # make output windows-friendly
        return text.replace(':', ' -').replace('?', '').replace('"', '\'').replace('*', '').replace('<', '-').replace('>', '-').replace('/', ', ')


    def _constructName(self):
        name = self.title

        if SETTING['addEpisode'] and self.episode > 0:
            name = name + ' ' + format(self.season) + 'x' + format(self.episode, '02d')
        if self.title2:
            name = name + ' - ' + self.title2
        if SETTING['addChannel'] and self.channel:
            name = name + '_' + self.channel
        if SETTING['addStarttime'] and self.starttime:
            name = name + '_' + self.starttime

        return self._friendly(name)


    def convert(self):
        if self.isPlaying() or self.isRecording(): # or not self.isScheduled():
            return

        t = threading.Thread(target=self._convert)
        #threads.append(t)
        #t.daemon = True
        t.start()


    def _convert(self):
        outPath = None
        tmpPath = None

        if not lock.acquire(False):
            return

        try:
            if self.title2:
                title = '{} ({})'.format(self.title.encode(SETTING['locEncoding']), self.title2.encode(SETTING['locEncoding'])).strip()
            else:
                title = self.title.encode(SETTING['locEncoding'])
            xbmc.log(msg='[{}] Archive process started for title \'{}\''.format(__addon_id__, title), level=xbmc.LOGNOTICE)

            if SETTING['notifySuccess'] or SETTING['notifyFailure']:
                xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30043), title))

            if not self.pvrpath or not self.pvrfiles:
                status = self.ERR_NO_PVRDATA
                return
            else:
                self.state = 'archiving'
                status = ''

            destDir = self._makeDestdir()
            if not destDir:
                status = self.ERR_NO_DESTDIR
                return

            outFile = self._constructName() + SETTING['outputFmt']
            outPath = os.path.join(destDir, outFile)

            if xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                if SETTING['overwrite']:
                    xbmcvfs.delete(outPath.encode(SETTING['dstEncoding']))
                    self.isArchived(set=False)
                else:
                    status = self.ERR_FILE_EXIST
                    return

            tmpPath = os.path.join(SETTING['tmpDir'], outFile)
            if os.path.exists(tmpPath):
                os.remove(tmpPath)

            cmd = self._buildCmd()
            cmd.append(outPath if os.path.exists(destDir) else tmpPath )

            subprocess.check_call(cmd, preexec_fn=lambda: os.nice(19))

            if os.path.exists(tmpPath) and not xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                xbmcvfs.copy(tmpPath.encode(SETTING['locEncoding']), outPath.encode(SETTING['dstEncoding']))

            if xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                if SETTING['notifySuccess']:
                    xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30040), title))

                self.isArchived(set=True)

                status = self.CONV_SUCCESS

                if SETTING['delSource']:
                    self._cleanupSource()
            else:
               status = self.CONV_FAILED

        except Exception as e:
            xbmc.log(msg='[{}] Archive process aborted with exception \'{}\''.format(__addon_id__, e), level=xbmc.LOGERROR)
            status = self.CONV_FAILED

            if SETTING['notifyFailure']:
                xbmc.executebuiltin('Notification({},\'{}\')'.format(__localize__(30041), title))

            if outPath and xbmcvfs.exists(outPath.encode(SETTING['dstEncoding'])):
                xbmcvfs.delete(outPath.encode(SETTING['dstEncoding']))
                if not xbmcvfs.listdir(destDir.encode(SETTING['dstEncoding'])):
                    xbmcvfs.rmdir(destDir.encode(SETTING['dstEncoding']))

        finally:
            self.isScheduled(set=False)

            if tmpPath and os.path.exists(tmpPath):
                os.remove(tmpPath)

            if status == self.CONV_SUCCESS:
                self.state = 'archived'
            elif status == self.CONV_FAILED:
                self.state = 'archiving failed'
            elif status == self.ERR_FILE_EXIST:
                self.state = 'archive exists'
            elif status == self.ERR_NO_DESTDIR:
                self.state = 'no destination'
            elif status == self.ERR_NO_PVRDATA:
                self.state = 'missing PVR data'
            xbmc.log(msg='[{}] Archive process finished with status \'{}\''.format(__addon_id__, self.state), level=xbmc.LOGNOTICE)

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


def addRecording(id, details):
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
        'file':        urllib2.unquote(details['file'])
        }
    rec = Recording(r, getVDRdata)

    return rec


def updateRecordings(recList, sort=None, convertNew=False): # --> getRecordings()
    idList = [rec.id for rec in recList]

    result = jsonRequest('PVR.GetRecordings', params={'properties': ['isdeleted']})
    if result and 'recordings' in result:
        for recording in result['recordings']:
            if recording['isdeleted']:
                continue
            if recording['recordingid'] not in idList:
                res = jsonRequest('PVR.GetRecordingDetails', params={'properties': ['title', 'plotoutline', 'plot', 'channel', 'starttime', 'endtime', 'directory', 'file'], 'recordingid': recording['recordingid']})
                if res and 'recordingdetails' in res:
                    details = res['recordingdetails']
                    rec = addRecording(recording['recordingid'], details)
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


if __name__ == '__main__':
    lock = threading.Lock()
    monitor = MyMonitor()
    xbmc.log(msg='[{}] Addon started.'.format(__addon_id__), level=xbmc.LOGNOTICE)
    loadSettings()

    #Recs = []
    os.nice(19)

    while not monitor.abortRequested():
        updateRecordings(Recs, sort=SETTING['recSort'], convertNew=SETTING['convertNew'])
        for rec in Recs:
            if rec.isScheduled():
                rec.convert()
                break

        if monitor.waitForAbort(float(SETTING['sleepTime'])):
            xbmc.log(msg='[{}] Addon abort requested.'.format(__addon_id__), level=xbmc.LOGNOTICE)
            break
else:
    loadSettings()
