# Setup Pi-Hole, Wireguard and Unbound

## Step One: Server Selection

### Wyse 5070
> 
    - Pentium Silver J5005
    - 8GB RAM
    - 32GB M.2 NVMe drive
- Chosen to ensure sufficient RAM, a non MMC drive and enough processing power to handle further exapnsion, e.g. plex server, K3s etc...
## Step Two: Prerequesites 
### Install OS 
- Ubuntu Server for headless use.
- https://ubuntu.com/tutorials/install-ubuntu-server
- On storage, by default the installer when using Logical Volume Management (LVM), allocates only about half of the total disk space to the main root directory (/). It leaves the rest completely unallocated so system administrators can create snapshots or add other partitions later.
- As I want LUKS, I need to keep LVM, but increase the partition size during install. In used devices -> Ubuntu-lv -> edit -> increase size to max
- https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu
### Set static IP
- Need to ensure static IP is set
```yml
network:
  version: 2
  ethernets:
    enp1s0:
      match:
        macaddress: <wyse-mac-address>
      dhcp4: no
      dhcp6: no
      addresses:
        - <static-ip>/24
      routes:
        - to: default
          via: <router-ip>
      nameservers:
        addresses:
          - <router-ip>
    <unused-usb-ethernet-adapters>
      dhcp4: no
      dhcp6: no
      optional: true
```
- USB adapters were causing slow boot times so set to ```optional: true```

### Harden
#### Non root user
```bash
adduser <user_name>
usermod -aG sudo <user_name>
```
- Create non root user (Ubuntu server can do this during setup) and add them to sudo group
#### Set up keys for SSH
- From windows
```powershell
ssh-keygen -t ed25519
type id_ed25519.pub | ssh user@{remote IP} "cat >> .ssh/authorized_keys"
```
- Use a modern algorithm as a new server.
- Prompts save location and passphrase 
- Then copy to server
#### Turn off password auth and alter default port
- Instructions from https://psyonik.tech/posts/a-guide-for-wireguard-vpn-setup-with-pi-hole-adblock-and-unbound-dns/
- open ssh daemon config
```bash
sudo nano /etc/ssh/sshd_config
```
- Update file with following commands
```apacheconf 
port <required port>
AddressFamily inet # SSH Service will only listen to IPv4 addresses
PermitRootLogin no # disable root login
PubkeyAuthentication yes # only allow SSH key-based authentication  
AuthorizedKeysFile .ssh/authorized_keys # file that contains allowed public keys  
PasswordAuthentication no # do not allow password auth  
PermitEmptyPasswords no # do not allow empty passwords 
ChallengeResponseAuthentication no # Specifies if challenge-response auth is allowed
UsePAM no # disable authentication through PAM (Pluggable Authentication Module)
```
- Difference from instructions is that in latest Ubuntu port is configured via sshd.conf
- Restart ssh daemon and ssh socket
```bash
sudo systemctl daemon-reload
sudo systemctl restart ssh.socket
```
- Confirm
```bash
sudo sshd -T | grep passwordauthentication
```
- If still set to yes then:
```bash
sudo nano /etc/ssh/sshd_config.d/50-cloud-init.conf
```
- Set PasswordAuthentication no
- See https://www.thadaw.com/posts/disable-password-ubuntu-2025?id=6nnlqym for details

