#Set variables
$homeSSID = "Speak Friend and Enter" #SSID name
$tunnelName = "peer2" #name of tunnel in wireguard
$confLocation = "C:\Users\dabak\source\Tools\wireguard scripts\${tunnelName}.conf" #location of the wireguard config file
$pathToWireguard = "C:\Program Files\Wireguard\Wireguard.exe" #location of wireguard.exe
$serviceName = "WireGuardTunnel$"+$tunnelName #name of the wireguard service for the specified tunnel