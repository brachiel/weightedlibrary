
import time

if __name__ != "__main__":
    from quodlibet import app
    from quodlibet.plugins.songsmenu import SongsMenuPlugin

    from gi.repository import Gtk
else:
    _ = lambda x: x

    class SongsMenuPlugin:
        pass
    class Gtk:
        class Window:
            pass

class BpmTagger(SongsMenuPlugin):
    """Provide a GUI to be able to manually tag songs Beats Per Minute by tapping a button"""

    PLUGIN_ID = "bpmtagger"
    PLUGIN_NAME = _("BPM Tagger")
    PLUGIN_ICON = Gtk.STOCK_FIND_AND_REPLACE
    PLUGIN_DESC = _("Tap to the music to tag beats per minute of the current song")

    def plugin_songs(self, songs):
        win = BpmTaggerWindow()
        win.set_icon_name(self.PLUGIN_ICON)
        win.set_title(self.PLUGIN_NAME)
        win.show_all()

class BpmTaggerWindow(Gtk.Window):
    def __init__(self):
        super(BpmTaggerWindow, self).__init__()

        vbox = Gtk.VBox(spacing=20)
        self.add(vbox)

        topbox = Gtk.HBox(spacing=10)
        botbox = Gtk.HBox(spacing=10)
        vbox.pack_start(topbox, True, True, 0)
        vbox.pack_start(botbox, True, True, 0)
        vbox.show()

        # top box
        self.top_label = Gtk.Label()
        self.song_bpm_label = Gtk.Label()
        
        reset_button = Gtk.Button(label="Reset")
        reset_button.connect("clicked", self.on_reset_clicked)

        # middle box
        self.mid_label = Gtk.Label("Tap to the beat")
        self.current_bpm_label = Gtk.Label("-")

        tapper_button = Gtk.Button(label="Tap!")
        tapper_button.connect("pressed", self.on_tapper_pressed)

        # bottom box
        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.on_save_clicked)
        save_button.options('disabled',True)

        # packing

        # mix top and mid boxes such that they are aligned
        labelbox = Gtk.VBox()
        bpmbox = Gtk.VBox()
        buttonbox = Gtk.VBox()

        labelbox.pack_start(self.top_label, True, True, 0)
        bpmbox.pack_start(self.song_bpm_label, True, True, 0)
        buttonbox.pack_start(reset_button, True, True, 0)

        labelbox.pack_start(self.mid_label, True, True, 0)
        bpmbox.pack_start(self.current_bpm_label, True, True, 0)
        buttonbox.pack_start(tapper_button, True, True, 0)

        topbox.pack_start(labelbox, True, True, 0)
        topbox.pack_start(bpmbox, True, True, 0)
        topbox.pack_start(buttonbox, True, True, 0)
        botbox.pack_start(save_button, True, True, 0)
        
        ## initialisation
        self.reset()
    
    def reset(self):
        self.current_bpm = None
        self.current_taps = None
        self.current_run_start = None

        self.current_song = app.player.song

        self.current_bpm_label.set_label('-')
        self.top_label.set_label("Current song: " + self.current_song("title"))
        self.song_bpm_label.set_label(self.current_song("bpm") or "-")

    def on_tapper_pressed(self, event):
        if self.current_taps is None: # First tap
            self.current_taps = 0
            self.current_run_start = time.time()
            return

        self.current_taps += 1

        # Calculate current BPMs
        time_diff = time.time() - self.current_run_start # in seconds
        self.current_bpm = self.current_taps * 60 / time_diff # *60 -> per minute

        print "time_diff: %s, current_taps: %s, bpm: %s" % (time_diff, self.current_taps, self.current_bpm)

        # Show current bpm
        self.current_bpm_label.set_label(str(int(self.current_bpm)))
    
    def on_save_clicked(self, event):
        bpm = int(self.current_bpm)
        self.current_song["bpm"] = str(bpm) # bpm (apparently) is a string attribute
        self.reset()
    
    def on_reset_clicked(self, event):
        self.reset()
      