- I have multiple hosts and store keys in separate folders
- Need a config file to point to the correct private key saved in the .ssh folder
```
Host homelab
    Hostname <homelab-ip>
    IdentityFile "%USERPROFILE%\.ssh\homelab\id_ed25519"
    User <homelab-username>    

Host host2
    Hostname <host2-ip>
    IdentityFile "%USERPROFILE%\.ssh\<host2>\id_ed25519"
    User <host2-username>

Host *
    Port <>
    IdentitiesOnly yes
```
- IdentitiesOnly forces client to only use the specified key, Host * provides values for all hosts
- This is also useful as I can add dropbear too.
- Guide: https://linuxize.com/post/using-the-ssh-config-file/
#### UFW (Uncomplicated Firewall)
- Set up to allow SSH, enable it and check status
```bash
ufw enable
ufw status
```
- Update to open required ports
```bash
ufw allow from 192.168.0.0/24 to any port 80 proto tcp
ufw allow from 192.168.0.0/24 to any port 67 proto udp
ufw allow from 192.168.0.0/24 to any port 53
ufw allow 51820/udp
ufw allow <shh-port>/tcp
```
- pi-hole listens on port 80 for admin portal
- port 67 required for DHCP
- port 53 required DNS (TCP and UDP)
- these can be open and restricted to internal traffic
- wireguard (51820/udp) needs to be open to the internet
#### LUKS (Linux Unified Key Setup-on-disk-format)
- During install LVM with LUKS was selected, this requires a passphrase to be entered to unlock the drive on boot. As this is a headless set up then this isn't practical.
- Followed the excellent guide here: https://www.cyberciti.biz/security/how-to-unlock-luks-using-dropbear-ssh-keys-remotely-in-linux/
- Used dropbear to SSH server, which is loaded into initramfs to allow SSH connection during boot to unlock the disk, 
```bash
ssh -i $env:USERPROFILE/.ssh/id_ed25519 -p <port-number> -o "HostKeyAlgorithms=ssh-ed25519" root@<ip-of-server>
```
- during setup need the following IP config
```
IP=<wyse-static-IP>::<rooter-ip>:<subnet>:<hostname>:<adapter>:off
```
- This is the call required from windows
#### Unattended Upgrades
- Just turn on unattended upgrades for security packages
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades   # answer Yes
```
- The last line turns on the timers
- ensure ```/etc/apt/apt.conf.d/20auto-upgrades``` are both 1
```ini
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```
- Edit ```/etc/apt/apt.conf.d/50unattended-upgrades```
```ini
Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
        "${distro_id}ESMApps:${distro_codename}-apps-security";
        "${distro_id}ESM:${distro_codename}-infra-security";
//      "${distro_id}:${distro_codename}-updates";
};
```
- Uncomment these line, auto removes old kernals etc... and stops automatic reboots
```ini
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false"; 
```
- Updates that require a reboot will flag ```/var/run/reboot-required
- Check config
```bash
apt-config dump | grep -i unattended
```
- Dry run
```bash
sudo unattended-upgrade --dry-run --debug
```
 
### Fail2ban
- Help against bots scanning for SSH
```bash
sudo apt install fail2ban
```
- create local config
```bash
sudo nano /etc/fail2ban/jail.local
```
- update config
```ini
[sshd]
enabled = true
port = <ssh port>
maxretry = 3
bantime = 1h
findtime = 10m
```
### Docker
- Docker required, as all servies will run through docker container
- See https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04#step-2-executing-the-docker-command-without-sudo-optional for details
#### Install using kerings
---
```bash
sudo install -m 0755 -d /etc/apt/keyrings
```
- Adds directory with correct permissions (Owner can read, write, execute; group can read and execute, all users can read and execute)
```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
```
- Downloads Dockers public key, extra curl commands remove clutter, shows errors, and follows and redirects
- ```--dearmor``` removes armoured headers and converts to binary and then saves
- curl commands, ```-f``` fail silently on http errors ```-s``` silent mode ```-S``` shows errors messages (even in silent mode) ```-L``` follow redirects
```bash
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```
- Sets permissions of key so can be read by all users

