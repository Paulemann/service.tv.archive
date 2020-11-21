#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import time
import xbmc
import xbmcgui
import xbmcaddon
#import pyxbmct
import pyxbmct.addonwindow as pyxbmct

from datetime import datetime
from service import getClients, getTimers, updateRecordings


__addon__          = xbmcaddon.Addon()
__setting__        = __addon__.getSetting
__addon_id__       = __addon__.getAddonInfo('id')
__addon_path__     = __addon__.getAddonInfo('path')
__checked_icon__   = os.path.join(__addon_path__, 'checked.png') # Don't decode _path to utf-8!!!
__unchecked_icon__ = os.path.join(__addon_path__, 'unchecked.png') # Don't decode _path to utf-8!!!
__localize__       = __addon__.getLocalizedString


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
        self.setControls()
        self.listing.addItems(items or [])
        if (self.listing.size() > 0):
            for index in range(self.listing.size()):
                if index in self.selected:
                    self.listing.getListItem(index).setIconImage(__checked_icon__)
                    self.listing.getListItem(index).setLabel2("checked")
                else:
                    self.listing.getListItem(index).setIconImage(__unchecked_icon__)
                    self.listing.getListItem(index).setLabel2("unchecked")
        else:
            self.listing.addItems([__localize__(30053)])
        self.placeControls()
        self.connectControls()
        self.setNavigation()

    def setControls(self):
        self.listing = pyxbmct.List(_imageWidth=15)
        self.placeControl(self.listing, 0, 0, rowspan=9, columnspan=10)
        self.okButton = pyxbmct.Button(__localize__(30051))
        self.cancelButton = pyxbmct.Button(__localize__(30052))

    def connectControls(self):
        self.connect(self.listing, self.toggleSelect)
        self.connect(self.okButton, self.ok)
        self.connect(self.cancelButton, self.close)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

    def placeControls(self):
        if (self.listing.getListItem(0).getLabel2()):
            self.placeControl(self.okButton, 9, 3, columnspan=2)
            self.placeControl(self.cancelButton, 9, 5, columnspan=2)
        else:
            self.placeControl(self.cancelButton, 9, 4, columnspan=2)

    def setNavigation(self):
        if (self.listing.getListItem(0).getLabel2()):
            self.listing.controlUp(self.okButton)
            self.listing.controlDown(self.okButton)
            self.okButton.setNavigation(self.listing, self.listing, self.cancelButton, self.cancelButton)
            self.cancelButton.setNavigation(self.listing, self.listing, self.okButton, self.okButton)
            self.setFocus(self.listing)
        else:
            self.setFocus(self.cancelButton)

    def toggleSelect(self):
        list_item = self.listing.getSelectedItem()
        if list_item.getLabel2() == "checked":
            list_item.setIconImage(__unchecked_icon__)
            list_item.setLabel2("unchecked")
        else:
            list_item.setIconImage(__checked_icon__)
            list_item.setLabel2("checked")

    def ok(self):
        self.selected = [index for index in range(self.listing.size())
                                if self.listing.getListItem(index).getLabel2() == "checked"]
        super(MultiChoiceDialog, self).close()

    def close(self):
        self.selected = None
        super(MultiChoiceDialog, self).close()


if __name__ == '__main__':
    WIN = xbmcgui.Window(10000)

    if WIN.getProperty(__addon_id__ + '.running') == 'True':
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
            item = '{} {}: \"{} ({})\" - {}'.format(prefix, convertDate(rec.starttime, tmFormat, '%d.%m.%Y %H:%M'), rec.title.encode(locEncoding), rec.title2.encode(locEncoding), rec.channel.encode(locEncoding))
        else:
            item = '{} {}: \"{}\" - {}'.format(prefix, convertDate(rec.starttime, tmFormat, '%d.%m.%Y %H:%M'), rec.title.encode(locEncoding), rec.channel.encode(locEncoding))
        items.append(item)

        if rec.isScheduled():
            preSelect.append(index)

    dialog = MultiChoiceDialog(__localize__(30050), items, preSelect)
    dialog.doModal()

    if dialog.selected is not None:
        unselect = [index for index in preSelect if index not in dialog.selected]
        for index in unselect:
            recs[index].isScheduled(set=False)

        for index in dialog.selected:
            recs[index].isScheduled(set=True)

    dialog.selected = None
    del dialog

    WIN.clearProperty(__addon_id__ + '.running')
    sys.exit(0)
