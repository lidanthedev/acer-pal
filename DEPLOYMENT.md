# Production Deployment Guide

## Prerequisites
- Docker and Docker Compose installed
- Access to the server/VPS where you want to deploy

## Quick Start

1. **Clone the repository** (or copy files to your server)
   ```bash
   git clone <your-repo-url>
   cd acer-pal
   ```

2. **Configure environment variables**
   ```bash
   cp .env .env.production
   # Edit .env.production with your production settings
   nano .env.production
   ```

3. **Build and start the application**
   ```bash
   # Basic deployment (Flask app only)
   docker-compose up -d

   # With Nginx reverse proxy
   docker-compose --profile with-nginx up -d
   ```

## Configuration

### Environment Variables (.env)
```bash
# Authentication - CHANGE THESE IN PRODUCTION!
AUTH_USERNAME=your_admin_username
AUTH_PASSWORD=your_secure_password

# Flask Configuration
SECRET_KEY=your-very-long-random-secret-key-here
FLASK_ENV=production
FLASK_DEBUG=0

# Server Configuration
HOST=0.0.0.0
PORT=5000

# API Configuration
API_BASE_URL=https://acermovies.val.run/api
```

### Important Security Notes
1. **Change default credentials** - Update `AUTH_USERNAME` and `AUTH_PASSWORD`
2. **Generate a secret key** - Use `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. **Use HTTPS in production** - Configure SSL certificates with nginx

## Deployment Options

### Option 1: Basic Deployment
```bash
docker-compose up -d
```
- Access via: `http://your-server:5000`
- Direct Flask application

### Option 2: With Nginx Reverse Proxy
```bash
docker-compose --profile with-nginx up -d
```
- Access via: `http://your-server` (port 80)
- Nginx handles static files and adds security headers

## Management Commands

```bash
# View logs
docker-compose logs -f acer-pal

# Stop the application
docker-compose down

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d

# Update containers
docker-compose pull
docker-compose up -d

# Backup downloads
tar -czf downloads_backup_$(date +%Y%m%d).tar.gz downloads/
```

## Monitoring

- **Health check**: Available at `/login` endpoint
- **Logs**: Use `docker-compose logs -f`
- **Resources**: Monitor with `docker stats`

## File Persistence

The following directories are mounted as volumes:
- `./downloads:/app/downloads` - Downloaded files
- `./logs:/app/logs` - Application logs (optional)

## SSL/HTTPS Setup (Optional)

1. Place SSL certificates in `nginx/ssl/`
2. Update `nginx/nginx.conf` to include SSL configuration
3. Restart nginx: `docker-compose restart nginx`

## Troubleshooting

1. **Application won't start**: Check logs with `docker-compose logs acer-pal`
2. **Permission issues**: Ensure downloads directory is writable
3. **Port conflicts**: Change port mapping in docker-compose.yml
4. **Memory issues**: Adjust resource limits in docker-compose.yml

## Production Checklist

- [ ] Changed default authentication credentials
- [ ] Generated secure SECRET_KEY
- [ ] Configured proper domain/hostname
- [ ] Set up SSL certificates (if using nginx)
- [ ] Configured backup strategy for downloads
- [ ] Set up monitoring/logging
- [ ] Tested application functionality
- [ ] Documented access credentials securely