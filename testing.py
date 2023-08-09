from ks_includes.Wifi_Utils import wifi_utils

wifi = wifi_utils()

wifi.request_scan()
print(wifi.get_networks(True))