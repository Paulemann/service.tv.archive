## service.tv.archive

Kodi addon to archive TV recordings by converting them to ffmpeg-supported video formats.

This addon converts locally accessible TV recordings (VDR ts and info files) to other, ffmpeg-supported, video formats and stores them at the configured destination (incl. NAS). Via the addon settings you can set various processing options, e.g. HD to SD conversion or which audio and subtitle languages to include. You can also specify how the output name is composed, e.g. to include channel name and recording date.

The addon is installed as a service which periodically monitors a given source folder and, optionally, converts all newly added video items - if not currently recorded or played back.

The addon also provides an option (dialog) to manually select the TV recordings for conversion. Any ongoing recording is marked with a leading 'T' (to signal an active timer) in the list. Accordingly, titles that were successfully archived are marked with a leading 'A' in the list - unless the source has been removed.

The addon was developed and tested on a linux platform with Kodi 18. Some code has been implemented to support other platforms and newer Kodi releases with Python3 support which remains yet to be tested. It leverages Kodi JSONRPC calls to retrieve the list of active Kodi timers and recordings. The mapping of Kodi recordings to the PVR backend (VDR) specific files is handled in a single function. It is possible to add mappings to other PVR backends than VDR by implementing the appropriate function calls.

Currently, only German and English translations are provided. Use at your own risk and please be aware that the
addon code is still under development.

My special credits go to Roman_V_M of Team-Kodi whose PyXBMCt framework helped me to easily create the selection dialog for this addon.
