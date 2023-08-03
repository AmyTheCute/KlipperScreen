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

        main_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content.add(main_frame)

        self.wifi = wifi_utils()
        ip = "1.2.3.4"

        self.networks = []
        self.networks_saved = []

        # --- Initialize icons for wifi siganl --- #
        self.signal_icon = []
        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-low", 64, 64)
        self.signal_icon.append(pixbuf)

        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-med", 64, 64)
        self.signal_icon.append(pixbuf)

        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-high", 64, 64)
        self.signal_icon.append(pixbuf)


        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        control_box.set_vexpand(False)

        ### --- SETUP CONTROL BOX --- ###
        main_frame.add(control_box)
        wifi_toggle_label = Gtk.Label(label="Wifi: ")
        wifi_toggle_label.set_margin_start(20)

        swifi_toggle = Gtk.Switch()
        swifi_toggle.connect("notify::active", self.toggle_wifi)

        ## TODO: Add interface: add connected wifi on top with special treatment.


        reload_networks_button = self._gtk.Button("refresh", None, "color1", .66)                                                                                                                                   
        reload_networks_button.connect("clicked", self.reload_networks)
        reload_networks_button.set_hexpand(False)

        control_box.add(wifi_toggle_label)
        control_box.add(swifi_toggle)
        control_box.pack_end(reload_networks_button, False, False, 0)

        
        ### ---- SETUP NETWORKS SCROLL WINDOW --- ###
        networks_scroll = self._gtk.ScrolledWindow()
        self.networks_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        networks_scroll.add(self.networks_widget)
        main_frame.add(networks_scroll)

        main_frame.connect("focus-in-event", self._screen.remove_keyboard)
        
        self.initialized = True

        GLib.idle_add(self.update_networks)
        # GLib.timeout_add_seconds(4, self.update_networks)
        
    def toggle_wifi(self, switch, state):
        if switch.get_active():
            self.wifi.toggle_wifi(True)
        else:
            self.wifi.toggle_wifi(False)

    def update_networks(self):
        self.wifi.request_scan()
        network_list = self.wifi.get_networks(True)

        for child in self.networks_widget.get_children():
            self.networks_widget.remove(child)

        for i in network_list:
            if i['SSID'] == "":
                continue
            self.add_network(i)

        self.networks_widget.show_all()
        
        return False
    
    def network_connection_panel(self, button, ssid):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label=f'{ssid} PSWD:')
        password_entry = Gtk.Entry()
        password_entry.set_hexpand(True)
        password_entry.grab_focus_without_selecting()
        
        button_save = self._gtk.Button("sd", _("Save"), "color3")

        hbox.add(label)
        hbox.add(password_entry)
        hbox.add(button_save)

        self.networks_widget.add(hbox)
        self.networks_widget.reorder_child(hbox, 0)

        self._screen.show_keyboard(password_entry)

    def save_network(self, ssid, connect = True):
        pass

    def add_network(self, network):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        ssid_label = Gtk.Label(label=network['SSID'])

        connect_button = self._gtk.Button("load", None, "color3", .8)
        connect_button.set_hexpand(False)
        connect_button.set_halign(Gtk.Align.END)

        connect_button.connect("clicked", self.network_connection_panel, network['SSID'])
        
        strength = 0

        if(network['signal'] >= 65):
            strength = 2
        elif(network['signal'] >= 40):
            strength = 1

        signal_icon =  Gtk.Image.new_from_pixbuf(self.signal_icon[strength])

        hbox.pack_start(signal_icon, False, False, 0)
        hbox.pack_start(ssid_label, False, False, 0)
        hbox.pack_end(connect_button, False, False, 0)

        self.networks_widget.add(hbox)

    def reload_networks(self, button):
        self.update_networks()
    
    def remove_network(self, network):
        pass

    def activate(self):
        if self.initialized:
            pass

    def deactivate(self):
        pass
