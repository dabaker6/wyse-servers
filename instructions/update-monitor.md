
### Docker image update
- update .env file with new version if pinned, else go straight to
```bash
docker compose pull && docker compose up -d
docker image prune
```

Docker images
- pinned
    - env file with pinned version
    - Github - ensure correct repos
        - wireguard
        - pi-hole
        - unbound

- latest
    - docker check
        - mcgalaxy
        - samba?

- apt
    - Ubuntu