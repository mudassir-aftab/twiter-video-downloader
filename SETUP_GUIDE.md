# Complete Setup Guide

## Prerequisites

- **Docker Desktop** installed and running on your machine
- **Git** or file explorer to navigate to the backend folder
- **curl** or Postman for testing (optional, but helpful)

## Step-by-Step Setup

### 1️⃣ Navigate to Backend Directory

```bash
cd backend
```

You should see these files:
```
backend/
├── main.py
├── worker.py
├── config.py
├── models.py
├── redis_client.py
├── rabbitmq_client.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── .env.example
└── README.md
```

### 2️⃣ Create Environment Configuration

Copy the example `.env` file:

```bash
cp .env.example .env
```

The `.env` file now contains:
```env
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

MAX_CONCURRENT_DOWNLOADS=3
TASK_TTL_SECONDS=604800
VIDEO_INFO_CACHE_TTL=3600
```

**Note:** These settings connect services by their Docker Compose service names. No changes needed for Docker Desktop!

### 3️⃣ Start Docker Services

Launch all services with one command:

```bash
docker-compose up -d
```

This command starts:
1. **Redis** container - Caching and state storage
2. **RabbitMQ** container - Task queue and message broker
3. **API** container - FastAPI server (main HTTP endpoint)
4. **Worker** container - Background task processor

**Expected output:**
```
Creating backend_redis_1      ... done
Creating backend_rabbitmq_1   ... done
Creating backend_api_1        ... done
Creating backend_worker_1     ... done
```

### 4️⃣ Verify Services Are Running

Check that all containers are running:

```bash
docker-compose ps
```

**Expected output:**
```
NAME                  COMMAND                  SERVICE      STATUS
backend_redis_1       redis-server --appen    redis        Up 10s
backend_rabbitmq_1    rabbitmq-server         rabbitmq     Up 8s
backend_api_1         python -m uvicorn       api          Up 6s
backend_worker_1      python worker.py        worker       Up 3s
```

All statuses should be "Up".

### 5️⃣ Test Health Endpoint

Wait 5-10 seconds for services to fully initialize, then test:

```bash
curl http://localhost:8000/health
```

**Expected output:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "rabbitmq": "connected",
  "timestamp": "2024-03-01T10:30:45.123456"
}
```

If you get connection errors, wait a bit longer and retry.

### 6️⃣ View Logs

To see what's happening, monitor the logs:

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api       # FastAPI server
docker-compose logs -f worker    # Worker process
docker-compose logs -f redis     # Redis
docker-compose logs -f rabbitmq  # RabbitMQ
```

Press `Ctrl+C` to stop viewing logs.

## Testing the API

### Test 1: Get Video Information

```bash
curl -X POST "http://localhost:8000/api/v1/info?url=https://x.com/elonmusk/status/1234567890"
```

**Expected response:**
```json
{
  "video_id": "1234567890",
  "title": "Video Title",
  "duration": 60,
  "uploader": "elonmusk",
  "upload_date": "20240301",
  "formats": [...]
}
```

### Test 2: Start a Download

Replace the URL with a real Twitter/X video URL:

```bash
curl -X POST "http://localhost:8000/api/v1/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://x.com/user/status/1234567890",
    "format_id": "best[ext=mp4]",
    "quality": "720p"
  }'
```

**Expected response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Download queued successfully",
  "status": "pending"
}
```

Save the `task_id` for the next test.

### Test 3: Check Download Progress

Using the `task_id` from Test 2:

```bash
TASK_ID="550e8400-e29b-41d4-a716-446655440000"
curl "http://localhost:8000/api/v1/status/$TASK_ID"
```

**Expected response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "message": "Downloading: video.mp4",
  "download_speed": "2.5 MB/s",
  "eta": "00:30",
  "downloaded_bytes": 125000000,
  "total_bytes": 275000000
}
```

