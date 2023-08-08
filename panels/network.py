import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from ks_includes.screen_panel import ScreenPanel
from ks_includes.Wifi_Utils import wifi_utils

class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.initialized = False
        self.wifi = None
        self.connected_network = None
        self.networks_saved = []
        self.signal_icon = []
        self.networks_scroll = None
        self.networks_widget = None
        self.networks_saved_widget = None
        self.status_thread = None
        self.connecting = None
        

        self.init_mainframe()

    def init_mainframe(self): ## TODO: benchmark grid vs box?
        """ Initializes the mainframe Widget """
        main_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content.add(main_frame)

        self.wifi = self._screen.wifi
        ip = self.wifi.get_ip_address()

        # --- Initialize icons for wifi siganl --- 
        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-low", 50, 50)
        self.signal_icon.append(pixbuf)

        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-med", 50, 50)
        self.signal_icon.append(pixbuf)

        pixbuf = self._gtk.PixbufFromIcon("wifi-signal-high", 50, 50)
        self.signal_icon.append(pixbuf)


        ### --- SETUP CONTROL BOX --- ###
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        control_box.set_vexpand(False)

        wifi_toggle_label = Gtk.Label(label="Wifi: ")
        wifi_toggle_label.set_margin_start(20)

        wifi_toggle = Gtk.Switch()
        wifi_toggle.set_active(self.wifi.get_wifi_state())
        wifi_toggle.set_hexpand(False)
        wifi_toggle.set_vexpand(False)
        wifi_toggle.set_valign(Gtk.Align.CENTER)
        wifi_toggle.connect("state_set", self.toggle_wifi)


        reload_networks_button = self._gtk.Button("refresh", None, "color1", .66)                                                                                                                                   
        reload_networks_button.connect("clicked", self.reload_networks)
        reload_networks_button.set_hexpand(False)


        self.label_ip_address = Gtk.Label(label=ip)
        self.label_ip_address.set_halign(Gtk.Align.CENTER)

        control_box.pack_start(wifi_toggle_label, False, False, 0)
        control_box.pack_start(wifi_toggle, False, False, 0)
        control_box.pack_start(self.label_ip_address, True, False, 0)
        control_box.pack_end(reload_networks_button, False, False, 0)


        main_frame.add(control_box)

        
        ### ---- SETUP NETWORKS SCROLL WINDOW --- ###
        self.networks_scroll = self._gtk.ScrolledWindow()
        networks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.networks_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.networks_saved_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        networks_box.add(self.networks_widget)
        networks_box.add(self.networks_saved_widget)
        self.networks_scroll.add(networks_box)

        main_frame.add(self.networks_scroll)

        main_frame.connect("focus-in-event", self._screen.remove_keyboard)
        main_frame.show_all()

        self.networks_saved = self.wifi.get_saved_networks()

        self.initialized = True

        self.status_thread = GLib.timeout_add(25, self.wifi._on_ap_change, self.connection_error_handler)

        GLib.idle_add(self.update_networks)
    
    def remove_duplicates(self, list, key): ## Room for optimization if needed
        """ Removes Duplicate enteries (Access point repeaters) from the list.
         Since the list is sorted by signal beforehands there's no need to worry about choosing the strongest AP """

        memo = set()
        res = []
        for sub in list:    
            if(sub[key] not in memo):
                res.append(sub)

                memo.add(sub[key])

        return res

        
    def toggle_wifi(self, switch, state):
        """ Turns the wifi on or off """

        if switch.get_active():
            self.wifi.toggle_wifi(True)
            GLib.timeout_add_seconds(2, self.update_networks) ## wifi takes time to wakeup...
            GLib.timeout_add_seconds(5, self.update_base_ip)
        else:
            self.wifi.toggle_wifi(False)

             ## discard the scan
            net_widget = self.networks_widget
            any(net_widget.remove(child) for child in self.networks_widget.get_children())
            self.networks_widget.show_all()

            ## Update the IP
            GLib.timeout_add_seconds(2, self.update_base_ip)

    def update_networks(self):
        """ Updates the GUI with wifi networks both scanned and saved to the device """
        self.wifi.request_scan()

        ## Delete previous scan from GUI
        net_widget = self.networks_widget
        any(net_widget.remove(child) for child in self.networks_widget.get_children())

        saved_net_widget = self.networks_saved_widget
        any(saved_net_widget.remove(child) for child in saved_net_widget.get_children())


        network_list = self.wifi.get_networks(True)

        # Temporary solution for NM first scan nonsense.
        if(len(network_list) <= 2):
            network_list = self.wifi.update_aps(True)

        if(not network_list):
            logging.info("Could not find any wifi_networks...")
            return False
            
        ## Add Saved and Known networks first
        
        ### Create priority for sorting. (make function? returning and re assigning might be slower)
        self.connected_network = self.wifi.get_current_connected()
        if self.connected_network is None:
            connected_ssid = "  " #Hacky way of not doing Try, faster in thoery vs Try, am I going mad with performance?
        else:
            connected_ssid = self.connected_network['SSID']
        

        ## Prioritize the network connections while removing the connections in reach from the saved section
        saved_not_found = self.networks_saved[:] ##Quick way to make a hard copy.
        for net in network_list:
            ssid = net['SSID']
            if ssid == connected_ssid:
                net['priority'] = 0
                for known_net in saved_not_found:
                    if known_net['SSID'] == ssid:
                        saved_not_found.remove(known_net)
            else:
                net['priority'] = 2
                for known_net in saved_not_found:
                    if known_net['SSID'] == ssid:
                        net['priority'] = 1
                        saved_not_found.remove(known_net)

        network_list = self.remove_duplicates(network_list, 'SSID')

        network_list = sorted(network_list, key=lambda x: x['priority']) 

    
        for i in network_list:
            if i['SSID'] == "": ## Don't show hidden networks.
                continue
            
            self.add_network(i)
        
        ### Add saved not found networks
        if len(saved_not_found) > 0:
            saved_label = Gtk.Label(label="Saved networks")
            saved_label.set_halign(Gtk.Align.CENTER)
            self.networks_saved_widget.add(saved_label)

            for i in saved_not_found:
                self.add_network_saved(i)

        net_widget.show_all()
        self.networks_saved_widget.show_all()
        
        return False # Returns False so that timeout_add doesn't continiously run it if used as a delay
        
    def add_network_saved(self, network):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label_ssid = Gtk.Label(label=network['SSID'])
        label_ssid.set_hexpand(False)
        label_ssid.set_vexpand(False)
        button_forget = self._gtk.Button("delete", None, "color3", 0.66)
        button_forget.set_hexpand(False)
        button_forget.set_vexpand(False)
        button_forget.connect("clicked", self.forget_network, network['UUID'])

        hbox.pack_start(label_ssid, False, False, 0)
        hbox.pack_end(button_forget, False, False, 0)
        self.networks_saved_widget.add(hbox)

    def forget_network(self, button, ssid):
        self.wifi.delete_connection_ssid(ssid)
        print("Print function to just delaty, temp fix and weird issue lol") ## remove...
        self.networks_saved = self.wifi.get_saved_networks()
        GLib.timeout_add_seconds(1, self.update_networks)
        GLib.timeout_add_seconds(2, self.update_base_ip)

    
    def add_network(self, network):
        """ Add Wifi network to the GUI  """
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.set_vexpand(False)
        
        logging.info(f"Connecting: {self.connecting}, current: {network['SSID']}")
        if(network['priority'] == 0):
            if network['SSID'] == self.connecting:
                label_name = f"{network['SSID']} (Connecting....)"
            else:
                label_name = f"{network['SSID']} (Connected)"
        elif network['priority'] == 1:
            label_name = f"{network['SSID']} (Saved)"
        else:
            label_name = network['SSID']

        ssid_label = Gtk.Label(label=label_name)

        connect_button = self._gtk.Button("load", None, "color3", .8)
        connect_button.set_hexpand(False)
        connect_button.set_halign(Gtk.Align.END)
        

        if(network['priority'] == 1):
            connect_button.connect("clicked", self.connect_network, network['SSID'])
        elif(network['priority'] == 0):
            connect_button.connect("clicked", self.disconnect_network, network['SSID'])
        else:
            connect_button.connect("clicked", self.network_connection_panel, network['SSID'])
        
        button_forget = None
        if(network['priority'] <= 1):
            button_forget = self._gtk.Button("delete", None, "color3", 0.66)
            button_forget.set_hexpand(False)
            button_forget.set_vexpand(False)
            button_forget.connect("clicked", self.forget_network, network['SSID'])

        ## Signal Icons
        strength = 0

        if(network['signal'] >= 65):
            strength = 2
        elif(network['signal'] >= 40):
            strength = 1

        signal_icon =  Gtk.Image.new_from_pixbuf(self.signal_icon[strength])

        hbox.pack_start(signal_icon, False, False, 8)
        hbox.pack_start(ssid_label, False, False, 0)
        hbox.pack_end(connect_button, False, False, 0)
        if button_forget is not None:
            hbox.pack_end(button_forget, False, False, 0)

        self.networks_widget.add(hbox)
        
    
    def network_connection_panel(self, button, ssid):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label=f'{ssid} PSWD:')
        password_entry = Gtk.Entry()
        password_entry.set_hexpand(True)
        password_entry.set_vexpand(False)
        password_entry.set_valign(Gtk.Align.CENTER)
        
        button_save = self._gtk.Button("sd", _("Save"), "color3")
        button_save.set_hexpand(False)
        button_save.connect("clicked", self.save_network, ssid, password_entry)

        hbox.add(label)
        hbox.add(password_entry)
        hbox.add(button_save)

        self.networks_widget.add(hbox)
        self.networks_widget.reorder_child(hbox, 0)

        self.networks_scroll.get_vscrollbar().get_adjustment().set_value(0)

        self._screen.show_keyboard(password_entry)
        password_entry.grab_focus_without_selecting()

    def save_network(self, button, ssid, psk_entery, connect = True):
        self._screen.show_popup_message(f"Connecting to {ssid} ...")
        self.connecting = ssid
        self.wifi.add_connection(ssid, psk_entery.get_text())
        children = self.networks_widget.get_children()
        self.networks_widget.remove(children[0])
        self._screen.remove_keyboard()
        GLib.timeout_add_seconds(2, self.update_base_ip)
        GLib.timeout_add_seconds(1, self.update_networks)

    def connect_network(self, button, ssid):
        self.connecting = ssid
        logging.info(f"Connecting to {ssid} ...")
        self._screen.show_popup_message(f"Connecting to {ssid} ...")
        status = self.wifi.connect(ssid)
        
        GLib.timeout_add_seconds(2, self.update_networks)
        
    def disconnect_network(self, button, ssid):
        logging.info("Not implemented feature, disconnect network")


    def reload_networks(self, button):
        self.update_networks()
        GLib.timeout_add_seconds(2, self.update_base_ip)
  
    
    def remove_network(self, network):
        pass

    def update_base_ip(self):
        self._screen.update_ip_adress()
        ip = self.wifi.get_ip_address()
        self.label_ip_address.set_label(ip)
        return False
    
    def back(self):
        pass

        
    def activate(self):
        if self.initialized:
            pass

    def deactivate(self):
        GLib.source_remove(self.status_thread)
        pass

    def connection_error_handler(self, msg):
        logging.info(F"Device state changed {msg}")
        if msg[0] == self.wifi.enums.DeviceState.FAILED:
            self._screen.show_popup_message(f"Could not connect to {self.connecting}.")
            self.wifi.delete_connection_ssid(self.connecting)
            self.connecting = None
            GLib.timeout_add_seconds(2, self.update_networks)
        elif msg[0] == self.wifi.enums.DeviceState.ACTIVATED:
            self._screen.show_popup_message(f"Connected")
            GLib.timeout_add_seconds(1, self.update_networks)
            self.connecting = None