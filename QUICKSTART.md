# Quick Start Guide - Twitter/X Video Downloader v2.0

## 🚀 Get Running in 5 Minutes

### Step 1: Ensure Docker Desktop is Running

Make sure Docker Desktop is open and running on your machine.

```bash
# Verify Docker is running
docker --version
docker-compose --version
```

### Step 2: Navigate to Backend Directory

```bash
cd backend
```

### Step 3: Create Environment File

```bash
cp .env.example .env
```

Your `.env` file now has:
- Redis: localhost:6379
- RabbitMQ: localhost:5672
- API: localhost:8000

### Step 4: Start All Services

```bash
docker-compose up -d
```

This will:
1. Start **Redis** (caching & state)
2. Start **RabbitMQ** (task queue)
3. Start **FastAPI** server (API)
4. Start **Worker** process (downloads videos)

Wait 10-15 seconds for services to initialize.

### Step 5: Verify Everything is Running

```bash
# Check health
curl http://localhost:8000/health

# Expected output:
# {
#   "status": "healthy",
#   "redis": "connected",
#   "rabbitmq": "connected",
#   "timestamp": "2024-03-01T10:00:00.000000"
# }
```

### Step 6: Test the API

#### Get Video Information:
```bash
curl -X POST "http://localhost:8000/api/v1/info?url=https://x.com/elonmusk/status/1234567890"
```

#### Start a Download:
```bash
TASK_ID=$(curl -s -X POST "http://localhost:8000/api/v1/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://x.com/user/status/1234567890",
    "format_id": "best[ext=mp4]",
    "quality": "720p"
  }' | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)

echo "Task ID: $TASK_ID"
```

#### Check Download Progress:
```bash
curl "http://localhost:8000/api/v1/status/$TASK_ID"
```

Keep running this until you see `"status": "completed"` and `"progress": 100`.

#### Download the File:
```bash
curl "http://localhost:8000/api/v1/download/$TASK_ID" -o video.mp4
```

## 📊 Monitor Services

### View API Logs:
```bash
docker-compose logs -f api
```

### View Worker Logs:
```bash
docker-compose logs -f worker
```

### View All Logs:
```bash
docker-compose logs -f
```

### Access RabbitMQ Management UI:
```
http://localhost:15672
Username: guest
Password: guest
```

View queues, messages, and connections.

## 🔧 Scale to Multiple Workers

### Scale to 3 Workers:
```bash
docker-compose up -d --scale worker=3
```

This creates:
- worker-1 (automatic)
- worker-2
- worker-3

Each worker independently downloads videos. Now you can handle **9 concurrent downloads**.

### Check All Workers:
```bash
docker-compose ps | grep worker
```

### View Specific Worker Logs:
```bash
docker-compose logs -f worker_1
docker-compose logs -f worker_2
```

## 🛑 Stop Everything

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (delete all data)
docker-compose down -v
```

## 📝 Common Tasks

### Initialize Fresh (Reset State):
```bash
docker-compose down -v
docker-compose up -d
```

### View All Active Tasks:
```bash
curl http://localhost:8000/api/v1/tasks
```

### Cancel a Specific Download:
```bash
curl -X POST "http://localhost:8000/api/v1/cancel/$TASK_ID"
```

### View Docker Desktop Stats:
```bash
# Open Docker Desktop → Dashboard → Containers
# See resource usage for each service
```

## 🐛 Troubleshooting

### Services Won't Start?
```bash
# View error logs
docker-compose logs

# Restart
docker-compose restart
```

### Redis Connection Error?
```bash
# Check if Redis container is healthy
docker inspect twitter-downloader-redis | grep -A 5 "State"

# Restart Redis
docker-compose restart redis
```

### RabbitMQ Connection Error?
```bash
# Check if RabbitMQ container is healthy
docker inspect twitter-downloader-rabbitmq | grep -A 5 "State"

# Restart RabbitMQ
docker-compose restart rabbitmq
```

### Worker Not Processing Tasks?
```bash
# Check worker is running
docker-compose ps | grep worker

# View worker logs for errors
docker-compose logs worker

# Restart worker
docker-compose restart worker
```

### Port Already in Use?

If port 8000, 6379, or 5672 is already in use, edit `docker-compose.yml` and change the ports:

```yaml
services:
  redis:
    ports:
      - "6380:6379"  # Changed from 6379:6379
  
  rabbitmq:
    ports:
      - "5673:5672"  # Changed from 5672:5672
  
  api:
    ports:
      - "8001:8000"  # Changed from 8000:8000
```

## 🎯 Next Steps

1. **Read full documentation**: See `README.md`
2. **Scale workers**: `docker-compose up -d --scale worker=5`
3. **Explore API docs**: Visit `http://localhost:8000/docs`
4. **Monitor RabbitMQ**: Visit `http://localhost:15672`
5. **Check Redis**: Use `redis-cli` command-line tool

## 💡 Key Concepts

- **Redis**: Stores task state & caches video info
- **RabbitMQ**: Distributes download tasks to workers
- **Worker**: Processes tasks independently, can be scaled
- **API**: Accepts requests, publishes to queue, serves files

## ✅ You're Ready!

Your production-ready Twitter/X video downloader is now running with:
- ✅ Redis caching (1 hour video info TTL)
- ✅ RabbitMQ queue (reliable task distribution)
- ✅ Worker system (scalable processing)
- ✅ Persistent state (Redis-backed)
- ✅ Real-time progress (API status endpoint)

**Happy downloading!** 🎉
