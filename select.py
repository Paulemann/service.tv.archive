#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import time
import xbmc
import xbmcgui
import xbmcaddon
import pyxbmct.addonwindow as pyxbmct

from datetime import datetime
from service import getClients, getTimers, updateRecordings

if sys.version_info.major < 3:
    INFO = xbmc.LOGNOTICE
    from xbmc import translatePath
else:
    INFO = xbmc.LOGINFO
    from xbmcvfs import translatePath

__addon__          = xbmcaddon.Addon()
__setting__        = __addon__.getSetting
__addon_id__       = __addon__.getAddonInfo('id')
__addon_path__     = __addon__.getAddonInfo('path')
__localize__       = __addon__.getLocalizedString
__checked_icon__   = os.path.join(__addon_path__, 'resources', 'media', 'checked.png')
__unchecked_icon__ = os.path.join(__addon_path__, 'resources', 'media', 'unchecked.png')
__list_bg__        = os.path.join(__addon_path__, 'resources', 'media', 'background.png')
__texture_nf__     = os.path.join(__addon_path__, 'resources', 'media', 'texture-nf.png')

# Enable or disable Estuary-based design explicitly
pyxbmct.skin.estuary = True

locEncoding          = sys.getfilesystemencoding()
tmFormat             = '%Y-%m-%d %H:%M:%S'


def convertDate(t_str, t_fmt_in, t_fmt_out):
    try:
        t = datetime.strptime(t_str, t_fmt_in)
    except TypeError:
        t = datetime(*(time.strptime(t_str, t_fmt_in)[0:6]))

    return t.strftime(t_fmt_out)


class MultiChoiceDialog(pyxbmct.AddonDialogWindow):
    def __init__(self, title="", items=None, selected=None):
        super(MultiChoiceDialog, self).__init__(title)

        self.setGeometry(800, 600, 10, 10)

        self.selected = selected or []
        self.items = items or []

        self.setControls()
        self.placeControls()
        self.connectControls()

        self.listing.addItems(self.items)

        if (self.items):
            for index in range(self.listing.size()):
                listitem = self.listing.getListItem(index)
                try:
                    listitem.setIconImage(__checked_icon if index in self.selected else __unchecked_icon__)
                except:
                    listitem.setArt({'icon': __checked_icon__ if index in self.selected else __unchecked_icon__})
                listitem.setProperty('selected', 'true' if index in self.selected else 'false')
        else:
            self.listing.addItems([__localize__(30053)])
            self.listing.getListItem(0).setProperty('selected', '')

        self.setNavigation()

    def setControls(self):
        self.list_bg = pyxbmct.Image(__list_bg__)
        self.listing = pyxbmct.List(_imageWidth=15, _itemTextYOffset=-1, _alignmentY=pyxbmct.ALIGN_CENTER_Y, _space=3, buttonTexture=__texture_nf__)
        self.okButton = pyxbmct.Button(__localize__(30051))
        self.cancelButton = pyxbmct.Button(__localize__(30052))

    def placeControls(self):
        self.placeControl(self.list_bg, 0, 0, rowspan=9, columnspan=10)
        self.placeControl(self.listing, 0, 0, rowspan=10, columnspan=10)

        if self.items:
            self.placeControl(self.okButton, 9, 3, columnspan=2)
            self.placeControl(self.cancelButton, 9, 5, columnspan=2)
        else:
            self.placeControl(self.cancelButton, 9, 4, columnspan=2)

    def connectControls(self):
        self.connect(self.listing, self.toggleSelect)
        self.connect(self.okButton, self.ok)
        self.connect(self.cancelButton, self.close)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

    def setNavigation(self):
        if self.items:
            self.listing.controlUp(self.okButton)
            self.listing.controlDown(self.okButton)
            self.okButton.setNavigation(self.listing, self.listing, self.cancelButton, self.cancelButton)
            self.cancelButton.setNavigation(self.listing, self.listing, self.okButton, self.okButton)
            self.setFocus(self.listing)
        else:
            self.setFocus(self.cancelButton)

    def toggleSelect(self):
        listitem = self.listing.getSelectedItem()
        listitem.setProperty('selected', 'false' if listitem.getProperty('selected') == 'true' else 'true')
        try:
            listitem.setIconImage(__checked_icon__ if listitem.getProperty('selected') else __unchecked_icon__)
        except:
            listitem.setArt({'icon': __checked_icon__ if listitem.getProperty('selected') == 'true'  else __unchecked_icon__})

    def ok(self):
        self.selected = [index for index in range(self.listing.size())
                                if self.listing.getListItem(index).getProperty('selected') == 'true']
        super(MultiChoiceDialog, self).close()

    def close(self):
        super(MultiChoiceDialog, self).close()


if __name__ == '__main__':
    WIN = xbmcgui.Window(10000)

    if WIN.getProperty(__addon_id__ + '.running') == 'True':
        xbmc.log(msg='[{}] Previous instance not properly terminated. Restart kodi.'.format(__addon_id__), level=INFO)
        sys.exit(1)
    else:
        WIN.setProperty(__addon_id__ + '.running' , 'True')

    try:
        recSort = int(__setting__('recsort'))
        pvrPort = int(__setting__('pvrport'))
    except:
        recSort = 0
        pvrPort = 34890

    timers  = getTimers()
    #clients = getClients(pvrPort)

    recs = []
    updateRecordings(recs, sort=recSort)

    items = []
    preSelect = []

    for index, rec in enumerate(recs):
        if rec.isRecording(timers=timers):
            prefix = 'T'
        #elif rec.isPlaying(clients=clients):
        #    prefix = 'P'
        elif rec.isArchived():
            prefix = 'A'
        else:
            prefix = '  '
        if rec.title2:
            item = '{} {}: \"{} ({})\" - {}'.format(prefix, convertDate(rec.starttime, tmFormat, '%d.%m.%Y %H:%M'), rec.title, rec.title2, rec.channel)
        else:
            item = '{} {}: \"{}\" - {}'.format(prefix, convertDate(rec.starttime, tmFormat, '%d.%m.%Y %H:%M'), rec.title, rec.channel)
        items.append(item)

        if rec.isScheduled():
            preSelect.append(index)

    dialog = MultiChoiceDialog(__localize__(30050), items, preSelect)
    dialog.doModal()

    if set(dialog.selected) != set(preSelect):
        unselect = [index for index in preSelect if index not in dialog.selected]
        for index in unselect:
            xbmc.log(msg='[{}] Scheduled archiving of title \'{}\' was cancelled.'.format(__addon_id__, recs[index].title), level=INFO)
            recs[index].isScheduled(set=False)

        select = [index for index in dialog.selected if index not in preSelect]
        for index in select:
            xbmc.log(msg='[{}] Title \'{}\' has been selected for archiving'.format(__addon_id__, recs[index].title), level=INFO)
            recs[index].isScheduled(set=True)

    del dialog

    WIN.clearProperty(__addon_id__ + '.running')

    sys.exit(0)
