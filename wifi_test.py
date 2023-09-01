from sdbus_async.networkmanager import (
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

import time
import asyncio
from sdbus import sd_bus_open_system, set_default_bus
from uuid import uuid4
import logging

# TODO: IMPLEMNT SIGNAL HANDLING AND OWN SDBUS IMPLEMENTATION (Will require C helpers, not worth it for now)


class wifi_utils_core:
    def __init__(self):
        self.system_bus = sd_bus_open_system()  # Set the default system bus
        set_default_bus(self.system_bus)

        self.nm = None
        self.nm_settings = None
        self.wlan_device = None
        self.wlan_device_path = None
        self.available_networks = []
        self.saved_networks = []
        self.signalthresh = 20 # Will not add networks below the treshold
        self.wlan_device_name = None


    async def init(self):
        print("Intiializing yawn")
        self.nm = NetworkManager(self.system_bus)
        self.nm_settings = NetworkManagerSettings(self.system_bus)

        await self.getWlanDevice()
        self.wlan_device.state_changed
    async def getWlanDevice(self):
        """Initialize and find the WLAN device. Finds the first device that is of type "Wlan"."""

        device_paths = await self.nm.get_devices()
        for device_path in device_paths:
            device = NetworkDeviceWireless(device_path, self.system_bus)
            dev_type = await device.device_type
            if(dev_type == 2): # type 2 is wlan according to docs
                self.wlan_device = device
                self.wlan_device_name = await device.interface
                self.wlan_device_path =  device_path

    async def request_scan(self):
        """Requests a fresh scan from Network Manager"""
        #Remove await if not needed after.
        await self.wlan_device.request_scan({})
        
    async def update_aps(self, scan = False) -> None:
        """This method updates the internal list of nearby access points"""
        if(scan):
            await self.request_scan()

        acess_points = [] #reset old networks.
        results = await self.wlan_device.get_all_access_points()
        
        for res in results:
            ap = AccessPoint(res)
            if(await ap.strength >=  self.signalthresh): # Dismiss if network has weak signal
                network = await self.ap_to_network(ap)
                # network['freq'] = ap.frequency #CB1 does not support 5Ghz
                acess_points.append(network)
            
        self.available_networks = sorted(acess_points, key=lambda d: d['signal'], reverse=True) 

    async def get_networks(self, update = True):
        """Returns a list of Networks(Dictionary)"""
        if(update):
            await self.update_aps(update)
            
        return self.available_networks
        

    async def get_saved_networks(self, update = True):
        """Returns a list of saved wireless network connections"""
        saved_network_paths = await self.nm_settings.list_connections()
        self.saved_networks = []

        for netpath in saved_network_paths:
            saved_con = NetworkConnectionSettings(netpath, self.system_bus)
            con_settings = await saved_con.get_settings()
            ### 'type': ('s', '802-11-wireless') ###
            if con_settings['connection']['type'][1] == "802-11-wireless":
                self.saved_networks.append({'SSID': con_settings['802-11-wireless']['ssid'][1].decode(),
                                            'UUID': con_settings['connection']['uuid'][1]})

        
        return self.saved_networks
        


    async def add_connection(self, ssid, passwd, autconnect = True, connect=True):
        """ Adds a connection to networkmanager and system
        SSID: the network SSID
        passwd: Password"""
        existing_network = NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid)
        if existing_network:
            await self.delete_connection_path(existing_network[0])

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

        nmSettings = self.nm_settings
        try:
            nmSettings.add_connection(properties)
        except:
            return "Password type is incorrect."
        
        if(connect):
            return self.connect(ssid)

    async def connect(self, ssid):
        connection = NetworkManagerSettings(self.system_bus).get_connections_by_id(ssid)

        if len(connection) == 0:
            return "Error, network not found"
        
        await self.nm.activate_connection(connection[0])


    async def ap_to_network(self, ap):
        network = dict()
        ssid = await ap.ssid
        network['SSID'] = ssid.decode("utf-8") 
        network['signal'] = await ap.strength
        network['security'] = await ap.flags
        return network


    def get_wifi_state(self):
        return self.nm.wireless_enabled
    
    def toggle_wifi(self, state):
            self.nm.wireless_enabled = state

    async def get_current_connected(self):
        curr = self.wlan_device.active_access_point
        if(len(curr) >= 5):
            curr = AccessPoint(curr, self.system_bus)
            curr = await self.ap_to_network(curr)
            return curr
    
    def delete_connection_path(self, path):
        "Takes connection path and deletes it"
        NetworkConnectionSettings(path, self.system_bus).delete()

    def delete_connection_uuid(self, uuid):
        self.nm_settings.delete_connection_by_uuid(uuid)

    def delete_connection_ssid(self, ssid):
        connection = self.nm_settingself.get_connections_by_id(ssid)
        self.delete_connection_path(connection)

    def is_valid_path(self, path):
        """ Checks if provided path is valid, NM sometimes returns "/" or bad adresses instead of none"""
        return len(path) > 5

    def get_ip_address(self):
        """Get the IP address of the current primary network"""
    
        # Get the active connection
        active_connection_path = self.nm.primary_connection

        if not self.is_valid_path(active_connection_path):
            return "" # No active connection
        
        active_connection = ActiveConnection(active_connection_path, self.system_bus)
        ip_info = IPv4Config(active_connection.ip4_config, self.system_bus)

        return ip_info.address_data[0]['address'][1]

    async def _testing(self):
        print("in testing")
        await self.init()
        print(await self.get_networks(True))

    async def _printnets(self):
        while(True) :
            print(await self.get_networks(True))
            await asyncio.sleep(2)

    async def _on_ap_state_changed(self, bunny):
        async for x in self.wlan_device.state_changed:
            print('changed: ', x)
            bunny()

    async def _on_ap_added(self, bunny):
        async for x in self.wlan_device.access_point_added:
            print('Added ', x)
            bunny()

    async def _on_ap_removed(self, bunny):
        async for x in self.wlan_device.access_point_removed:
            print('removed ', x)
            bunny()
    


    async def _update_aps(self):
        while(True):
            await self.request_scan()
            await asyncio.sleep(5)