```bash
echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```
- Constructs a string of architecture + GPG key + os + version
- Writes to file and clears from terminal
```bash
sudo apt update
apt-cache policy docker-ce
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
- Update package database 
- Ensure that the package is installed from Docker and not Ubuntu
- Install all required packages
#### Add user to docker group
```bash
sudo usermod -aG docker <username>
```
- Removes need to use sudo for docker commands
#### Ensure Docker starts on reboot
```bash
sudo nano /etc/systemd/system/homelab.service
```
```ini
[Unit]
Description=Homelab Docker Compose Stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/homelab
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
```
- Included in this tutorial https://www.uncommonengineer.com/docs/engineer/LAB/pihole-docker-unbound/#auto-start-on-boot
## Step Three: Set up Unbound, Pi-hole and Wireguard
- Main services run through docker compose
### Unbound
- Before using follow the steps at https://docs.pi-hole.net/guides/dns/unbound/#recommended-test-access-to-root-servers to check that unbound will work
- Create a config file `./unbound/unbound.conf`
```apacheconf 
server:
    # Ensure only logs errors
    verbosity: 1
    logfile: ""
    # Listens on local host
    interface: 127.0.0.1

    # Port to listen on
    port: 5335

    # Protocols
    do-ip4: yes
    do-udp: yes
    do-tcp: yes
    do-ip6: no
    prefer-ip6: no

    # Increase from default of 10 to mitigate WARNING: Connection error (127.0.0.1#5335): TCP
    # connection failed while receiving payload length from upstream (Connection prematurely
    # closed by remote server)
    # https://discourse.pi-hole.net/t/connection-error-127-0-0-1-5335-tcp-connection-failed-while-receiving-payload-length-from-upstream-connection-prematurely-closed-by-remote-server/76148/10
    incoming-num-tcp: 40

    # only trust glue records from authoritative source
    harden-glue: yes

    # ensure DNSSEC signature is present if required
    harden-dnssec-stripped: yes

    # no capitalistion
    use-caps-for-id: no

    # Ensures no IP fragmentation See https://docs.pi-hole.net/guides/dns/unbound/ for explanation
    edns-buffer-size: 1232

    # enable prefetching
    prefetch: yes

    # one thread OK for homesetup
    num-threads: 2

    # ensure adequate kernal buffer
    so-rcvbuf: 4m
    so-sndbuf: 4m

    # use root hints
    root-hints: "/opt/unbound/etc/unbound/root.hints"

    # Ensure privacy of local IP ranges
    private-address: 192.168.0.0/16
    private-address: 169.254.0.0/16
    private-address: 172.16.0.0/12
    private-address: 10.0.0.0/8
    private-address: fd00::/8
    private-address: fe80::/10

    # Ensure no reverse queries to non-public IP ranges (RFC6303 4.2)
    private-address: 192.0.2.0/24
    private-address: 198.51.100.0/24
    private-address: 203.0.113.0/24
    private-address: 255.255.255.255/32
    private-address: 2001:db8::/32

    # Restrict access
    access-control: 127.0.0.1/32 allow
    access-control: 192.168.0.0/24 allow

    # Serve stale records if upstream is slow rather than failing
    serve-expired: yes
    serve-expired-ttl: 86400

    # Handle more simultaneous queries
    num-queries-per-thread: 2048
    outgoing-range: 4096

    # Increase caches (defaults are 4MB msg, 4MB rrset)
    msg-cache-size: 64m
    rrset-cache-size: 128m

    # More slabs to reduce lock contention (should be power of 2, close to num-threads)
    msg-cache-slabs: 2
    rrset-cache-slabs: 2
    infra-cache-slabs: 2
    key-cache-slabs: 2
```
- Extra components to standard configuration to mitigate burts from corporate laptop
- Docker compose file `docker-compose.unbound.yml`
```yml
services:
  unbound:
    container_name:
      unbound
    image: mvance/unbound:latest
    network_mode: host
    volumes:
      - ./unbound:/opt/unbound/etc/unbound
      - ./unbound/root.hints:/opt/unbound/etc/unbound/root.hints
    restart: unless-stopped
