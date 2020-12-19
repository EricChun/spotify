import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import csv
import pandas as pd
from collections import Counter

class Connections:
    def __init__(self, client_id, client_secret, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = 'http://example.com'
        self.sp = None
        self.sp_user = None
        self.user_playlists = []
        self.playlist = None
        self.filtered_playlist = None

    def set_sp(self):
        self.sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=self.client_id, client_secret=self.client_secret))

    def set_sp_user(self):
        self.sp_user = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=self.scope, client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.redirect_uri))

    def get_user_playlists(self):
        if self.sp_user is None:
            print('sp_user not set')
        else:
            resp = self.sp_user.current_user_playlists()
            for i in resp['items']:
                d = {
                    'id': i['id'],
                    'name': i['name']
                }
                self.user_playlists.append(d)

    def choose_playlist(self):
        if len(self.user_playlists) == 0:
            print('no playlists yet')
        else:
            for i in range(len(self.user_playlists)):
                print('[{}] {}'.format(i, self.user_playlists[i]['name']))
            while self.playlist is None:
                choice = int(input('Please pick a playlist: '))
                while choice < 0 or choice >= len(self.user_playlists):
                    choice = int(input('Please pick a valid playlist: '))
                id, name = self.user_playlists[choice]['id'], self.user_playlists[choice]['name']
                self.playlist = self.Playlist(id, name, self.sp)

    def filter_playlist(self):
        """
        Returns filtered_tracks, a dataframe of tracks filtered to genres of interest

        :param tracks: dataframe
            tracks data
        :param genres: list
            list of genres on which to filter
        """
        if self.playlist.filtered_tracks is None:
            print('no filtered playlist to create')
        else:
            self.filtered_playlist = self.Filtered_Playlist(self.playlist.filtered_tracks, self.playlist.name, self.playlist.filter, self.user_playlists, self.sp_user)

    class Playlist:
        def __init__(self, id, name, sp):
            self.id = id
            self.name = name
            self.size = None
            self.sp = sp
            self.limit = 20
            self.market = 'US'
            self.offset = 0
            self.tracks = []
            self.albums = []
            self.artists = []
            self.raw_dict = None
            self.file_names = {
                'tracks': 'raw_tracks',
                'albums': 'raw_albums',
                'artists': 'raw_artists',
            }
            self.raw_tracks = None
            self.raw_albums = None
            self.raw_artists = None
            self.fact_tracks = None
            self.genre_counts = None
            self.word_counts = None
            self.filter_type = None
            self.filter = None
            self.filtered_tracks = None

        def set_size(self):
            """
            Sets the size (number of tracks) of a playlist, using playlist_items API call.
            """
            playlist_resp = self.sp.playlist(playlist_id=self.id)
            self.size = playlist_resp['tracks']['total']

        def set_raw_dict(self):
            """
            Returns a dictionary containing 3 items (tracks, albums, and artists) from a playlist.
            Each item is a list of dictionaries - each being its own track, album, or artist.

            !!! could look into making this more simple/modular and/or using a better/separate deduping method
                e.g. frozenset (https://www.geeksforgeeks.org/python-removing-duplicate-dicts-in-list/)

            !!! playlist_items returns a dictionary
                mostly interested in the item called "items", but keeping everything for now for discovery reasons
            """
            # reset offset to 0 if rerunning
            if self.raw_dict is not None:
                self.offset = 0
            # playlist_items API call which returns a dictionary with data about a playlist
            playlist_resp = self.sp.playlist_items(playlist_id=self.id, limit=self.limit, market=self.market, offset=self.offset)
            # create empty lists for album and artist IDs of each track
            album_ids = []
            artist_ids = []
            # grab the list of dictionaries for every track
            items_li = playlist_resp['items']
            # raw_tracks (list of dictionaries of unique tracks)
            for item_dict in items_li:
                track_dict = item_dict['track']
                track_id = track_dict['id']
                track_name = track_dict['name']
                album_dict = track_dict['album']
                album_id = album_dict['id']
                album_ids.append(album_id)
                artists_li = track_dict['artists']
                for artist_dict in artists_li:
                    artist_id = artist_dict['id']
                    artist_ids.append(artist_id)
                track = {
                    "id": track_id,
                    "name": track_name,
                    "album_id": album_id,
                    "artist_ids": [artist['id'] for artist in artists_li],
                }
                if track['id'] not in [t['id'] for t in self.tracks]:
                    self.tracks.append(track)
            # list of unique album IDs
            albums_resp = self.sp.albums(list(set(album_ids)))
            # raw_albums (list of dictionaries of unique albums - appended to the function arg)
            for album_dict in albums_resp['albums']:
                id = album_dict['id']
                name = album_dict['name']
                genres = album_dict['genres']   # albums don't actually have genres, which is interesting
                label = album_dict['label']
                album = {
                    "id": id,
                    "name": name,
                    "genres": genres,
                    "label": label,
                }
                # dedupe
                if album['id'] not in [a['id'] for a in self.albums]:
                    self.albums.append(album)
            # list of unique artist IDs
            artists_resp = self.sp.artists(list(set(artist_ids)))
            # raw_artists (list of dictionaries of unique artists - appended to the function arg)
            for artist_dict in artists_resp['artists']:
                id = artist_dict['id']
                name = artist_dict['name']
                genres = artist_dict['genres']
                artist = {
                    "id": id,
                    "name": name,
                    "genres": genres,
                }
                # dedupe
                if artist['id'] not in [a['id'] for a in self.artists]:
                    self.artists.append(artist)
            # recursive
            if self.offset + self.limit > self.size:
                print('Done.')
                self.raw_dict = {
                    "tracks": self.tracks,
                    "albums": self.albums,
                    "artists": self.artists,
                }
                return
            else:
                print('{}/{} done. Next {}'.format(self.offset + self.limit, self.size, self.limit))
                print('tracks: {}, albums: {}, artists: {}'.format(len(self.tracks), len(self.albums), len(self.artists)))
                self.offset += self.limit
                # recursion to process the next batch
                return self.set_raw_dict()

        def to_csv(self):
            """
            Creates a CSV file using a list of dictionaries.

            !!! create a SQL db so that we can write to the db instead of creating CSVs
            """
            for type, file_name in self.file_names.items():
                li_dict = self.raw_dict[type]
                # get the keys of the dictionaries to use a column head for the CSV
                col_names = li_dict[0].keys()
                # convert values of columns with list to strings
                li_v_0 = list(li_dict[0].values())
                li_cols = [li_v_0.index(v) for v in li_v_0 if isinstance(v, list)]
                li_keys = [list(col_names)[i] for i in li_cols]
                for d in li_dict:
                    for k in li_keys:
                        d[k] = ', '.join(d[k])
                # write a CSV
                with open('{}.csv'.format(file_name), 'w') as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=col_names)
                    writer.writeheader()
                    writer.writerows(li_dict)

        def set_raws(self):
            self.raw_tracks = pd.read_csv('{}.csv'.format(self.file_names['tracks']))
            self.raw_albums = pd.read_csv('{}.csv'.format(self.file_names['albums']))
            self.raw_artists = pd.read_csv('{}.csv'.format(self.file_names['artists']))

        def set_fact_tracks(self):
            """
            Sets fact_tracks, a dataframe of tracks with a column of lists of the main artist's genres.
            """
            # new col: main_artist who is the first in the list
            self.raw_tracks['main_artist'] = self.raw_tracks['artist_ids'].str.split(', ').str[0]
            # join two dataframes on main artist
            self.fact_tracks = self.raw_tracks.merge(self.raw_artists, left_on='main_artist', right_on='id', suffixes=('_track', '_artist'))
            # list of columns to drop from the table (ones that share the same column names in both dataframes but are from artists)
            drop_cols = [x for x in self.fact_tracks.columns if '_artist' in x]
            # drop columns
            self.fact_tracks.drop(columns=drop_cols, inplace=True)
            # rename column names from tracks that shared names with artists (and therefore got suffixes appended)
            self.fact_tracks.columns = [x.replace('_track', '') for x in self.fact_tracks.columns]

        def set_counts(self):
            tracks = self.fact_tracks.copy()
            tracks['genres'].fillna('', inplace=True)
            # convert string of genres for each row into lists, then create a list of each row's list, and then flatten
            genres = [genre for li in tracks['genres'].str.split(', ').to_list() for genre in li]
            # create a flattened list of words in genres
            words = [word for li in [w.split(' ') for w in genres] for word in li]
            # set counts
            self.genre_counts = Counter(genres).most_common()
            self.word_counts = Counter(words).most_common()

        def view_counts(self):
            """
            Allows users to see counts of tracks by genres and words.
            """
            options = ['genres', 'key words', 'done']
            quit = 0
            while quit == 0:
                for o in range(len(options)):
                    print('[{}] {}'.format(o, options[o]))
                print_choice = int(input('Enter 0 to see number of tracks by genres, 1 to see by key words, or 2 to quit: ').strip())
                if print_choice == 0:
                    for i in range(len(self.genre_counts)):
                        print('[{}] {}: {}'.format(i, self.genre_counts[i][0], self.genre_counts[i][1]))
                elif print_choice == 1:
                    for i in range(len(self.word_counts)):
                        print('[{}] {}: {}'.format(i, self.word_counts[i][0], self.word_counts[i][1]))
                else:
                    quit = 1

        def choose_filter_type(self):
            # ask user if they want to filter by genres or words
            self.filter_type = int(input('Filter by genres or words? Enter 0 for genres; 1 for words: '))

        def set_filter(self):
            """
            Sets the list of user's chosen filters.
            """
            choices = input('Enter indexes of genres you want (separated by commas): ').replace(' ', '').split(',')
            # set genre(s) filter list
            if self.filter_type:
                self.filter = [self.word_counts[int(i)][0] for i in choices]
            else:
                self.filter = [self.genre_counts[int(i)][0] for i in choices]

        def set_filtered_tracks(self):
            """
            Sets filtered_tracks, a dataframe of tracks filtered to genres of interest
            """
            # create filter string with genres to look for (OR denoted by '|') to be used in .contains method
            filter = '|'.join(self.filter)
            # fill missing genres with empty string
            tracks = self.fact_tracks.copy()
            tracks['genres'].fillna('', inplace=True)
            # filter tracks to interested genres
            self.filtered_tracks = tracks[tracks['genres'].str.contains(filter)].reset_index(drop=True)

    class Filtered_Playlist:
        def __init__(self, filtered_tracks, orig_name, filter, user_playlists, sp_user):
            self.filtered_tracks = filtered_tracks
            self.orig_name = orig_name
            self.filter = filter
            self.user_playlists = user_playlists
            self.sp_user = sp_user
            self.name = '{} - {} - {}'.format(self.orig_name, 'API', '/'.join(self.filter))
            self.user_id = self.sp_user.current_user()['id']
            self.playlist_description = 'API'

        def create_playlist(self):
            """
            Create or updates filtered playlist for the user.
            """
            # check if the playlist exists
            found = [(p['id'], p['name']) for p in self.user_playlists if p['name'] == self.name]
            # if playlist doesn't already exist, create one and grab ID
            if len(found) == 0:
                resp = self.sp_user.user_playlist_create(self.user_id, self.name, description=self.playlist_description)
                playlist_id = resp['id']
            else:
                playlist_id = found[0][0]
            # empty playlist
            self.sp_user.playlist_replace_items(playlist_id, '')
            # populate playlist
            i = 0
            track_ids = self.filtered_tracks['id'].to_list()
            track_ids.reverse()
            while i < len(track_ids):
                self.sp_user.playlist_add_items(playlist_id, track_ids[i: i + 50])
                i += 50

def main():
    secret = input("Enter client secret: ")
    c = Connections("a2ba45697eec4d41a1812bf63e7e5846", secret, "playlist-modify-public")
    c.set_sp()
    c.set_sp_user()
    c.get_user_playlists()
    # create new instance of Playlist
    c.choose_playlist()
    p = c.playlist
    p.set_size()
    # create raw tables
    p.set_raw_dict()
    p.to_csv()  # explore free firebase/mongodb
    p.set_raws()
    # create fact tables
    p.set_fact_tracks()
    p.fact_tracks.to_csv('fact_tracks.csv', index=False)
    p.set_counts()
    p.view_counts()
    # let user choose genres/words to filter on
    p.choose_filter_type()
    p.set_filter()
    # filter tracks
    p.set_filtered_tracks()
    p.filtered_tracks.to_csv('filtered_tracks.csv', index=False)
    # create new instance of Filtered_Playlist
    c.filter_playlist()
    f = c.filtered_playlist
    # create or update filtered playlist
    f.create_playlist()