class wifi_utils(wifi_utils_core):
    def __init__(self):
        import time
        super().__init__()
        self.loop = None
        self.tasks =[]

    async def init_boy(self, bunny):
        print("innit boi")
        asyncio.create_task(self._async_main(bunny))
        # loop.create_task(self._async_main(bunny))

    def print_bun(self, bunny):
        print("BUnnnnasndfasnfdsandf")
        task = asyncio.to_thread(self._async_main, bunny)

    async def _async_main(self, bunny = print):
        print("I'm in main")
        self.loop = asyncio.get_event_loop()
        t1 = self.loop.create_task(self._testing())
        await t1
        print("out o testing")
        self.tasks.append(self.loop.create_task(self._on_ap_state_changed(bunny)))
        self.tasks.append(self.loop.create_task(self._on_ap_added(bunny)))
        self.tasks.append(self.loop.create_task(self._on_ap_removed(bunny)))
        self.tasks.append(self.loop.create_task(self._update_aps()))
        self.tasks.append(self.loop.create_task(self._keepalive()))

    async def _keepalive(self):
        while (True):
            print("snore sleeping")
            await asyncio.sleep(2)

    def __del__(self):
        print("Oh no i'm getting deleted X_X")
        try:
            tasks = self.tasks
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                # give canceled tasks the last chance to run
                t.cancel()
        finally:
            pass
        
def helko():
    loop = asyncio.new_event_loop()
    loop.create_task(fuck())
    loop.run_forever()
    print(loop)

async def fuck():
    while(True):
        print("Fuck")
        await asyncio.sleep(0.5)

class bunnygirl:
    def __init__(self):
        self.networks = []

    def _on_signal(self, text=""):
        print("i am the bunny" , text)

    def _update_networks(self, networks):
        self.networks = networks
        print("oi m8, got netwroks!")
        
if __name__ == "__main__":
    # logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
    import time
    bunny = bunnygirl()
    goop = wifi_utils()
    loop = asyncio.get_event_loop()
    print(loop)
    tred = asyncio.to_thread(helko)
    asyncio.run(tred)
    print("I'm outside!")
    time.sleep(20)
    print("Time to go to bed zzzz")
    
