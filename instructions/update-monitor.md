# Update Monitor
## Outline
- Automated python script to check for updated apt packages, github releases and docker image updates
- Automatic security updates enabled in Ubuntu
- Other updates and any requiring a reboot need manual intervention to avoid updates breaking the system
- Cron job to time, database to track updates and then notify user
- Files will follow FHS (File Hierarchy Standard) as not containerised.
## Implementation
### python script
- See repo
- Creates a database to track updates, and whether it's been actioned
- For each source
    - checks for updates
    - if updates available the database is updated
    - updates are collated and sent to pushover for notification
- Move python file to local executables and make executable
- **Note for docker:** if the tag is pinned to a specific version, the docker check will not flag any changes, as this is a digest check, so for specific releases the digest *shouldn't* change. If the latest tag is used then the digest will change when a new version is released and this will flag and be notified. For pinned images the github repo should be checked.
```bash
sudo mv update_monitor.py /usr/local/bin/ && sudo chmod +x /usr/local/bin/update_monitor.py
```

### conf file
- See repo
- General data about system info
- Pushover user_key
- Each source of update then has it's own app token, so different updates will show a different icon, also each source has it's own config
- renotify section to set number of days before notification is resent
- Move conf file to system wide configs and only allow admin to read
```bash
sudo mv update-monitor.conf /etc/ && sudo chmod 600 /etc/update-monitor.conf
```
### Create folder for sql database
- Create folder for peristent db
```bash
sudo mkdir -p /var/lib/update-monitor
```
- Check
```bash
sudo update_monitor.py test-notify   # confirm Pushover works
sudo update_monitor.py check         # first run
```
### Cronjob
- Needs to be added to admin cronjob
```bash
sudo crontab -e
# 0 8 * * * /usr/local/bin/update_monitor.py check >> /var/log/update-monitor.log 2>&1
```
- Will run at 8am every morning and log the output.
## After check

### General
- will need to run ```./update_monitor.py done <guid>``` or ```./update_monitor.py done-all``` once updates are completed to update the database
### Ubuntu
-
```bash
sudo apt update
sudo apt upgrade
sudo apt remove # optional, run periodically
```
### Docker image update
- else go straight to
```bash
docker compose pull && docker compose up -d
docker image prune
```
- If pinned the update will be from Github. First update .env file with new version and then follow docker instructions
### Github
- Will notify of a new release, then needs manual assessment of whether the new release should be actioned.


## Notes
- Python Scripts coming from windows needs dos2unix installed to to stop issues with CR+LF vs LF
```bash
sudo apt install dos2unix
```
- Then
```bash
dos2unix /path/to/file
```
### Locations
- apt
    - Ubuntu
- docker images
    - mcgalaxy
    - samba? - change to better image
- Github
    - docker images
        - wireguard
        - pi-hole
        - unbound



# DONE BUT:
- write up - claude to summarise chat.
- expansion
- docs - including troubleshooting