Keep running this command until `progress` reaches 100 and `status` is `"completed"`.

### Test 4: Download the Completed File

Once the download is complete (status = "completed"):

```bash
TASK_ID="550e8400-e29b-41d4-a716-446655440000"
curl "http://localhost:8000/api/v1/download/$TASK_ID" -o video.mp4
```

This will download the video file to your current directory.

### Test 5: View All Active Tasks

```bash
curl "http://localhost:8000/api/v1/tasks"
```

**Expected response:**
```json
{
  "total": 1,
  "tasks": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "url": "https://x.com/user/status/1234567890",
      "status": "completed",
      "progress": 100,
      ...
    }
  }
}
```

## Monitoring Services

### 🔴 Redis

Redis is used for state and caching. To interact with it:

```bash
# Get a shell in the Redis container
docker exec -it backend_redis_1 redis-cli

# Then try these commands:
KEYS *                    # See all keys
GET task:*                # Get task state
GET video_info:*          # Get cached video info
TTL key_name              # See time to live
DBSIZE                    # Total number of keys
FLUSHDB                   # Clear all data (careful!)
```

### 🟠 RabbitMQ

RabbitMQ is used for task distribution. Access the management UI:

```
Open your browser: http://localhost:15672
Username: guest
Password: guest
```

From the UI, you can:
- **Queues**: See `download_tasks` queue
- **Messages**: Check pending/ready messages
- **Consumers**: See connected workers
- **Connections**: Monitor active connections

### 🔵 FastAPI

The API server provides automatic documentation:

```
Open your browser: http://localhost:8000/docs
```

You can:
- See all API endpoints
- Read documentation
- Test endpoints directly
- View request/response schemas

Alternative documentation:
```
http://localhost:8000/redoc
```

### ⚫ Worker Process

Monitor the worker consuming tasks:

```bash
docker-compose logs -f worker
```

You'll see logs like:
```
2024-03-01 10:30:45 - worker - INFO - 🚀 Starting worker process...
2024-03-01 10:30:46 - worker - INFO - ✅ All connections verified
2024-03-01 10:30:47 - worker - INFO - 🔄 Worker started consuming tasks from RabbitMQ...
2024-03-01 10:30:50 - worker - INFO - 📩 Received task 550e8400-e29b-41d4-a716-446655440000
2024-03-01 10:30:51 - worker - INFO - 🎬 Starting download for task...
```

## Scaling Up

### Add More Workers

Want to download multiple videos simultaneously? Scale up workers:

```bash
# Scale to 3 workers (9 concurrent downloads)
docker-compose up -d --scale worker=3
```

Check they're running:

```bash
docker-compose ps | grep worker
```

View all worker logs:

```bash
docker-compose logs -f worker
```

### Remove Workers

Scale back down:

```bash
docker-compose up -d --scale worker=1
```

## Stopping Services

### Stop Everything (Keep Data)

```bash
docker-compose stop
```

To start again:

```bash
docker-compose start
```

### Stop and Remove Everything (Keep Volume Data)

```bash
docker-compose down
```

To start fresh:

```bash
docker-compose up -d
```

### Stop and Remove Everything (Delete All Data)

```bash
docker-compose down -v
```

This deletes:
- All containers
- All volumes (Redis data, downloads)
- All networks

Use `-v` only when you want a complete reset.

## Troubleshooting

### Services Won't Start

**Problem:** `docker-compose up -d` gives errors

**Solution:**
1. Check Docker Desktop is running
2. View error logs: `docker-compose logs`
3. Check port conflicts: `lsof -i :8000` (replace with your port)
4. Clean up: `docker-compose down -v && docker-compose up -d`

### "Port already in use"

**Problem:** Error like `Bind for 0.0.0.0:8000 failed`

**Solution:**
Edit `docker-compose.yml` and change the port:
```yaml
api:
  ports:
    - "8001:8000"  # Use 8001 instead of 8000
```