```
- Ensure pi-hole docker compose file has
```yml
...
FTLCONF_dns_upstreams: '127.0.0.1#5335'
...
```
- To check unbound is working
```bash
sudo ss -tlnp | grep 5335
```
- Unbound will be listening on 5335
```bash
dig @127.0.0.1 -p 5335 google.com
```
- If working a response will be returned
- In the pi-hole admin centre the upstream DNS servers will be custom.

### Pi-Hole
```yaml
services:
  pihole:
    container_name: pihole
    image: pihole/pihole:<pinned-version>
    network_mode: host
    environment:
      TZ: 'Europe/London'
      FTLCONF_webserver_api_password: '*****'
      FTLCONF_dns_listeningMode: 'LOCAL'
      FTLCONF_dns_upstreams: '127.0.0.1#5335'
    volumes:
      - './etc-pihole:/etc/pihole'     
    cap_add:
      - NET_ADMIN
    restart: unless-stopped
    depends_on:
      - unbound
```
- No option on router, so DHCP has to be handled by pi-hole. and `network_mode` is changed to `host`  (future  update to macvlan)
- FTLCONF_dns_upstreams is local host and port for unbound e.g. `127.0.0.1#5335`
- Ubuntu's systemd-resolve can occupy port 53 to cache DNS. Ensure this is turned off.
```bash
sudo nano /etc/systemd/resolved.conf
```
```ini
[Resolve]
DNS=192.168.0.1
DNSStubListener=no
```
- Need a line dhcp-host and dns-ratelimit-ip for each device.
- limits to 30 queries per 60 seconds before requests are dropped.
- Check that dsnmasq syntax OK
```bash
docker exec -it pihole pihole-FTL --test
```
### Wireguard
```yml
services:
  wireguard:
    image: lscr.io/linuxserver/wireguard:latest
    container_name: wireguard
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/London
      - SERVERURL=<my-domain>
      - SERVERPORT=<port>
      - PEERS=1
      - PEERDNS=<dns of pihole>
      - LOG_CONFS=true
    volumes:
      - /opt/wireguard-server/config:/config
      - /lib/modules:/lib/modules
    ports:
      - <server port>:<server-port>/udp
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
    restart: unless-stopped
    depends_on:
      - pihole
```
- Server port needs to be port forwarded in router
- My router needs a new service set up, detailing the protocol, port and IP to forward to and then a firewall rule set up using the service to allow port forwarding.
```apacheconf
name: wireguard
type: UDP
Start Port: <my-port>
End Port: <my-port>
Destination: <pi-hole IP address>
```
```apacheconf
name: ssh
type: TCP
Start Port: <my-port>
End Port <my-port>
Destination: <pi-hole IP address>
```
- Test open ports using https://www.yougetsignal.com/tools/open-ports/ (to find public IP https://whatismyip.com).
- Run leaktests https://dnsleaktest.com/ to check for no DNS leaks. If all OK only the ISP server will be shown
#### Add new peer
- Increase peer count
```bash
sudo nano docker-compose.wireguard.yml
```
```yml
environments:
  - PEERCOUNT=1
```
- Or update .env if using
- Recreate
```bash
docker compose -f docker-compose.wireguard.yml down
docker compose -f docker-compose.wireguard.yml up -d
```
- If any updates to wireguard, stop docker, then remove any peers being updated.
```bash
docker compose down
sudo rm -rf ./wireguard/config/peer1
docker compose up -d
```

