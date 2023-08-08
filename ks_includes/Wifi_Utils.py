from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkConnectionSettings,
    NetworkManagerSettings,
    AccessPoint,
    NetworkManagerConnectionProperties,
    IPv4Config,
    ActiveConnection,
    enums,
)
from sdbus import sd_bus_open_system, set_default_bus
from uuid import uuid4
import logging, time

# TODO: IMPLEMNT SIGNAL HANDLING AND OWN SDBUS IMPLEMENTATION (Will require C helpers, not worth it for now)

class wifi_utils:

    def __init__(self):
        self.system_bus = sd_bus_open_system()  # Set the default system bus
        set_default_bus(self.system_bus)

        self.nm = NetworkManager()
        self.nm_settings = NetworkManagerSettings()
        self.wlan_device = None
        self.wlan_device_path = None
        self.available_networks = []
        self.saved_networks = []
        self.signalthresh = 20 # Will not add networks below the treshold
        self.wlan_device_name = None
        self.run_loops = False
        self.enums = enums
        self.last_state = None

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
                self.wlan_device_path = device_path
                self.last_state = device.state_reason

    def request_scan(self):
        """Requests a fresh scan from Network Manager"""
        results = self.wlan_device.request_scan({})
        
    def update_aps(self, scan = False) -> None:
        """This method updates the internal list of nearby access points"""
        if(scan):
            self.request_scan()

        acess_points = [] #reset old networks.
        results = self.wlan_device.get_all_access_points()
        
        for res in results:
            ap = AccessPoint(res, self.system_bus)
            if(ap.strength >= self.signalthresh): # Dismiss if network has weak signal
                network = self.ap_to_network(ap)
                # network['freq'] = ap.frequency #CB1 does not support 5Ghz
                acess_points.append(network)
            
        self.available_networks = sorted(acess_points, key=lambda d: d['signal'], reverse=True) 

    def get_networks(self, update = True):
        """Returns a list of Networks(Dictionary)"""
        if(update):
            self.update_aps()
            
        return self.available_networks
        

    def get_saved_networks(self, update = True):
        """Returns a list of saved wireless network connections"""
        saved_network_paths = NetworkManagerSettings().list_connections()
        self.saved_networks = []

        for netpath in saved_network_paths:
            saved_con = NetworkConnectionSettings(netpath)
            con_settings = saved_con.get_settings()
            ### 'type': ('s', '802-11-wireless') ###
            if con_settings['connection']['type'][1] == "802-11-wireless":
                self.saved_networks.append({'SSID': con_settings['802-11-wireless']['ssid'][1].decode(),
                                            'UUID': con_settings['connection']['uuid'][1]})

        
        return self.saved_networks
    
    def _on_ap_change(self, function):

        if not self.wlan_device.state_reason == self.last_state:
            self.last_state = self.wlan_device.state_reason
            # logging.info(f"Device state changed to : {self.last_state}")
            function(self.last_state)
            
        return True
            


    def add_connection(self, ssid, passwd, autconnect = True, connect=True):
        """ Adds a connection to networkmanager and system
        SSID: the network SSID
        passwd: Password"""
        existing_network = NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid)
        if existing_network:
            self.delete_connection_path(existing_network[0])

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
        try:
            nmSettings.add_connection(properties)
        except:
            return "Password type is incorrect."
        
        if(connect):
            return self.connect(ssid)

    def connect(self, ssid):
        connection = NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid)

        if len(connection) == 0:
            return "Error, network not found"
        
        self.nm.activate_connection(connection[0])


    def ap_to_network(self, ap):
        network = dict()
        network['SSID'] = ap.ssid.decode("utf-8") 
        network['signal'] = ap.strength
        network['security'] = ap.flags
        return network


    def get_wifi_state(self):
        return self.nm.wireless_enabled
    
    def toggle_wifi(self, state):
            self.nm.wireless_enabled = state

    def get_current_connected(self):
        curr = self.wlan_device.active_access_point
        if(len(curr) >= 5):
            curr = AccessPoint(curr)
            curr = self.ap_to_network(curr)
            return curr
    
    def delete_connection_path(self, path):
        "Takes connection path and deletes it"
        NetworkConnectionSettings(path).delete()

    def delete_connection_uuid(self, uuid):
        NetworkManagerSettings().delete_connection_by_uuid(uuid)

    def delete_connection_ssid(self, ssid):
        connection = self.nm_settings.get_connections_by_id(ssid)
        for con in connection:
            self.delete_connection_path(con)

    def is_valid_path(self, path):
        """ Checks if provided path is valid, NM sometimes returns "/" or bad adresses instead of none"""
        return len(path) > 5

    def get_ip_address(self):
        """Get the IP address of the current primary network"""
    
        # Get the active connection
        active_connection_path = self.nm.primary_connection

        if not self.is_valid_path(active_connection_path):
            return "" # No active connection
        
        active_connection = ActiveConnection(active_connection_path)
        ip_info = IPv4Config(active_connection.ip4_config)

        return ip_info.address_data[0]['address'][1]

    def _testing(self):
        import time
        try:
            print(self.add_connection("Amy's Note 10", "Ameliaishere4you"))
        except Exception as excpetion:
            print(excpetion)
        
        for i in range(400):
            dev_reasons = self.wlan_device.state_reason
            nm_reasons = self.nm.state

            logging.info(f"wlan_device reasons: {dev_reasons}")
            logging.info(f"networkManager reasons: {nm_reasons}")
            time.sleep(0.1)
        

        
if __name__ == "__main__":
    logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
    wifi = wifi_utils()
    wifi._testing()