Then restart:
```bash
docker-compose up -d
```

### Connection Refused Errors

**Problem:** `Connection refused` when accessing API

**Solution:**
1. Wait 15-20 seconds for services to initialize
2. Check services are running: `docker-compose ps`
3. Check health: `curl http://localhost:8000/health`
4. View API logs: `docker-compose logs api`

### Redis Connection Failed

**Problem:** "Cannot connect to Redis"

**Solution:**
```bash
# Check Redis is running
docker-compose ps | grep redis

# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis
```

### RabbitMQ Connection Failed

**Problem:** "Cannot connect to RabbitMQ"

**Solution:**
```bash
# Check RabbitMQ is running
docker-compose ps | grep rabbitmq

# Check RabbitMQ logs
docker-compose logs rabbitmq

# Restart RabbitMQ
docker-compose restart rabbitmq

# Access management UI
http://localhost:15672 (guest/guest)
```

### Worker Not Processing Tasks

**Problem:** Tasks stay in "pending" state

**Solution:**
```bash
# Check worker is running
docker-compose ps | grep worker

# View worker logs
docker-compose logs worker

# Restart worker
docker-compose restart worker

# Check RabbitMQ has consumer
# Visit http://localhost:15672 → Queues → download_tasks
```

### Download Completes But No File

**Problem:** Status shows "completed" but file not found

**Solution:**
```bash
# Check download volume
docker volume ls | grep backend_downloads

# Check files in volume
docker volume inspect backend_downloads
# Mount point shown under "Mountpoint"

# Or check from container
docker exec -it backend_worker_1 ls -la /app/downloads/
```

## Performance Tips

### For Better Performance

1. **Increase Workers**
   ```bash
   docker-compose up -d --scale worker=5
   ```

2. **Monitor Resource Usage**
   - Open Docker Desktop Dashboard
   - See CPU/Memory per container
   - Add more workers if utilization < 50%

3. **Check Queue Depth**
   - Visit http://localhost:15672
   - Look at "download_tasks" queue
   - If messages building up, add more workers

4. **Cache Utilization**
   - Requests for same video info are fast (1 hour cache)
   - Check Redis memory: `docker exec backend_redis_1 redis-cli INFO memory`

## Docker Desktop Tips

### View Resources

1. Open Docker Desktop
2. Go to Dashboard
3. See CPU, Memory, Network per container
4. Click container name to see details

### View Container Terminal

1. Open Docker Desktop
2. Go to Dashboard
3. Click on container
4. See "Logs" and "Inspect" tabs
5. Can execute commands

### View Volumes

1. Open Docker Desktop
2. Go to Dashboard
3. Click on Volumes
4. See storage used by each volume
5. Can inspect or delete

## What's Next?

✅ **Setup complete!** You now have:
- Redis caching running
- RabbitMQ queue system running
- FastAPI server listening on port 8000
- Worker process consuming tasks

### Try These:

1. **Start a real download**
   - Use a real Twitter/X video URL
   - Monitor progress with status endpoint

2. **Scale to 3 workers**
   - `docker-compose up -d --scale worker=3`
   - Start 9 downloads simultaneously
   - Watch them all complete

3. **Explore the API docs**
   - Visit http://localhost:8000/docs
   - Try each endpoint
   - See request/response examples

4. **Monitor RabbitMQ**
   - Visit http://localhost:15672
   - Watch tasks flow through queue
   - See consumer connections

5. **Read documentation**
   - QUICKSTART.md - Fast overview
   - README.md - Complete guide
   - ARCHITECTURE.md - How it works

---

## Need Help?

- **Can't start services?** → Check "Troubleshooting" section
- **API not working?** → Check health endpoint first
- **Want to scale?** → Use `docker-compose up -d --scale worker=N`
- **Need to reset?** → `docker-compose down -v && docker-compose up -d`

**You're all set!** 🚀
