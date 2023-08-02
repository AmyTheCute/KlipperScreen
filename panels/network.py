import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel
from ks_includes.Wifi_Utils import wifi_utils

class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)

        self.wifi = wifi_utils()
        ip = "1.2.3.4"

        self.networks = []
        self.networks_saved = []

        main_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content.add(main_frame)

        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        control_box.set_vexpand(False)

        ### --- SETUP CONTROL BOX --- ###
        main_frame.add(control_box)
        wifi_toggle_label = Gtk.Label(label="Wifi: ")
        wifi_toggle_label.set_margin_start(20)

        wifi_toggle = Gtk.Switch()

        ## TODO: Add interface: add connected wifi on top with special treatment.


        reload_networks = self._gtk.Button("refresh", None, "color1", .66)                                                                                                                                   
        reload_networks.connect("clicked", self.reload_networks)
        reload_networks.set_hexpand(False)

        control_box.add(wifi_toggle_label)
        control_box.add(wifi_toggle)
        control_box.pack_end(reload_networks, False, False, 0)

        
        ### ---- SETUP NETWORKS SCROLL WINDOW --- ###
        networks_scroll = self._gtk.ScrolledWindow()
        self.networks_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        networks_scroll.add(self.networks_widget)
        main_frame.add(networks_scroll)

        self.initialized = True

        GLib.idle_add(self.update_networks)
        

    def update_networks(self):
        print("Updaten networks m8")
        self.wifi.request_scan()
        network_list = self.wifi.get_networks(True)

        for i in network_list:
            if i['SSID'] == "":
                continue
            self.add_network(i)

        self.networks_widget.show_all()
        
        return False


    def add_network(self, network):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        test_label = Gtk.Label(label=network['SSID'])
        test_label1 = Gtk.Label(label=f'{network["signal"]}%')
        test_button = self._gtk.Button("load", None, "color3", .8)
        test_button.set_hexpand(False)
        test_button.set_halign(Gtk.Align.END)

        hbox.pack_start(test_label, False, False, 0)
        hbox.pack_start(test_label1, True, True, 0)
        hbox.pack_end(test_button, False, False, 0)

        self.networks_widget.add(hbox)

    def reload_networks(self):
        self.wifi.get_networks(True)
    
    def remove_network(self, network):
        pass

    def activate(self):
        if self.initialized:
            pass

    def deactivate(self):
        pass
