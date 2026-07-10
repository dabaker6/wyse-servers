## Check the disk and create partitions
- Check disk
```bash
sudo fdisk -l /dev/sda
lsblk
```
- If any partitions or data, remove. **BE CAREFUL!**
```bash
sudo wipefs -a <drive-name>
```
- Partition the drive
```bash
sudo fdisk <drive-name>
```
- ```n``` for new partition, accept defaults, the ```w``` to write
- Format the partition
```bash
sudo mkfs.ext4 <drive-name><partition-number>
```
## Mounting
- Create new folder(s)
- I am creating a private and family share so will have two folders
```bash
mkdir -p /mnt/storage/share
mkdir -p /mnt/storage/private
```
- Mount
```bash
sudo mount /dev/<drive-name><partition-number> /mnt/storage
```
- Make the mount persistent across reboots
```bash
sudo blkid <drive-name><partition-number>
```
- Note the UUID and then add a line to ```etc/fstab```
```bash
sudo nano /etc/fstab
UUID=<your-uuid> /mnt/storage ext4 defaults 0 2
```
- Test without rebooting
```bash
sudo umount /mnt/storage
sudo mount -a
```
- Ensure own user has acess
```bash
sudo chown -R $USER:$USER /mnt/storage/share

sudo chown -R $USER:$USER /mnt/storage/private
```
## Samba docker compose
- Docs: https://github.com/dperson/samba
```yaml
services:
  samba:
    image: dperson/samba
    container_name: samba
    env_file:
      - .env
    ports:
      - "139:139"
      - "445:445"
    volumes:
      - /mnt/storage/share:/share
      - /mnt/storage/private:/private
    command:
      - -p
      - -u
      - "${ADMIN};${ADMIN_PASSWORD};${ADMIN_ID};${GROUP};${GID}"
      - -u
      - "${FAMILYUSER};${FAMILYUSER_PASSWORD};${FAMILYUSER_ID};${GROUP};${GID}"
      - -s
      - "share;/share;yes;no;no;${FAMILYUSER},${ADMIN};;family shared drive"
      - -s
      - "private;/private;no;no;no;${ADMIN};;private share"
      - -G
      - "share;force user = ${ADMIN}"
      - -G
      - "share;force group = ${GROUP}"
      - -g
      - "deadtime = 15"
    restart: unless-stopped
```
- Two shares created
- -p alters permissions
- -u adds users, admin and family user. The admin user has the same ID and the host so all files can also be seen by SSHing into the server.
- -s creates the shares, family user has user access to share, and admin has admin access to /share and /private
- -G here is for forcing files to be written as admin, meaning that any file is accessible to all
- -g global option to disconnect idle or dead sessions
- Start container
```bash
docker compose -f docker-compose.samba.yml up
```
## Troubleshooting
- Usual
```bash
docker compose ps
docker compose logs samba --since 1h
```
- System resource
```bash
docker stats samba
```
- Disk usage
```bash
df -h /mnt/storage
```
- File system errors
```bash
sudo dmesg | grep -i sda
```
- Check for active sessions and locks
```bash
docker exec samba smbstatus
```