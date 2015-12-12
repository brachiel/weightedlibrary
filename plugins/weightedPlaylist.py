
import random

if __name__ != "__main__":
    from quodlibet.plugins.songsmenu import SongsMenuPlugin
    from quodlibet import app
else:
# __main__ mode. Simulate some interfaces for quod libet
    _ = lambda x: x
    class PlayOrderPlugin:
        pass


class Rater(object):
    def rate(self, obj, context):
        """Return a rating for object in the given context in [0,1]"""
        raise NotImplementedError

    def __repr__(self):
        return self.__class__.__name__

class BpmRater(Rater):
    def __init__(self, target_bpm=80, spread=20):
        self.target_bpm = target_bpm
        self.spread = spread
        
    def rate(self, song, song_list):
        try:
            song_bpm = int(song('~#bpm'))
        except ValueError:
            return 0.

        raw_rating = 1.-(song_bpm - self.target_bpm)/(2.*self.spread)
        return max(0., raw_rating)
        
class SongRatingRater(Rater):
    def rate(self, song, song_list):
        return song("~#rating")

class RepeaterRater(Rater):
    def rate(self, song, song_list):
        try:
            last_song = song_list[-1]
            prelast_song = song_list[-2]
        except IndexError:
            return 1.
        except KeyError:
            return 1.

        total_rating = 0

        # How many repetitions are ok?
        # Second in tuple is weight; weights needs to add to 1
        # Repetition = 0 attributes force a score of 0 on repetition
        attributes = { 'genre': (1, 1.), 'artist': (0, 0) }
        for attribute, (allowed_repetitions, weight) in attributes.items():
            this = song(attribute)
            previous = last_song(attribute)
            prepre = prelast_song(attribute)

            if this != previous:
                repetitions = 0
            else:
                # We're repeating
                if previous == prepre:
                    repetitions = 2
                else:
                    repetitions = 1
            
            if repetitions > allowed_repetitions:
                # We'd be repeating more than we should =(
                return 0. # Force 0
            elif repetitions == allowed_repetitions:
                # We're on point with repetitions. This is good
                total_rating += weight
            else:
                # We're repeating less than we're allowed. This is ok but not good
                total_rating += weight/2

        return total_rating

class AveragedRater(Rater):
    def __init__(self):
        self.raters = []
        self.weight_sum = 0.

    def add_rater(self, weight, rater):
        self.raters.append((weight, rater))
        self.weight_sum += weight

    def rate_with_details(self, song, song_list):
        rate = 0.
        rating_details = {}
        for weight, rater in self.raters:
            this_rating = weight/self.weight_sum * rater.rate(song, song_list)
            rating_details[rater] = this_rating
            rate += this_rating

        return max(0, rate), rating_details 

    def rate(self, song, song_list):
        rating, _ = self.rate_with_details(song, song_list)
        return rating

class ModifiedAveragedRater(AveragedRater):
    def __init__(self):
        super(ModifiedAveragedRater, self).__init__()
        self.modifiers = []

    def add_modifier(self, weight, rater):
        self.modifiers.append((weight, rater))

    def rate_with_details(self, song, song_list):
        rate, rating_details = super(ModifiedAveragedRater, self).rate_with_details(song, song_list)

        for rater, rating in rating_details.items():
            rating_details[rater] = ('+', rating)

        for weight, modifier in self.modifiers:
            this_rating = weight * modifier.rate(song, song_list)
            rating_details[modifier] = ('*', this_rating)
            rate *= this_rating

        return rate, rating_details


