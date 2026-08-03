# Update Docker Images
- unbound and samba both from non maintained registries
- So move to ones that are

# Samba
- Change to dockurr/samba
- simpler config, use two .conf files, smb.conf and users.conf to set up share
- configurations swapped over from earlier image

# Unbound
- Change to klutchell/unbound
- simpler config, all custom config from previous image already included, only needed to add port and interface (127.0.0.1 only allows traffic to unbound from server)
- amended docker image
- also root hints included in image so removal of script to check root-hints

#
Both images will be pinned to ensure no unexpected drops in service.