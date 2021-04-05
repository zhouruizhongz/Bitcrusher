########################################
#  Sky.fm XBMC plugin
#  by Tim C. 'Bitcrusher' Steinmetz
#  http://qualisoft.dk
#  Github: https://github.com/Bitcrusher/Sky-FM-XBMC-plugin
#  Git Read-only: git://github.com/Bitcrusher/Sky-FM-XBMC-plugin.git
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#

import os
import sys
import re
import urllib
import urllib2
import string
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import pickle
import time
import random
from xml.dom import minidom
from httpcomm import HTTPComm	

# Various vars used throughout the script
HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon(id='plugin.audio.sky.fm')


# Plugin constants
__plugin__       = "Sky.fm"
__author__       = "Tim C. Steinmetz"
__url__          = "http://qualisoft.dk/"
__platform__     = "xbmc media center, [LINUX, OS X, WIN32]"
__date__         = "3. May 2012"
__version__      = ADDON.getAddonInfo('version')



BASEURL    = "http://www.sky.fm"
PREMIUMURL = "http://www.sky.fm/login"

PROFILEPATH = xbmc.translatePath( ADDON.getAddonInfo('profile') ).decode('utf-8')

ART_DIR = os.path.join( PROFILEPATH, 'resources', 'art', '' ) # path to channelart

STREAMURLSCACHE = PROFILEPATH + "cachestream.dat"
STREAMTITLESCACHE = PROFILEPATH + "cachestreamtitle.dat"
STREAMBITRATECACHE = PROFILEPATH + "streamrate.dat"
STREAMLABELCOLORCACHE = PROFILEPATH + "streamisnew.dat"
CHECKINFILE = PROFILEPATH + "lastcheckin.dat"
TMP_STREAM = PROFILEPATH + "tmp_stream.dat"

NEWSTREAMS = 0
LABELCOLOR = 'FF0000'

HTTPCOMM = None

xbmc.log( "[PLUGIN] %s v%s (%s)" % ( __plugin__, __version__, __date__ ), xbmc.LOGNOTICE )

