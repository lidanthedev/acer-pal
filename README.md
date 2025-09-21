# 🎬 Acer-PAL - Self-Hosted Media Acquisition & Management for Homelabs

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1+-green.svg)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Homelab](https://img.shields.io/badge/Homelab-Ready-orange.svg)](#)
[![Self-Hosted](https://img.shields.io/badge/Self--Hosted-Privacy--First-green.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Acer-PAL** is a privacy-focused, self-hosted media acquisition platform designed specifically for homelab enthusiasts. Transform your home server into a powerful media hub with intelligent content discovery, automated downloads, and seamless integration with your existing *arr stack (Sonarr, Radarr, Prowlarr).

## ✨ Perfect for Your Homelab

### 🏠 **Self-Hosted Privacy & Control**
- **Complete Data Ownership**: All content and metadata stays on your local network
- **No Cloud Dependencies**: Runs entirely offline on your homelab hardware
- **VPN Compatible**: Works seamlessly behind VPNs and reverse proxies
- **Local Authentication**: Built-in auth system with no external dependencies

### 🔗 ***arr Stack Integration**
- **Torrent Blackhole**: Direct integration with Sonarr/Radarr via torrent blackhole method
- **Automated Torrent Management**: Seamless .torrent file handling for *arr applications
- **Custom Categories**: Flexible folder structure for TV shows, movies, and other content
- **Smart Post-Processing**: Automatic file organization and naming conventions for media servers

### � **Homelab-Optimized Deployment**
- **Docker Compose Ready**: One-command deployment with persistent volumes
- **Resource Efficient**: Optimized for Raspberry Pi 4, Intel NUC, and low-power servers
- **Reverse Proxy Friendly**: Works with Traefik, Nginx Proxy Manager, and Caddy
- **Health Monitoring**: Built-in health checks for uptime monitoring

### � **High-Performance Download Engine**
- **Concurrent Processing**: Up to 4 simultaneous downloads (configurable for your hardware)
- **Smart Queue Management**: Intelligent prioritization and bandwidth management
- **Network Resilience**: Automatic retry and resume on connection drops
- **Progress Persistence**: Download state survives container restarts

### 🎯 **Intelligent Content Discovery**
- **Quality Selection**: Choose from 720p, 1080p, 4K based on your storage capacity
- **Season Management**: Bulk download entire seasons or cherry-pick episodes
- **Search History**: Remember what you've looked for across sessions
- **Metadata Rich**: Detailed content information for informed decisions

### � **Media Server Integration**
- **Plex/Jellyfin Ready**: Organized folder structure for immediate media server pickup
- **Automated Moves**: Smart file placement based on content type
- **Hardlink Support**: Preserve storage space with proper file linking
- **Permission Management**: Correct file ownership for media server access

## 🏗️ Homelab Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Reverse Proxy   │────│   Acer-PAL      │────│ External APIs   │
│ (Traefik/NPM)   │    │   Container     │    │ (via VPN)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │  Local Storage  │
                       │ (NAS/Local HDD) │
                       └─────────────────┘
                                │
    ┌───────────────────────────┼───────────────────────────┐
    │                           │                           │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Sonarr      │    │     Radarr      │    │  Plex/Jellyfin  │
│   (TV Shows)    │    │    (Movies)     │    │ (Media Server)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Homelab Quick Start

### Hardware Requirements
- **Minimum**: Raspberry Pi 4 (4GB RAM), 32GB storage
- **Recommended**: Intel NUC, Synology NAS, or dedicated server
- **Network**: Stable internet connection (VPN recommended)

### One-Click Docker Deployment

1. **Create your stack directory**
   ```bash
   mkdir -p /opt/acer-pal && cd /opt/acer-pal
   ```

2. **Download the compose file**
   ```bash
   wget https://raw.githubusercontent.com/lidanthedev/acer-pal/main/docker-compose.yml
   ```

3. **Configure for your homelab**
   ```bash
   # Create environment file
   cat > .env << EOF
   SECRET_KEY=your_super_secret_key_here
   AUTH_USERNAME=admin
   AUTH_PASSWORD=your_secure_password
   DOWNLOAD_DIRECTORY=/data/downloads
   COMPLETED_DIRECTORY=/data/media
   ENABLE_AUTO_MOVE=true
   EOF
   ```

4. **Deploy to your homelab**
   ```bash
   docker-compose up -d
   ```

5. **Access via your reverse proxy**
   - Direct: `http://your-server-ip:5000`
   - Reverse Proxy: `https://acer-pal.yourdomain.local`

### Integration with Existing *arr Stack

1. **Torrent Blackhole Setup**
   ```bash
   # Configure Sonarr/Radarr Download Client:
   # Type: Torrent Blackhole
   # Torrent Folder: /data/torrents/
   # Watch Folder: /data/downloads/
   # Category: tv (for Sonarr) or movies (for Radarr)
   ```

2. **Volume Mapping for Torrent Blackhole**
   ```yaml
   volumes:
     - /data/torrents:/app/torrents           # Torrent files from *arr
     - /data/downloads:/app/downloads         # Active downloads
     - /data/media/tv:/app/completed/tv       # Sonarr pickup
     - /data/media/movies:/app/completed/movies  # Radarr pickup
   ```

## 🔧 Homelab Configuration

### Essential Environment Variables

| Variable | Description | Homelab Recommendation |
|----------|-------------|-------------------------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `5000` |
| `SECRET_KEY` | Flask session secret | Generate with `openssl rand -hex 32` |
| `AUTH_USERNAME` | Admin username | Your choice |
| `AUTH_PASSWORD` | Admin password | Strong password (consider using Vaultwarden) |
| `DOWNLOAD_DIRECTORY` | Active downloads path | `/data/downloads` |
| `COMPLETED_DIRECTORY` | Finished files path | `/data/media` |
| `TORRENTS_DIRECTORY` | Torrent blackhole path | `/data/torrents` |
| `ENABLE_AUTO_MOVE` | Auto-organize files | `true` |

### Homelab-Specific Configuration

#### **Reverse Proxy Setup (Traefik)**
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.acer-pal.rule=Host(`acer-pal.yourdomain.local`)"
  - "traefik.http.routers.acer-pal.tls=true"
  - "traefik.http.services.acer-pal.loadbalancer.server.port=5000"
```

#### **Resource Limits for Small Hardware**
```yaml
deploy:
  resources:
    limits:
      memory: 256M      # Raspberry Pi friendly
      cpus: '0.5'       # Half a core
    reservations:
      memory: 128M
      cpus: '0.25'
```

#### **Storage Optimization**
- **Downloads**: Fast SSD for active downloads
- **Completed**: Slower HDD/NAS for long-term storage
- **App Data**: SSD for database and logs

### Network Security
- **VPN Integration**: Works behind Mullvad, NordVPN, etc.
- **Local Network Only**: Restrict access to local subnet
- **HTTPS**: Use with your reverse proxy SSL certificates

## 📚 API Endpoints

### Core Operations
- `POST /search` - Content discovery and search
- `POST /download` - Initiate single downloads
- `POST /download_all_season` - Batch season downloads
- `GET /downloads` - Monitor download progress

### File Management
- `GET /file_manager` - Browse and manage files
- `POST /move_to_completed` - Organize downloaded content
- `POST /delete_file` - Remove unwanted files

### System Management
- `GET /login` - Authentication interface
- `GET /settings` - Application configuration

## 🧪 Testing

```bash
# Run test suite
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific tests
pytest tests/test_downloads.py
```

## 🐳 Homelab Docker Deployment

### Basic Docker Compose
```yaml
version: '3.8'
services:
  acer-pal:
    image: ghcr.io/lidanthedev/acer-pal:latest
    container_name: acer-pal
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - AUTH_USERNAME=${AUTH_USERNAME}
      - AUTH_PASSWORD=${AUTH_PASSWORD}
    volumes:
      - /opt/acer-pal/data:/app/app_data
      - /data/torrents:/app/torrents
      - /data/downloads:/app/downloads
      - /data/media:/app/completed
    networks:
      - homelab
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
```

### With Reverse Proxy (Traefik)
```yaml
version: '3.8'
services:
  acer-pal:
    image: ghcr.io/lidanthedev/acer-pal:latest
    container_name: acer-pal
    restart: unless-stopped
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - AUTH_USERNAME=${AUTH_USERNAME}
      - AUTH_PASSWORD=${AUTH_PASSWORD}
    volumes:
      - /opt/acer-pal/data:/app/app_data
      - /data/torrents:/app/torrents
      - /data/downloads:/app/downloads
      - /data/media:/app/completed
    networks:
      - traefik
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.acer-pal.rule=Host(`acer-pal.yourdomain.local`)"
      - "traefik.http.routers.acer-pal.tls=true"
```

### Resource-Constrained Deployment (Pi 4)
```yaml
version: '3.8'
services:
  acer-pal:
    image: ghcr.io/lidanthedev/acer-pal:latest
    container_name: acer-pal
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - MAX_CONCURRENT_DOWNLOADS=2  # Reduced for Pi
    volumes:
      - ./data:/app/app_data
      - /mnt/usb/torrents:/app/torrents
      - /mnt/usb/downloads:/app/downloads
      - /mnt/usb/media:/app/completed
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
```

## 🏠 Community & Support

### Homelab Communities
- **r/homelab** - Share your Acer-PAL setup
- **r/selfhosted** - Self-hosting discussions and tips
- **Discord/Matrix** - Real-time support and configuration help

### Related Projects
- **Sonarr/Radarr** - Automated media management
- **Prowlarr** - Indexer management
- **Overseerr** - Media request management
- **Tautulli** - Plex/Jellyfin monitoring

## 🔗 Homelab Resources

- **Full Documentation**: [Homelab Setup Guide](docs/homelab/)
- ***arr Integration Guide**: [docs/arr-integration.md](docs/arr-integration.md)
- **Reverse Proxy Examples**: [docs/reverse-proxy/](docs/reverse-proxy/)
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md)
- **Performance Tuning**: [docs/performance.md](docs/performance.md)

## ⚠️ Disclaimer

This project was developed with assistance from AI tools to enhance code quality, documentation, and development efficiency. All code has been reviewed and tested to ensure functionality and security standards.

---

<div align="center">

**🏠 Built by Homelab Enthusiasts, for Homelab Enthusiasts 🏠**

[⭐ Star this repository](https://github.com/lidanthedev/acer-pal) | [🏠 Share on r/homelab](https://reddit.com/r/homelab) | [� Join our Discord](https://discord.gg/homelab)

</div>
