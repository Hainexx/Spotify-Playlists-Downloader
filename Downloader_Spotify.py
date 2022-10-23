'''Downloader Spotify'''
import urllib.request
from os import path
from os import system
import sys
import mutagen
import yt_dlp as youtube_dl
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from mutagen.mp3 import MP3
import pandas as pd
from spotify_dl.scaffold import log
from spotify_dl.utils import sanitize

import tekore as tk
import pandas as pd
#import numpy as np





'''Code below has to be ran only the first time, then it is saved in .cfg file'''
'''Uncomment it if this is your first time'''
'''insert your personal client_id and client_secret code here'''

#client_id = ''
#client_secret = ''
#redirect_uri = 'http://localhost:8888/callback'


#conf = (client_id, client_secret, redirect_uri)
#token = tk.prompt_for_user_token(*conf, scope=tk.scope.every)

#conf = (client_id, client_secret, redirect_uri, token.refresh_token)
#tk.config_to_file('tekore.cfg', conf)

conf = tk.config_from_file('/Users/hainex/projects/Spotify/tekore.cfg', return_refresh=True)
user_token = tk.refresh_user_token(*conf[:2], conf[3])
s = tk.Spotify(user_token, chunked_on=False)
  
def prompt_user(what: str) -> bool:
    '''prompt tot select playlists manually'''
    while True:
        resp = input(f"{what} [Y/n]: ").strip()
        if resp.lower() == "y" :
            return True
        elif resp.lower() == "n" or resp == "":
            return False

def downlad_data(spoty = s):
    artist_name = []
    track_name = []
    popularity = []
    track_id = []
    genres = []
    playlist_name = []

    for playlist in spoty.all_items(s.followed_playlists()):
        if not prompt_user(f"Analyze playlist '{playlist.name}'?"):
            continue
        for item in s.all_items(s.playlist_items(playlist.id)):
            if not item.track.track or item.track.is_local:
                continue
            playlist_name.append(playlist.name)
            artist_name.append(item.track.artists[0].name)
            track_name.append(item.track.name)
            popularity.append(item.track.popularity)
            track_id.append(item.track.id)
            ids = item.track.artists[0].id
            try:
                gen_ls = []
                for gen in s.artist(ids).genres[:5]:
                    gen_ls.append(gen)
                genres.append(gen_ls)
            except:
                genres.append(None)
                
    df_tracks = pd.DataFrame({'artist_name':artist_name,'track_name':track_name,'track_id':track_id,'popularity':popularity,'genres':genres,'playlist_name':playlist_name})
    print('number of elements in the track_id list:', len(df_tracks))
    return df_tracks



def default_filename(song):
    return sanitize(f"{song.artist_name} - {song.track_name}", '#')  # youtube-dl automatically replaces with #


def playlist_num_filename(song):
    return f"{song.indexx} - {default_filename(song)}"


def download_songs(songs, download_directory = "~/Desktop/music/", format_string = 'bestaudio/best', skip_mp3 = False,
                   keep_playlist_order=False, no_overwrites=False, skip_non_music_sections=False,
                   file_name_f=default_filename):
    """
    Downloads songs from the YouTube URL passed to either current directory or download_directory, is it is passed.
    :param songs: Dictionary of songs and associated artist
    :param download_directory: Location where to save
    :param format_string: format string for the file conversion
    :param skip_mp3: Whether to skip conversion to MP3
    :param keep_playlist_order: Whether to keep original playlist ordering. Also, prefixes songs files with playlist num
    :param no_overwrites: Whether we should avoid overwriting the song if it already exists
    :param skip_non_music_sections: Whether we should skip Non-Music sections using SponsorBlock API
    :param file_name_f: optional func(song) -> str that returns a filename for the download (without extension)
    """
    overwrites = not no_overwrites
    log.debug(f"Downloading to {download_directory}")
    for song in songs.iloc():
        query = f"{song.artist_name} - {song.track_name} ".replace(":", "").replace("\"", "")
        download_archive = path.join(download_directory, 'downloaded_songs.txt')

        file_name = file_name_f(song)
        file_path = path.join(download_directory, file_name)

        sponsorblock_remove_list = ['music_offtopic'] if skip_non_music_sections else []

        outtmpl = f"{file_path}.%(ext)s"
        ydl_opts = {
            'format': format_string,
            'download_archive': download_archive,
            'outtmpl': outtmpl,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'no_color': False,
            'postprocessors': [
                {
                    'key': 'SponsorBlock',
                    'categories': sponsorblock_remove_list,
                },
                {
                    'key': 'ModifyChapters',
                    'remove_sponsor_segments': ['music_offtopic'],
                    'force_keyframes': True,
                }],
            'postprocessor_args': ['-metadata', 'title=' + song.track_name,
                                   '-metadata', 'artist=' + song.artist_name,
                                   '-metadata', 'album=' + song.playlist_name]
        }
        if not skip_mp3:
            mp3_postprocess_opts = {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
            ydl_opts['postprocessors'].append(mp3_postprocess_opts.copy())

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([query])
            except Exception as e:
                log.debug(e)
                print('Failed to download: {}, please ensure YouTubeDL is up-to-date. '.format(query))
                continue

        if not skip_mp3:
            mp3filename = f"{file_path}.mp3"
            mp3file_path = path.join(mp3filename)
            if overwrites or not path.exists(mp3file_path):
                try:
                    song_file = MP3(mp3file_path, ID3=EasyID3)
                except mutagen.MutagenError as e:
                    log.debug(e)
                    print('Failed to download: {}, please ensure YouTubeDL is up-to-date. '.format(query))
                    continue
                song_file['date'] = song.indexx
                if keep_playlist_order:
                    song_file['tracknumber'] = str(song.indexx)
                else:
                    song_file['tracknumber'] = str(song.track_id) + '/' + str(song.indexx)
                song_file['genre'] = song.genres
                song_file.save()
                song_file = MP3(mp3filename, ID3=ID3)
                song_file.save()
            else:
                print('File {} already exists, we do not overwrite it '.format(mp3filename))
                


def main():
    print('-------------------------------------------------------------')
    df_tracks = downlad_data(s)
    df_tracks.reset_index(inplace=True)
    df_tracks['indexx'] = df_tracks.index
    download_songs(df_tracks)

if __name__ == '__main__':
    main();

