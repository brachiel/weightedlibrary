
import time

if __name__ != "__main__":
    from quodlibet import app, qltk
    from quodlibet.plugins.songsmenu import SongsMenuPlugin

    from gi.repository import Gtk
else:
    _ = lambda x: x
    class qltk:
        class Icons:
            MEDIA_SKIP_FORWARD = ""

    class SongsMenuPlugin:
        pass
    class Gtk:
        class Window:
            pass

class BpmTagger(SongsMenuPlugin):
    """Provide a GUI to be able to manually tag songs Beats Per Minute by tapping a button"""

    PLUGIN_ID = "bpmtagger"
    PLUGIN_NAME = _("BPM Tagger")
    PLUGIN_ICON = qltk.Icons.MEDIA_SKIP_FORWARD
    PLUGIN_DESC = _("Tap to the music to tag beats per minute of the current song")

    def plugin_songs(self, songs):
        win = BpmTaggerWindow()
        win.set_icon_name(self.PLUGIN_ICON)
        win.set_title(self.PLUGIN_NAME)
        win.show_all()

class BpmTaggerWindow(Gtk.Window):
    def __init__(self):
        super(BpmTaggerWindow, self).__init__()

        #self.set_size_request(400, 400)

        hbox = Gtk.Box(spacing=6)
        self.add(hbox)
        hbox.show()

        fix_label = Gtk.Label("Tap to the beat")
        self.current_bpm_label = Gtk.Label("-")

        tapper_button = Gtk.Button(label="Tap!")
        tapper_button.connect("pressed", self.on_tapper_pressed)

        reset_button = Gtk.Button(label="Reset")
        reset_button.connect("clicked", self.on_reset_clicked)

        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.on_save_clicked)

        hbox.pack_start(fix_label, True, True, 0)
        hbox.pack_start(self.current_bpm_label, True, True, 0)
        hbox.pack_start(tapper_button, True, True, 0)
        hbox.pack_start(reset_button, True, True, 0)
        hbox.pack_start(save_button, True, True, 0)
        
        ## initialisation
        self.reset()

        this_song = app.window.playlist.current
        print "BPM of the current song: %s" % this_song("bpm")
    
    def reset(self):
        self.current_bpm = None
        self.current_taps = None
        self.current_run_start = None


    def on_tapper_pressed(self, event):
        if self.current_taps is None: # First tap
            self.current_taps = 0
            self.current_run_start = time.time()

            print "BPM first tap"

            return

        self.current_taps += 1

        # Calculate current BPMs
        time_diff = time.time() - self.current_run_start # in seconds
        self.current_bpm = self.current_taps * 60 / time_diff # *60 -> per minute

        print "time_diff: %s, current_taps: %s, bpm: %s" % (time_diff, self.current_taps, self.current_bpm)

        # Show current bpm
        self.current_bpm_label.set_label(str(int(self.current_bpm)))
    
    def on_save_clicked(self, event):
        this_song = app.window.playlist.current
        print "BPM of the current song: %s" % this_song("bpm")

        bpm = int(self.current_bpm)
        this_song["~#bpm"] = bpm

        self.current_bpm_label.set_label('Saved')
        self.reset()
    
    def on_reset_clicked(self, event):
        self.current_bpm_label.set_label('-')
        self.reset()
      
