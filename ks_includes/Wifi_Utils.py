from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkConnectionSettings,
    NetworkManagerSettings,
    AccessPoint,
    NetworkManagerConnectionProperties,
)
from sdbus import sd_bus_open_system, set_default_bus
from uuid import uuid4

# TODO: IMPLEMNT SIGNAL HANDLING AND OWN SDBUS IMPLEMENTATION (Will require C helpers, not worth it for now)

class wifi_utils:

    def __init__(self):
        self.system_bus = sd_bus_open_system()  # Set the default system bus
        set_default_bus(self.system_bus)

        self.nm = NetworkManager()
        self.wlan_device = None
        self.available_networks = []
        self.saved_network_paths = []
        self.signalthresh = 20 # Will not add networks below the treshold
        self.wlan_device_name = ""

        self.getWlanDevice()

    def getWlanDevice(self):
        """Initialize and find the WLAN device. Finds the first device that is of type "Wlan"."""

        device_paths = self.nm.get_devices()
        for device_path in device_paths:
            device = NetworkDeviceWireless(device_path)
            dev_type = device.device_type
            if(dev_type == 2): # type 2 is wlan according to docs
                self.wlan_device = device
                self.wlan_device_name = device.interface

    # Requests a fresh scan from Network Manager
    def request_scan(self):
        results = self.wlan_device.request_scan({})
        
    #This method updates the internal list of nearby access points
    def update_aps(self, scan = False) -> None:
        if(scan):
            self.rescan_networks()

        acess_points = [] #reset old networks.
        results = self.wlan_device.get_all_access_points()
        
        for res in results:
            ap = AccessPoint(res, self.system_bus)
            if(ap.strength >= self.signalthresh): # Dismiss if network has weak signal
                network = dict()
                network['SSID'] = ap.ssid.decode("utf-8") 
                network['signal'] = ap.strength
                network['security'] = ap.flags
                # network['freq'] = ap.frequency #CB1 does not support 5Ghz
                acess_points.append(network)
            
        self.available_networks = sorted(acess_points, key=lambda d: d['signal'], reverse=True) 

    #Returns a list of networks available
    def get_networks(self, update = True):
            if(update):
                self.update_aps()
                
            return self.available_networks
        
    # Adds a path list of existing connections to saved_network_paths
    def update_saved_networks(self):
        self.saved_network_paths = NetworkManagerSettings().list_connections()

    def add_connection(self, ssid, passwd, autconnect = True, connect=True):
        """ Adds a connection to networkmanager and system
        SSID: the network SSID"""
        if NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid):
            #TODO: Implement delete. reinstall conn on duplicate
            return

        #Generate properties
        properties: NetworkManagerConnectionProperties = {
            "connection": {
                "id": ("s", ssid),
                "uuid": ("s", str(uuid4())),
                "type": ("s", "802-11-wireless"),
                "autoconnect": ("b", autconnect),
                "interface-name": ("s", self.wlan_device_name)
            },
            "802-11-wireless": {
                "mode": ("s", "infrastructure"),
                "security": ("s", "802-11-wireless-security"),
                "ssid": ("ay", ssid.encode("utf-8")),
            },
            "802-11-wireless-security": {
                "key-mgmt": ("s", "wpa-psk"),
                "auth-alg": ("s", "open"),
                "psk": ("s", passwd),
            },
            "ipv4": {"method": ("s", "auto")},
            "ipv6": {"method": ("s", "auto")},
        }

        nmSettings = NetworkManagerSettings(self.system_bus)
        nmSettings.add_connection(properties)
        if(connect):
            self.connect(ssid)


    def toggle_wifi(self, state):
        pass


    def delete(self, network):
        "Takes network with ['UUID'], deletes it from the connections"
        NetworkManagerSettings().delete_connection_by_uuid(network['uuid'])

    def connect(self, ssid):
        connection = NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid)

        if connection == None:
            print("Error, could not find network")
            return
        
        self.nm.activate_connection(connection[0])
        return

