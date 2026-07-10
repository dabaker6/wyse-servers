# Setup Home Minecraft Server

## Step One: Outline and aims

I want to create a self hosted minecraft server that's free to run and play, is on the local network only for now, and will run on a thin client.
- Wyse 5070 with a pentium processor, 32GB SSD and 6GB RAM
- Minecraft server: MCGalaxy
- Minecraft client: Classicube
<p>
The Wyse should provide enough grunt to run the minecraft server, with sufficient capacity for other tasks.
<p>
MCGalaxy and Classicube were chosen as they provide Minecraft classic, which for now is what I'm after, they're free to run and will run on the hardware. Consideration was given to Luanti, and as this setup will run using docker then I can easily spin up this version in the future.
<p>
Although it will be initially run locally, I already have a VPN setup which would allow remote connection.

## Step Two: Initial Setup

- See pi-hole setup step two.
- Although extra steps are added, this will ensure that the server is already hardened if it's decided to use it publically. In reality I will likely use it over the wireguard VPN, but better safe than sorry!

## Step Three: MCGalaxy

- Docker image provided by rdebath https://hub.docker.com/r/rdebath/mcgalaxy, which saves me having to build a container :)
```yml
services:
  mcgalaxy:
    container_name: mcgalaxy
    image: rdebath/mcgalaxy:latest
    volumes:
      - /data:/home/user
    ports:
      - 192.168.0.205:25566:25565
    restart: unless-stopped
```
- To use local data folder need to assign permissions to user
- create directory
```bash
sudo mkdir -p /opt/minecraft/mcgalaxy/data
```
- Check container user uid
```bash
docker exec mcgalaxy id
```
- Assign user as owner
```bash
sudo chown -R 1000:1000 /opt/minecraft/mcgalaxy/data
```
- As I may use a Minecraft Java server at some point, I will keep 25565 free on the host, and assign to 25565 to the container
- log into docker
```bash
docker exec -it mcgalaxy screen -U -D -r 
```
-exit use ctl-A + D, this leaves the server running

### Troubleshooting
- Check that verify-names is false
- Find server.properties file
```bash
docker exec -it mcgalaxy find /home/user -name server.properties
```
- Check value
```bash
docker exec -it mcgalaxy grep verify-names <path-to-file>
```
## Step Four: ClassiCube