- I have a custom domain name, so have written an automated script to script to update public IP address of the Wyse, as this will periodically change.
## Step Four: Component Updates
### Adding cron jobs
- Make a script executable
```bash
chmod +x <script-name>.sh
```
- Check permissions
```bash
ls -l
```
- ensure cron is running
```bash
sudo systemctl enable cron
```
- open cron
```bash
crontab -e
```
- Then add cron expression
### Update root.hints
```bash
#!/bin/bash
NAMED_ROOT_URL="https://www.internic.net/domain/named.root"
DEST="/opt/homelab/unbound/root.hints"

logger -t "$LOG_TAG" "INFO: Create temp file"
TMP_FILE=$(mktemp)

# Download to temp file first, not directly to destination
logger -t "$LOG_TAG" "INFO: Downloading new root hints"

if ! curl -fsSL --max-time 30 "$NAMED_ROOT_URL" -o "$TMP_FILE"; then
    logger -t "$LOG_TAG" "ERROR: Failed to download named.root"
    rm -f "$TMP_FILE"
    exit 1
fi

if ! grep -q "ROOT-SERVERS.NET" "$TMP_FILE"; then
    logger -t "$LOG_TAG" "ERROR: Downloaded file doesn't look like a valid named.root"
    rm -f "$TMP_FILE"
    exit 1
fi

# Backup existing file
cp "$DEST" "${DEST}.bak"
logger -t "$LOG_TAG" "INFO: Backup created at ${DEST}.bak"

# Only now replace the live file
mv "$TMP_FILE" "$DEST"

logger -t "$LOG_TAG" "SUCCESS: root.hints updated successfully"

# Reload Unbound inside the container dev/null required to enable successful logging
#
if docker restart unbound > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "INFO: Unbound restarted successfully"
else
    logger -t "$LOG_TAG" "ERROR: Failed to restart Unbound"
fi
```
- Root hints do not update very often so set cron job to once weekly
```
0 2 * * 1 /opt/homelab/scripts/update-root-hints.sh > /dev/null 2>&1
```
### Setup Azure CLI and update script
- Need some setup to ensure package from correct location is used. https://documentation.ubuntu.com/azure/azure-how-to/instances/install-azure-cli/
- Prerequisites
```bash
sudo apt-get update
sudo apt-get install apt-transport-https ca-certificates curl gnupg lsb-release
```
- Get key and convert to binary
```bash
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg
```
- Add repository to source list
```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ \
  $(. /etc/os-release && echo "$VERSION_CODENAME") main" | \
  sudo tee /etc/apt/sources.list.d/microsoft.list > /dev/null
```
- Pin rules to ensure Azure CLI is fetched from MS
```bash
sudo nano /etc/apt/preferences/99-microsoft
```
- Add following lines
```apacheconf 
Package: *
Pin: origin https://packages.microsoft.com/repos/azure-cli
Pin-Priority: 1
Package: azure-cli
Pin: origin https://packages.microsoft.com/repos/azure-cli
Pin-Priority: 500
```
- Install the CLI
```bash
sudo apt-get update
sudo apt-get install -y azure-cli
```
- Create service principle to login to Azure
```powershell
az ad sp create-for-rbac --name "{name}" --role "DNS Zone Contributor" --scopes /subscriptions/{subscriptionId}/resourceGroups/g-dev-personal-website/providers/Microsoft.Network/dnszones/{dns zone name}
```
- Create an A record with a TTL of 300s
```powershell
az network dns record-set a create --name {name of record} --resource-group {resource group name} --zone-name {DNS zone name} --ttl 300
```
- Script to automatically check current device IP, check DNS record and update if needed
```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_TAG="update-root-hints"
source "$SCRIPT_DIR/.env"

az login --service-principal \
  --username "$AZURE_CLIENT_ID" \
  --password "$AZURE_CLIENT_SECRET" \
  --tenant "$AZURE_TENANT_ID" \
  --output none

logger -t "$LOG_TAG" "Logged into Azure"

CURRENT_IP=$(curl -s https://api.ipify.org)
logger -t "$LOG_TAG" "Current IP is: $CURRENT_IP"

RECORD_IP=$(az network dns record-set a show \
  --resource-group "$RG" \
  --zone-name "$ZONE_NAME" \
  --name "$RECORD_NAME" \
  --query ARecords[0].ipv4Address -o tsv)

logger -t "$LOG_TAG" "Record IP is: ${RECORD_IP:-"No IP found"}"

if [ "$CURRENT_IP" != "$RECORD_IP" ]; then
    az network dns record-set a update \
      --resource-group "$RG" \
      --zone-name "$ZONE_NAME" \
      --name "$RECORD_NAME" \
      --set ARecords[0].ipv4Address="$CURRENT_IP"
    logger -t "$LOG_TAG" "Updated DNS to $CURRENT_IP"
else
    logger -t "$LOG_TAG" "No change required"
fi

az logout --output none
logger -t "$LOG_TAG" "Logged out of Azure"
```
- See above for making script executable and enabling cron
- Add following to run script every 15 minutes
```
*/15 * * * * /opt/homelab/scripts/update-vpn-dns.sh > /dev/null 2>&1
```
- Script is run and output sent to log
### Wireguard on demand in windows
- Wireguard doesn't have an ondemand setting like on mobile apps in windows
- Combination of powershell script and Task scheduler to acheive this
```powershell
$homeSSID = "" #SSID name
$tunnelName = "" #name of tunnel in wireguard
$confLocation = "" #location of the wireguard config file
$pathToWireguard = "C:\Program Files\Wireguard\Wireguard.exe" #location of wireguard.exe
$serviceName = "WireGuardTunnel$"+$tunnelName #name of the wireguard service for the specified tunnel
```
```powershell
#dot source the env.ps1 file to load the environment variables
. .\env.ps1

#Check if the current SSID is the home SSID and start/stop the wireguard service accordingly
$currentSSID = (Get-NetConnectionProfile -InterfaceAlias "WiFi" -ErrorAction SilentlyContinue).Name
#Get the WireGuard service for the specified tunnel
$service = Get-Service $serviceName -ErrorAction SilentlyContinue

if($currentSSID -match $homeSSID) {
    # If the current SSID matches the home SSID, stop the WireGuard service if it is running, match is used as Windows sometimes renames the SSIS internally when the router switches bands
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
```
- If the SSID is my home WiFi wireguard will be deactivated, but if the SSID isn't the same the service will start
- Additional checks are performed in case the service is already stopped, or hasn't been created yet.

