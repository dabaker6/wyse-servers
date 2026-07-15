#dot source the env.ps1 file to load the environment variables
. .\env.ps1

#Check if the current SSID is the home SSID and start/stop the wireguard service accordingly
$currentSSID = (Get-NetConnectionProfile -InterfaceAlias "WiFi" -ErrorAction SilentlyContinue).Name
#Get the WireGuard service for the specified tunnel
$service = Get-Service $serviceName -ErrorAction SilentlyContinue

if($currentSSID -match $homeSSID) {
    # If the current SSID matches the home SSID, stop the WireGuard service if it is running
    if($service -and $service.Status -eq "Running") {
        Stop-Service $serviceName -ErrorAction SilentlyContinue
    }
    # If the service does not exist, do nothing
} else {
    # If the current SSID does not match the home SSID, start the WireGuard service if it is stopped or install it if it does not exist
    if($service -and $service.Status -eq "Stopped") {
        Start-Service $serviceName -ErrorAction SilentlyContinue
    } elseif(-not $service) {
        & $pathToWireguard /installtunnelservice $confLocation
    }    
}