# -*- coding: utf-8 -*-
# Copyright 2005-2009 Joe Wreschnig, Steven Robertson
#                2012 Nick Boultbee
#                2015 Wanja Chresta
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import random

from gi.repository import Gtk

from quodlibet.plugins.songsmenu import SongsMenuPlugin
from quodlibet import app
from quodlibet import config
from quodlibet import util

class Rater(object):
    name = None

    def rate(self, obj, context):
        """Return a rating for object in the given context in [0,1]"""
        raise NotImplementedError

    def __repr__(self):
        return self.name

class BpmRater(Rater):
    name = "Bpm"

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
    name = "SongRating"

    def rate(self, song, song_list):
        return song("~#rating")

class RepeaterRater(Rater):
    name = "Repeater"

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
    name = "Averaged"

    def __init__(self):
        self.raters = []

    def add_rater(self, weight, rater):
        self.raters.append((weight, rater))

    def rate_with_details(self, song, song_list):
        score = 0.
        rating_details = {}
        for weight, rater in self.raters:
            this_score = weight * rater.rate(song, song_list)
            rating_details[rater] = this_score
            score += this_score

        return max(0, score), rating_details 

    def rate(self, song, song_list):
        score, _ = self.rate_with_details(song, song_list)
        return score

class ModifiedAveragedRater(AveragedRater):
    name = "ModifiedAveraged"

    def __init__(self):
        super(ModifiedAveragedRater, self).__init__()
        self.modifiers = []
        self.last_rating = {"base":{}, "modifier": {}}

    def add_modifier(self, weight, rater):
        self.modifiers.append((weight, rater))

    def rate_with_details(self, song, song_list):
        score, rating_details = super(ModifiedAveragedRater, self).rate_with_details(song, song_list)

        # save rating details for later use
        # Newly initialize! Otherwise we share information between rating runs
        self.last_rating = { "base":{}, "modifier":{} }
        self.last_rating["base"] = rating_details

        for weight, modifier in self.modifiers:
            this_score = weight * modifier.rate(song, song_list)
            self.last_rating["modifier"][modifier] = this_score # save for later use
            score *= this_score

        return score

    def rating_details(self):
        return self.last_rating

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

        # if we need to create a playlist with a specific duration, we need to know how long the
        # initial playlist takes
        for song in init_playlist:
            total_play_length += song("~#length")

        if debug:
            print "Total length in Queue: %i, goal: %i" % (total_play_length, play_length)

        songs = self.library[:] # make a copy of the song list

        # remove the songs already in the initial playlist
        for song in init_playlist:
            try:    
                songs.remove(song)
            except ValueError:
                pass

        while (len(songs) > 0 and       # as long as there's still songs to choose from
               (num_items is None or len(playlist) <= num_items) and        # and the total duration is not reached
               (play_length is None or total_play_length < play_length)):       # and we have not found enough songs
            scores = {}
            rating_details = {}

            total_score = 0.

            # Rate all songs depending on the current playlist
            for song in songs:
                scores[song] = self.rater.rate_with_details(song, playlist)
                if debug:
                    rating_details[song] = self.rater.rating_details()
                total_score += scores[song]

            random_score = random.random() * total_score
            current_score = 0.

            for song, score in scores.items():
                current_score += score
                if current_score >= random_score:
                    break
            else:
                # wasn't able to find a song; this should never be possble
                raise RuntimeError("Couldn't find song; this should never happen")
            # the last song, score of the above for loop is the chosen one :D

            if debug:
                # here, score is still the score from the above for loop
                song["~#score_total"] = score
                # times scores it by 100 to make it more readable
                print "%s (Total: %i)" % (song("title"), score)

                for rater, score in rating_details[song]["base"].iteritems():
                    song["~#score_%s" % rater.name.lower()] = score
                    print "    +%.2f (%s)" % (score, rater)

                for rater, score in rating_details[song]["modifier"].iteritems():
                    song["~#score_%s" % rater.name.lower()] = score
                    print "    *%.2f (%s)" % (score, rater)

            songs.remove(song) # Remove this song from the potential songlist
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

    # keys for configuration screen
    keys = [
        ("rating", _("Rated higher")),
        ("lastplayed", _("Played more recently"))
    ]

    # configuration values
    weights = {"rating":0.0, "lastplayed":0.0}

    def __init__(self, songs, library):
        super(WeightedPlaylist, self).__init__(songs, library)

        for (key, text) in self.keys:
            val = config.getfloat("plugins", "randomalbum_%s" % key, 0.0)
            self.weights[key] = val

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
        playlist = self.rated_library.create_playlist(init_playlist=current_queue, play_length=5*60*60)

        # Append to current queue
        app.window.playlist.enqueue(playlist)

        return True
    
    # we need to use classmethod since we're not an EventPlugin and are not instanciated until we're called.
    @classmethod
    def PluginPreferences(cls, plugin_container):
        # Almost copied identically from randomalbum plugin
        def changed_cb(hscale, key):
            val = hscale.get_value()
            cls.weights[key] = val
            config.set("plugins", "weightedlibrary_%s" % key, val)

        vbox = Gtk.VBox(spacing=12)
        table = Gtk.Table(n_rows=len(cls.keys) + 1, n_columns=3)
        table.set_border_width(3)

        frame = Gtk.Frame(label=_("Weights"))

        frame.add(table)
        vbox.pack_start(frame, True, True, 0)

        # Less label
        less_lbl = Gtk.Label()
        arr = Gtk.Arrow(arrow_type=Gtk.ArrowType.LEFT,
                        shadow_type=Gtk.ShadowType.OUT)
        less_lbl.set_markup("<i>%s</i>" % util.escape(_("avoid")))
        less_lbl.set_alignment(0, 0)
        hb = Gtk.HBox(spacing=0)
        hb.pack_start(arr, False, True, 0)
        hb.pack_start(less_lbl, True, True, 0)
        table.attach(hb, 1, 2, 0, 1, xpadding=3,
                     xoptions=Gtk.AttachOptions.FILL)
        # More label
        more_lbl = Gtk.Label()
        arr = Gtk.Arrow(arrow_type=Gtk.ArrowType.RIGHT,
                        shadow_type=Gtk.ShadowType.OUT)
        more_lbl.set_markup("<i>%s</i>" % util.escape(_("prefer")))
        more_lbl.set_alignment(1, 0)
        hb = Gtk.HBox(spacing=0)
        hb.pack_end(arr, False, True, 0)
        hb.pack_end(more_lbl, True, True, 0)
        table.attach(hb, 2, 3, 0, 1, xpadding=3,
                     xoptions=Gtk.AttachOptions.FILL)

        for (idx, (key, text)) in enumerate(cls.keys):
            lbl = Gtk.Label(label=text)
            lbl.set_alignment(0, 0)
            table.attach(lbl, 0, 1, idx + 1, idx + 2,
                         xoptions=Gtk.AttachOptions.FILL,
                         xpadding=3, ypadding=3)
            adj = Gtk.Adjustment(lower=-1.0, upper=1.0, step_increment=0.1)
            hscale = Gtk.HScale(adjustment=adj)
            hscale.set_value(cls.weights[key])
            hscale.set_draw_value(False)
            hscale.set_show_fill_level(False)
            hscale.connect("value-changed", changed_cb, key)
            lbl.set_mnemonic_widget(hscale)
            table.attach(hscale, 1, 3, idx + 1, idx + 2,
                         xpadding=3, ypadding=3)

        return vbox

        
class WeightedPlaylistAll(WeightedPlaylist):
    """Same as WeightedPlaylist but ignore the selection and take all available songs."""

    PLUGIN_ID = "weightedplaylistall"
    PLUGIN_NAME = _("Weighted playlist")
    PLUGIN_ICON = "gtk-media-next"
    PLUGIN_DESC = _("From the library with current filters, enqueue a playlist according to weighted ratings.")

    def plugin_songs(self, songs):
        # Use current songlist instead of songs
        songlist_songs = app.window.songlist.get_songs()

        # Call parent method with current songlist instead of selected songs
        return super(WeightedPlaylistAll, self).plugin_songs(songlist_songs)