- Create Task
- General
  - Name: name of task
  - Description: description of task
  - Security
    - Run with highest privileges
- Triggers
  - New
    - Begin the task: On an event
      - Log: Microsoft-Windows-NetworkProfile/Operational
      - Source: Network Profile
      - Event ID: 10000
  - New
    - At log on
- Actions
  - Action: Start a program
    - Settings:
      - Program/script: powershell.exe
      - Add arguments: -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%USERPROFILE%\source\Tools\wireguard scripts\wireguard-on-demand.ps1"
      - Start in: %USERPROFILE%\source\Tools\wireguard scripts
- Every time the laptop connects to a new network this task is triggered and the script run.
- Run with highest privileges is needed as it's run as administrator to interact with services.            

## Step Five: Troubleshooting

### General Linux
- Check permissions
```bash
ls -l
```
- Change file ownership
```bash
chown -R USERNAME:GROUPNAME /PATH/TO/FILE
```
- Delete file
```bash
rm /PATH/TO/FILE -i -r
```
- -i confirms deletion
- -r recurssive, use for folders to delete contents
- move / rename file
```bash
mv /PATH/TO/FILE /NEW/PATH/OR/NEW/FILENAME
```
### Docker
- General logs
```bash
docker compose logs <container-name>
# or tail and follow live
docker compose logs <container-name> -f --tail 50
```
### Ubound

### Pi-hole error logs
```bash
sudo docker compose logs pihole | grep -i "dnsmasq\|config\|error"
```

### Wireguard
- Check local ip and ip associated with domain
```bash
curl -s https://api.ipify.org
dig +short your-record.your-zone.com
```
- peers connected
```bash
docker exec wireguard wg show
```
- packets being received
```bash
sudo tcpdump -i any -n udp port 51820
```
### UFW
- When changing UFW settings (especially default settings) can end up with `DEFAULT_FORWARD_POLICY=DROP"`
```bash
sudo nano /etc/default/ufw
```
- Need to change to `ACCEPT`
```ini
DEFAULT_FORWARD_POLICY="ACCEPT"
```
- Restart
```bash
sudo ufw reload
```