# Main class
class Main:
	def __init__(self) :
		self.getStreams()
	
		# If streams should be sorted A-Z
		if ADDON.getSetting('sortaz') == "true" :
			xbmcplugin.addSortMethod( HANDLE, sortMethod=xbmcplugin.SORT_METHOD_LABEL )

		# End of list
		xbmcplugin.endOfDirectory( HANDLE, succeeded=True )

		# If stats is allowed and its been at least 24 hours since last stat checkin
		if (ADDON.getSetting('allowstats') == "true") and (self.checkFileTime(CHECKINFILE, 86400) == True) :
			open(CHECKINFILE, "w")
			
			account = 'public'
			if ADDON.getSetting('username') != "" :
				account = 'premium'

			xbmc.log( 'Submitting stats', xbmc.LOGNOTICE )
			HTTPCOMM.get('http://stats.qualisoft.dk/?plugin=sky&version=' + __version__ + '&account=' + account + '&key=5a2a72084f40402656555b665a0fdcddbbd87553')
		

	# Let's get some tunes!
	def getStreams(self) :
		global LABELCOLOR
		global HTTPCOMM

		failedstreams = 0

		# will be cached
		streamurls = []
		streamtitles = []
		streamisnew = []
		streambitrate = 40
		channelicons = None

		# Precompiling regexes
		iconreplacement_re = re.compile('[ \'-]', re.I) # generic regex for iconnames
		
		channelicon_re	= re.compile('="[\d\w\s]+?" src="(http:[^"]+)"', re.I)	
		playlist_re	= None

		HTTPCOMM = HTTPComm() # Init CURL thingy

		# Check if cachefiles has expired
		if ((int( ADDON.getSetting("cacheexpire") ) * 60) != 0 and self.checkFileTime(STREAMURLSCACHE, (int( ADDON.getSetting("cacheexpire") ) * 60)) == True) or ADDON.getSetting("forceupdate") == "true" :
		
			# If username NOT set, get public streams
			if ADDON.getSetting('username') == "" :
				xbmc.log( "Refreshing public streams", xbmc.LOGNOTICE )
				channeltitle_re = re.compile('>([^<]+)</a>[\s\r\n]*<ul>[\s\r\n]*<li>[\s\r\n]*<a href="/play/[^"]+" data-wp="false">WebPlayer</a>', re.I)
				streamurl_re 	= re.compile('<li>[\s\r\n]*<a href="/play/([^"]+)" data-wp="false">WebPlayer</a>', re.I) # first stream in .pls file


				# list of possible stream servers
				publicservers = []
				publicservers.append( 'http://u16b.sky.fm/' )				
				publicservers.append( 'http://u12.sky.fm/' )
				publicservers.append( 'http://u12b.sky.fm/' )
				publicservers.append( 'http://u16.sky.fm/' )
				publicservers.append( 'http://u17.sky.fm/' )
				publicservers.append( 'http://u17b.sky.fm/' )

				# Get frontpage of sky.fm - if it fails, show a dialog in XBMC
				try :
					htmlData     = HTTPCOMM.get( BASEURL )
				except Exception:
					xbmcgui.Dialog().ok( ADDON.getLocalizedString(30100), ADDON.getLocalizedString(30101), ADDON.getLocalizedString(30102) )
					xbmc.log( 'Connection error - Could not connect to sky.fm - Check your internet connection', xbmc.LOGERROR )
					return False

				playlists = streamurl_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(playlists)) + ' streams', xbmc.LOGNOTICE )

				streamtitles = channeltitle_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(streamtitles)) + ' titles', xbmc.LOGNOTICE )
						
				channelicons  = channelicon_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(channelicons)) + ' pieces of channelart', xbmc.LOGNOTICE )

				if len(playlists) == 0 :
					xbmcgui.Dialog().ok( ADDON.getLocalizedString(30110), ADDON.getLocalizedString(30111), ADDON.getLocalizedString(30112) )
					return False
				
				# output public streams to XBMC
				for index, item in enumerate(playlists):
					LABELCOLOR = 'FF0000'
					cur_servernr = 0
					streamurl = ''
					gotStream = False
					random.shuffle(publicservers) # Shuffle streamservers aka 'cheap-ass load balancing' :P

					while gotStream == False : # HTTPCOMM.testStream will return True when hitting a positive stream
						gotStream = HTTPCOMM.testStream(publicservers[cur_servernr] + 'sky_' + playlists[index] + '_aacplus.flv')
						streamurl = publicservers[cur_servernr] + 'sky_' + playlists[index] + '_aacplus.flv'
						if cur_servernr < len(publicservers)-1 :
							cur_servernr = cur_servernr+1
						elif cur_servernr == len(publicservers)-1 :
							gotStream = True
							streamurl = 'nostreamingserverfound'
							failedstreams = failedstreams+1
					
					streamtitle = streamtitles[index]

					icon = ART_DIR + string.lower(iconreplacement_re.sub('', streamtitle) + ".png")

					if(not self.getStreamicon( icon, channelicons[index] )) : # if False is returned, use plugin icon
						icon = xbmc.translatePath( os.path.join( ADDON.getAddonInfo('path'), '' ) ) + 'icon.png'

					if streamurl != 'nostreamingserverfound' :
						# Will highlight new channels/has new channelart
						if LABELCOLOR != 'FF0000' :
							self.addItem(streamtitle, streamurl, streambitrate, icon, LABELCOLOR)
						else :
							self.addItem(streamtitle, streamurl, streambitrate, icon, False)

					streamtitles.append(streamtitle) # for caching
					streamurls.append(streamurl)
					streamisnew.append(LABELCOLOR)


			# TODO: The premium support is disabled for now. As it's not possible to enter username
			# Got some logic about Premium stream handeling I need to work out

			# Get premium streams
			elif ( ADDON.getSetting('username') != "" ) :
				xbmc.log( "Refreshing premium streams", xbmc.LOGNOTICE )

				channeltitle_re = re.compile('>([^<]+)</a>[\s\r\n]*<ul>[\s\r\n]*<li>[\s\r\n]*<a href="/play/[^"]+" data-wp="true">WebPlayer</a>', re.I)
				streamurl_re 	= re.compile('<li>[\s\r\n]*<a href="/play/([^"]+)" data-wp="true">WebPlayer</a>', re.I) # first stream in .pls file

				logindata = urllib.urlencode({ 'member_session[username]':  ADDON.getSetting('username'),
  							       'member_session[password]':  ADDON.getSetting('password') })

				# list of possible stream servers
				premiumservers = []
				premiumservers.append( 'http://72.26.216.106/' )
				
				# Login and get frontpage of sky.fm - if it fails, show a dialog in XBMC
				try :
					htmlData = HTTPCOMM.post( PREMIUMURL, logindata, PROFILEPATH + 'authcookie.lwp' )
				except Exception:
					xbmcgui.Dialog().ok( ADDON.getLocalizedString(30100), ADDON.getLocalizedString(30101), ADDON.getLocalizedString(30102) )
					xbmc.log( 'Connection error - Could not connect to sky.fm - Check your internet connection', xbmc.LOGERROR )
					return False
				
				playlists = streamurl_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(playlists)) + ' streams', xbmc.LOGNOTICE )

				streamtitles = channeltitle_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(streamtitles)) + ' titles', xbmc.LOGNOTICE )
						
				channelicons  = channelicon_re.findall(htmlData)
				xbmc.log( 'Found ' + str(len(channelicons)) + ' pieces of channelart', xbmc.LOGNOTICE )

				if len(playlists) == 0 :
					xbmcgui.Dialog().ok( ADDON.getLocalizedString(30110), ADDON.getLocalizedString(30111), ADDON.getLocalizedString(30112) )
					return False

				playlists.pop(0) # removes the favorites stream
				streamtitles.pop(0)

				# Go find the listening key
				listenkeyData = HTTPCOMM.get( 'http://www.sky.fm/play/' + playlists[0], PROFILEPATH + 'authcookie.lwp' )
				keymatch = re.search(r"API.Config.listenKey = '([^']+)'", listenkeyData)
				#print listenkeyData
				if not keymatch: # If no listening key was found
					xbmcgui.Dialog().ok( ADDON.getLocalizedString(30160), ADDON.getLocalizedString(30111), ADDON.getLocalizedString(30112) )
					xbmc.log( 'No listening key found', xbmc.LOGERROR )
					return False
				else :
					xbmc.log( 'Found listening key', xbmc.LOGNOTICE )

				

				for index, item in enumerate(playlists) :
					#playlist = HTTPCOMM.get(item)
					
					LABELCOLOR = 'FF0000'
					cur_servernr = 0

					streamurl = ''
					gotStream = False

					streamurl = premiumservers[cur_servernr] + playlists[index] + '?' + keymatch.group(1) + '&type=.flv'

					'''
					random.shuffle(premiumservers) # Shuffle streamservers aka 'cheap-ass load balancing' :P
					
					while gotStream == False : # HTTPCOMM.testStream will return True when hitting a positive stream
						gotStream = HTTPCOMM.testStream(premiumservers[cur_servernr] + playlists[index] + '?' + keymatch.group(1) + '&type=.flv')
						streamurl = premiumservers[cur_servernr] + playlists[index] + '?' + keymatch.group(1) + '&type=.flv'
						#print premiumservers[cur_servernr] + playlists[index] + '?' + keymatch.group(1) + '&type=.flv'
						if cur_servernr < len(premiumservers)-1 :
							cur_servernr = cur_servernr+1
						elif cur_servernr == len(premiumservers)-1 :
							gotStream = True
							streamurl = False
					'''
					if streamurl != False : # only add to GUI if stream returned data
						streamtitle = streamtitles[index]

						icon = ART_DIR + string.lower(iconreplacement_re.sub('', streamtitle) + ".png")
	
						if(not self.getStreamicon( icon, channelicons[index] )) : # if False is returned, use plugin icon
							icon = xbmc.translatePath( os.path.join( ADDON.getAddonInfo('path'), '' ) ) + 'icon.png'

						# will highlight new channels/has new channelart
						if LABELCOLOR != 'FF0000' :
							self.addItem(streamtitle, streamurl, streambitrate, icon, LABELCOLOR)
						else :
							self.addItem(streamtitle, streamurl, streambitrate, icon, False)
						print "xxx" + streamurl
						streamtitles.append(streamtitle) # for caching
						streamurls.append(streamurl)
						streamisnew.append(LABELCOLOR)
					else :
						xbmc.log( 'Failed to reach the premium stream at ' + playlists[index], xbmc.LOGERROR )
						failedstreams = failedstreams+1

				xbmc.log( 'Found ' + str(len(playlists)) + ' streams', xbmc.LOGNOTICE )
				

			# Write channels to cache
			pickle.dump(streamurls, open(STREAMURLSCACHE, "w"), protocol=0)
			pickle.dump(streamtitles,  open(STREAMTITLESCACHE, "w"), protocol=0)
			pickle.dump(streambitrate, open(STREAMBITRATECACHE, "w"), protocol=0)
			pickle.dump(streamisnew, open(STREAMLABELCOLORCACHE, "w"), protocol=0)
		
			if (NEWSTREAMS > 0) : # Yay! New channels found
				xbmc.log( 'New channels found - There was found ' + str(NEWSTREAMS) + ' new piece(s) of channelart - Meaning there could be new channels', xbmc.LOGNOTICE )
				xbmcgui.Dialog().ok( ADDON.getLocalizedString(30130), ADDON.getLocalizedString(30131) + str(NEWSTREAMS) + ADDON.getLocalizedString(30132), ADDON.getLocalizedString(30133),ADDON.getLocalizedString(30134) )

			if (failedstreams > 0) : # Streams that failed
				xbmc.log( 'Failed to reach ' + str(failedstreams) + ' streams', xbmc.LOGNOTICE )
				xbmcgui.Dialog().ok( ADDON.getLocalizedString(30170), ADDON.getLocalizedString(30171) + str(failedstreams) + ADDON.getLocalizedString(30172), ADDON.getLocalizedString(30173) )

				
			# Resets the 'Force refresh' setting
			ADDON.setSetting(id="forceupdate", value="false")

		else :
			if not os.path.isfile(STREAMTITLESCACHE) or not os.path.isfile(STREAMURLSCACHE) or not os.path.isfile(STREAMBITRATECACHE) or not os.path.isfile(STREAMLABELCOLORCACHE) :
				xbmc.log( 'Cachefiles are missing - At least one of the cachefiles is missing please go to the addon settings and select "Force cache refresh"', xbmc.LOGERROR )
				xbmcgui.Dialog().ok( ADDON.getLocalizedString(30140), ADDON.getLocalizedString(30141), ADDON.getLocalizedString(30142), ADDON.getLocalizedString(30143) )
				return False

			streamurls     = pickle.load(open(STREAMURLSCACHE, "r"))    # load streams from cache
			streamtitles   = pickle.load(open(STREAMTITLESCACHE, "r"))  # load streamtitles from cache
			streambitrate  = pickle.load(open(STREAMBITRATECACHE, "r")) # load stream bitrate from cache
			streamisnew    = pickle.load(open(STREAMLABELCOLORCACHE, "r"))   # load stream 'is new' from cache

			# Output cache list of streams to XBMC
			for index, item in enumerate(streamurls):
				playlist = item
				streamurl = str(item)
				streamtitle = streamtitles[index]
				icon = ART_DIR + string.lower(iconreplacement_re.sub('', streamtitle) + ".png")

				if(not self.getStreamicon( icon, False )) : # if False is returned, use plugin icon
					icon = xbmc.translatePath( os.path.join( ADDON.getAddonInfo('path'), '' ) ) + 'icon.png'

				if streamisnew[index] != 'FF0000' :
					self.addItem(streamtitle, streamurl, streambitrate, icon, streamisnew[index])
				else :
					self.addItem(streamtitle, streamurl, streambitrate, icon, False)

			if (NEWSTREAMS < 0) : # Missing channelart dialog
				xbmc.log( "Channelart missing - There is " + str(abs(NEWSTREAMS)) + " piece(s) of channelart missing - You should refresh your cache - Disable using 'My Favorites' to get new channelart", xbmc.LOGWARNING )
				xbmcgui.Dialog().ok( ADDON.getLocalizedString(30150), ADDON.getLocalizedString(30151) + str(abs(NEWSTREAMS)) + ADDON.getLocalizedString(30152), ADDON.getLocalizedString(30153), ADDON.getLocalizedString(30154))
		
		return True

		
	# Adds streams to XBMC itemlist
	def addItem(self, channeltitle, streamurl, streambitrate, icon, labelcolor) :
		if labelcolor != False :
			li = xbmcgui.ListItem(label="[COLOR FF" + labelcolor + "]" + channeltitle + "[/COLOR]",thumbnailImage=icon)
			print "color item: " + labelcolor
		else :
			li = xbmcgui.ListItem(label=channeltitle,thumbnailImage=icon)
			print "normal item"

		li.setProperty("mimetype", 'audio/aac')
		li.setProperty("IsPlayable", "true")
		li.setProperty("IsLive", "true")
		li.setInfo('audio', { "title": channeltitle, "size": int(streambitrate)*1024 })
		xbmcplugin.addDirectoryItem(handle=HANDLE, url=streamurl, listitem=li, isFolder=False)

		return True


	# Will check if Streamart/icon is present on disk - if not, try to download
	def getStreamicon(self, iconpath, iconurl) :
		global NEWSTREAMS
		global LABELCOLOR

		if not os.path.exists(ART_DIR): # if dir for channel art is missing, create it
        		os.makedirs(ART_DIR)

		if (not os.path.isfile(iconpath) and iconurl) :
			HTTPCOMM.getImage( iconurl, iconpath )
			if not os.path.exists(iconpath) and not os.path.isfile(iconpath) : # fallback to plugin icon, if still no channel art
				LABELCOLOR = 'FF0000'
				return False
			else :
				LABELCOLOR = 'FFA800'
				NEWSTREAMS += 1
		elif (not os.path.exists(iconpath) and not os.path.isfile(iconpath) ) :
			NEWSTREAMS -= 1
			xbmc.log( 'Icon not found cached: ' + iconpath, xbmc.LOGWARNING )
			return False
		return True


	# Checks if a file is older than x seconds - returns bool
	def checkFileTime(self, tmpfile, timesince):
		# If file exists, check timestamp
		if os.path.isfile(tmpfile) :
			if os.path.getmtime(tmpfile) > (time.time() - timesince) :
				xbmc.log( 'It has not been ' + str(timesince) + ' seconds since last pagehit, using cache', xbmc.LOGNOTICE )
				return False
			else :
				xbmc.log( 'Cache has expired - refreshing cache', xbmc.LOGNOTICE )
				return True
		# If file does not exist, return true so the file will be created by scraping the page
		else :
			xbmc.log( 'Cachefile does not exist', xbmc.LOGNOTICE )
			return True

Main()