class RatedLibrary():
    def __init__(self, library, rater):
        self.library = library
        self.rater = rater

    def __getitem__(self, index):
        return self.library[index]

    def __iter__(self):
        return iter(self.library)

    def create_playlist(self, init_playlist=[], num_items=None, play_length=None, debug=False):
        playlist = []
        total_play_length = 0.

        for song in init_playlist:
            total_play_length += song("~#length")
        print "Total legth in Queue: %i, goal: %i" % (total_play_length, play_length)

        songs = self.library[:] # make a copy of the song list

        # remove the songs already in the initial playlist
        for song in init_playlist:
            songs.remove(song)

        while len(songs) > 0 and (num_items is None or len(playlist) <= num_items) and (play_length is None or total_play_length < play_length):
            ratings = {}
            total_rating = 0.

            # Rate all songs depending on the current playlist
            for song in songs:
                ratings[song] = {}
                ratings[song]["rating"], ratings[song]["details"] = self.rater.rate_with_details(song, playlist)
                total_rating += ratings[song]["rating"]

            random_score = random.random() * total_rating
            current_score = 0.

            for song, rating in ratings.items():
                current_score += rating["rating"]
                if current_score >= random_score:
                    break

            if debug:
                print "%s: %f\n    %s" % (song("title"), rating["rating"], '\n    '.join(["%s=%s" % (rater, rat) for rater,rat in rating["details"].items()]))

                for rater, rat in rating["details"].items():
                    rater_name = repr(rater)
                    rater_name = rater_name[:-5].lower()
                    song["~#score_%s" % rater_name] = rat[1] # 0 is sign, 1 is actual rating
               
                song["~#score_total"] = rating["rating"]

            songs.remove(song) # Remove this song from the songlist
            playlist.append(song) # Add this song to the playlist
            total_play_length += song("~#length")

        return playlist

def test(library):
    rater = ModifiedAveragedRater()
    rater.add_rater(weight=100., rater=SongRatingRater())
    rater.add_rater(weight=30.,  rater=BpmRater())
    rater.add_modifier(weight=3.,  rater=RepeaterRater())

    rated_library = RatedLibrary(library, rater)
    playlist = rated_library.create_playlist(num_items=100, play_length=None, debug=True)

    print playlist

if __name__ == '__main__':
    import random

    class FakeSong:
        def __init__(self):
            self.seen = {}

        def __getitem__(self, arg):
            try:
                return self.seen[arg]
            except KeyError:
                val = random.randint(0,20)
                self.seen[arg] = val
                return val

        def __call__(self, arg):
            return self[arg]

        def __repr__(self):
            return '['+';'.join([ '%s=%s' % (key,val) for key,val in self.seen.items() ])+']'

    library = []
    for i in range(50):
        library.append(FakeSong())

    test(library)
    

#####################################
# Quod Libet Plugin
class WeightedPlaylist(SongsMenuPlugin):
    PLUGIN_ID = "weightedplaylist"
    PLUGIN_NAME = _("Weighted playlist from selection")
    PLUGIN_ICON = "gtk-media-next"
    PLUGIN_DESC = _("From a selection of songs, enqueue a playlist of them accoring to weighted ratings.")

    def __init__(self, songs, library):
        super(WeightedPlaylist, self).__init__(songs, library)

        rater = ModifiedAveragedRater()
        rater.add_rater(weight=100.,  rater=SongRatingRater())
        rater.add_rater(weight=30.,   rater=BpmRater())
        rater.add_modifier(weight=3., rater=RepeaterRater())

        self.rater = rater
    
    def plugin_songs(self, songs):
        # Initiate a RatedLibrary with the given (selected) songs
        self.rated_library = RatedLibrary(songs, self.rater)

        # Create a playlist out of the selected songs that lasts at least 5 hours
        current_queue = list(app.window.playlist.q.itervalues()) # Make a copy
        playlist = self.rated_library.create_playlist(init_playlist=current_queue, play_length=5*60*60, debug=True)

        # Append to current queue
        app.window.playlist.enqueue(playlist)

        return True
        
class WeightedPlaylistAll(WeightedPlaylist):
    PLUGIN_ID = "weightedplaylistall"
    PLUGIN_NAME = _("Weighted playlist")
    PLUGIN_ICON = "gtk-media-next"
    PLUGIN_DESC = _("From the library with current filters, enqueue a playlist according to weighted ratings.")

    def plugin_songs(self, songs):
        # Use current songlist instead of songs
        songlist_songs = app.window.songlist.get_songs()

        # Call parent method with current songlist instead of selected songs
        return super(WeightedPlaylistAll, self).plugin_songs(songlist_songs)

