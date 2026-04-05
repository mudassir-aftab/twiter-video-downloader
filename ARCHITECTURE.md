# Architecture Documentation

## System Design Overview

### v2.0 Architecture (Current - Distributed)

```
┌──────────────────────────────────────────────────────────────┐
│                    Client Applications                        │
│  (Web, Mobile, Desktop - Makes HTTP requests)                │
└─────────────────────────┬──────────────────────────────────────┘
                          │ HTTP(S)
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Server                              │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ • Accept download requests                             │   │
│  │ • Query video info (with Redis cache)                  │   │
│  │ • Publish tasks to RabbitMQ                            │   │
│  │ • Serve completed video files                          │   │
│  │ • Provide task status via Redis lookup                 │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────┬────────────────────┬────────────────────────────┘
                │                    │
        ┌───────▼────────┐   ┌──────▼──────────┐
        │   Redis        │   │    RabbitMQ     │
        │ (Persistent)   │   │ (Task Queue)    │
        │                │   │                 │
        │ Stores:        │   │ Queue:          │
        │ • Task state   │   │ • download_     │
        │ • Video info   │   │   tasks         │
        │ • Cancel flags │   │ • Routing key   │
        │ • TTL: 7 days  │   │ • Durable       │
        │                │   │ • Persistent    │
        └────────┬───────┘   └────────┬────────┘
                 │                    │
                 └────────┬───────────┘
                          │ AMQP
            ┌─────────────┼─────────────┐
            │             │             │
     ┌──────▼────┐ ┌──────▼────┐ ┌──────▼────┐
     │  Worker 1 │ │  Worker 2 │ │  Worker 3 │
     │           │ │           │ │           │
     │ • Async   │ │ • Async   │ │ • Async   │
     │ • 3 conn  │ │ • 3 conn  │ │ • 3 conn  │
     │ • Read R  │ │ • Read R  │ │ • Read R  │
     │ • yt-dlp │ │ • yt-dlp │ │ • yt-dlp │
     │ • Update  │ │ • Update  │ │ • Update  │
     │   Redis   │ │   Redis   │ │   Redis   │
     └────┬──────┘ └────┬──────┘ └────┬──────┘
          │             │             │
          └─────────────┬─────────────┘
                        │ File I/O
            ┌───────────▼───────────┐
            │  Downloads Directory  │
            │  (Shared Volume)      │
            │                       │
            │ • video_1.mp4         │
            │ • video_2.mp4         │
            │ • video_3.mp4         │
            │ • ...                 │
            └───────────────────────┘
```

### Component Responsibilities

#### FastAPI Server (`main.py`)
- **HTTP Endpoints**: Accept client requests
- **Validation**: Validate Twitter/X URLs
- **Caching**: Query Redis for video info cache
- **Queue Publisher**: Publish tasks to RabbitMQ
- **State Reader**: Retrieve task status from Redis
- **File Server**: Serve completed video files

**Key Methods:**
- `POST /api/v1/download` → Create task + publish to RabbitMQ
- `POST /api/v1/info` → Query yt-dlp (or cache) + store in Redis
- `GET /api/v1/status/{task_id}` → Read from Redis
- `GET /api/v1/download/{task_id}` → Serve file

#### Redis (`redis_client.py`)
- **Task State Storage**: All task status, progress, metadata
- **Video Info Cache**: 1-hour TTL cache of video metadata
- **Cancellation Flags**: Signals from API to workers
- **Global State**: Single source of truth for all data

**Data Structures:**
```
Key: task:{task_id}
Value: {
  "id": "uuid",
  "url": "https://x.com/...",
  "status": "processing",
  "progress": 45,
  "message": "Downloading...",
  "download_speed": "2.5 MB/s",
  "eta": "00:30",
  ...
}
TTL: 604,800 seconds (7 days)

Key: video_info:{video_id}
Value: {cached video metadata}
TTL: 3,600 seconds (1 hour)

Key: cancel:{task_id}
Value: "1"
TTL: 3,600 seconds (auto-cleanup)
```

#### RabbitMQ (`rabbitmq_client.py`)
- **Task Distribution**: Reliable message delivery
- **Load Balancing**: Distributes tasks across workers
- **Persistence**: Messages survive broker restarts
- **Acknowledgment**: Prevents message loss

**Queue Configuration:**
```
Exchange: downloads
Type: DIRECT
Durable: Yes

Queue: download_tasks
Durable: Yes
Binding: routing_key = "download_tasks"

Message Format: JSON
{
  "task_id": "uuid",
  "url": "https://x.com/...",
  "format_id": "best[ext=mp4]",
  "quality": "720p",
  "created_at": "2024-03-01T10:00:00Z"
}
```

#### Worker Process (`worker.py`)
- **Task Consumer**: Connect to RabbitMQ, consume tasks
- **Download Engine**: Execute yt-dlp with progress tracking
- **State Updater**: Update progress in Redis in real-time
- **Error Handler**: Mark tasks failed, implement retry logic
- **Graceful Shutdown**: Cleanup on SIGTERM/SIGINT

**Workflow:**
1. Connect to RabbitMQ + Redis
2. Wait for task message
3. Extract task parameters
4. Create task state in Redis
5. Run yt-dlp with progress hook
6. Update Redis on each progress update
7. Mark task completed or failed
8. Acknowledge message to RabbitMQ
9. Go back to step 2

## Data Flow Diagrams

### Download Request Flow

```
1. Client
   POST /api/v1/download
   ├─ url: "https://x.com/user/status/123"
   ├─ format_id: "best[ext=mp4]"
   └─ quality: "720p"
        │
        ▼
2. FastAPI Server
   ├─ Generate task_id (UUID)
   ├─ Create initial task state in Redis (status=PENDING)
   ├─ Create DownloadTask message
   ├─ Publish to RabbitMQ
   └─ Return task_id to client
        │
        ▼
3. RabbitMQ
   ├─ Queue message in "download_tasks"
   ├─ Wait for consumer
        │
        ▼
4. Worker Process
   ├─ Consume message from queue
   ├─ Update Redis: status=PROCESSING
   ├─ Run yt-dlp with progress hook
   │   └─ Each progress update → Redis update
   ├─ Save video to downloads/
   ├─ Update Redis: status=COMPLETED, filename, download_url
   ├─ Acknowledge message to RabbitMQ
        │
        ▼
5. Client Polling (GET /api/v1/status/{task_id})
   ├─ Read from Redis
   ├─ See status=COMPLETED, progress=100
        │
        ▼
6. Client Download
   GET /api/v1/download/{task_id}
   ├─ Read filename from Redis
   ├─ Stream video file to client
   └─ Success!
```

### Caching Flow

```
1. Client
   GET /api/v1/info?url=https://x.com/user/status/123
        │
        ▼
2. FastAPI Server
   ├─ Extract video_id from URL
   ├─ Check Redis for video_info:{video_id}
   │   ├─ If HIT: Return cached data (FAST!)
   │   └─ If MISS: Continue...
        │
        ▼
3. Query yt-dlp
   ├─ Extract video metadata
   ├─ List available formats
        │
        ▼
4. Store in Redis
   ├─ Set key: video_info:{video_id}
   ├─ TTL: 3600 seconds
   └─ Return data to client
        │
        ▼
5. Next Request (within 1 hour)
   └─ Cache HIT! Skip yt-dlp query
```

## Scalability Characteristics

### Horizontal Scaling

```
Single Worker (3 concurrent downloads):
├─ Max throughput: ~1 video/minute
└─ Total capacity: 3 videos in flight

3 Workers (9 concurrent downloads):
├─ Max throughput: ~3 videos/minute
└─ Total capacity: 9 videos in flight

10 Workers (30 concurrent downloads):
├─ Max throughput: ~10 videos/minute
└─ Total capacity: 30 videos in flight

N Workers (3N concurrent downloads):
├─ Max throughput: ~N videos/minute
└─ Total capacity: 3N videos in flight
```

### Redis Scalability

```
Single Redis Instance:
├─ Handles all task state
├─ All video info caching
├─ All cancellation flags
├─ Max clients: ~10,000 (default)
└─ Memory: ~1 MB per 1000 tasks

Bottleneck: Network bandwidth (~10 Gbps network = millions of ops/sec)
For most use cases, single Redis is sufficient.
```

### RabbitMQ Scalability

```
Single RabbitMQ Broker:
├─ Max message throughput: ~50,000 msgs/sec
├─ Handles task queue
├─ Durable message storage
└─ Automatic requeue on failure

RabbitMQ Clustering (Advanced):
├─ Multiple brokers
├─ Shared queues
├─ High availability
└─ For multi-zone deployments
```

## Failure Modes & Recovery

### Failure: Worker Crashes

```
Scenario: Worker dies mid-download
├─ RabbitMQ: Message NOT acknowledged
├─ After timeout (default: 30min): Message requeued
├─ Redis: Task state remains (status=PROCESSING)
├─ Result: Another worker picks up the task
└─ Recovery: Automatic

Configuration: In rabbitmq_client.py
    consumer_timeout = 1800000  # 30 minutes
```

### Failure: Redis Connection Lost

```
Scenario: Redis temporarily unavailable
├─ FastAPI: Raises exception for status/info queries
├─ Worker: Cannot update progress
├─ Result: Client sees stale status
├─ Recovery: Auto-reconnect with exponential backoff
└─ Time to recovery: ~30 seconds

Configuration: In redis_client.py
    socket_connect_timeout = 5
    health_check_interval = 30
```

### Failure: RabbitMQ Down

```
Scenario: RabbitMQ broker offline
├─ FastAPI: Cannot publish new tasks
├─ Worker: Cannot consume tasks
├─ Result: New downloads blocked
├─ Existing tasks: State preserved in Redis
├─ Recovery: Auto-reconnect when broker comes back
└─ Messages in queue: Survive broker restart

Configuration: In rabbitmq_client.py
    connection = aio_pika.connect_robust(...)  # Auto-reconnect
```

### Failure: API Server Crash

```
Scenario: FastAPI server dies
├─ Workers: Still running, consuming tasks
├─ Redis: Task state intact
├─ Client: Cannot request new downloads
├─ Result: Existing tasks continue
├─ Recovery: Restart FastAPI server
└─ Impact: Minimal (workers independent)
```

## Comparison: v1 vs v2

### Version 1.0 (Original - Single Instance)

```
Architecture:
  FastAPI ──────────┐
                    ├─ ThreadPoolExecutor (3 threads)
                    └─ yt-dlp (download)

State:
  ├─ In-memory TaskManager dict
  ├─ Lost on restart
  └─ Maximum 3 concurrent

Scaling:
  └─ Not possible (single instance)

Caching:
  └─ None

Persistence:
  └─ None

Deployment:
  └─ Single process
```

### Version 2.0 (Current - Distributed)

```
Architecture:
  FastAPI ──┐
            ├─ Redis (state + caching)
            ├─ RabbitMQ (task queue)
            └─ Workers (multiple instances) ──┐
                                              ├─ yt-dlp (download)
                                              └─ async processing

State:
  ├─ Redis (persistent)
  ├─ Survives restart
  └─ Scalable to N workers

Scaling:
  └─ Horizontal: Add workers as needed

Caching:
  └─ 1-hour video info cache in Redis

Persistence:
  └─ 7-day task TTL in Redis

Deployment:
  └─ Containerized (Docker)
```

## Network Architecture

### Communication Patterns

```
                    TCP/IP (HTTP)
    Client ────────────────────────────► FastAPI
                                             │
                    TCP/IP (AMQP)           │
    RabbitMQ ◄──────────────────────────────┼─────► Worker
       │                                    │         │
       │ Durable Queue                      │         │
       └────────────────────────────────────┘         │
                                                      │
                    TCP/IP (Redis Protocol)         │
    Redis ◄──────────────────────────────────────────┘
       │
       └─────────────────────► FastAPI (queries)
```

### Port Allocations (Docker Network)

```
Service      Port    Protocol   Purpose
─────────────────────────────────────────────────
API          8000    HTTP       Client requests
RabbitMQ     5672    AMQP       Task distribution
RabbitMQ-UI  15672   HTTP       Management UI
Redis        6379    Redis      State storage
```

## Security Considerations

### Current Implementation

```
✅ Implemented:
├─ No authentication (localhost dev environment)
├─ CORS enabled for all origins (dev-friendly)
└─ No encryption on transport (local network)

⚠️ For Production Deployment:

1. Redis:
   ├─ Enable requirepass in redis.conf
   ├─ Use Redis SSL/TLS
   └─ Network isolation (firewall rules)

2. RabbitMQ:
   ├─ Change default credentials (guest/guest)
   ├─ Enable SSL/TLS
   ├─ Restrict user permissions
   └─ Network isolation

3. FastAPI:
   ├─ Add authentication (OAuth2, JWT)
   ├─ Enable HTTPS/TLS
   ├─ Rate limiting per client
   ├─ CORS restrict to specific origins
   └─ Input validation (already implemented)

4. Network:
   ├─ Use private subnets/VPCs
   ├─ Firewall rules per component
   ├─ No public internet access
   └─ VPN for remote workers
```

## Monitoring & Observability

### Key Metrics to Monitor

```
API Server:
├─ Request latency
├─ Queue publish success rate
├─ Cache hit rate
└─ Error rate

Workers:
├─ Task processing time
├─ Download success rate
├─ Retry count
└─ CPU/Memory usage

Redis:
├─ Memory usage
├─ Key expiration rate
├─ Command latency
└─ Connection count

RabbitMQ:
├─ Queue depth
├─ Message throughput
├─ Consumer count
└─ Message requeue rate
```

### Logging

```
Main.py: FastAPI logs
├─ Request received
├─ Task published
├─ File downloaded
└─ Error details

Worker.py: Worker logs
├─ Task consumed
├─ Download progress
├─ Completion status
└─ Error stack trace

Redis_client.py: Redis operations
├─ Connection status
├─ Set/Get operations
└─ Error details

Rabbitmq_client.py: RabbitMQ operations
├─ Connection status
├─ Publish success
├─ Consume details
└─ Error stack trace
```

## Deployment Strategies

### Development (Current)
```
docker-compose up -d
(Single Redis, RabbitMQ, API, Worker)
```

### Staging
```
Multiple workers (3-5)
Monitor logs
Performance testing
```

### Production
```
├─ Redis: Cluster mode, persistent storage, backup
├─ RabbitMQ: HA cluster, persistent queues
├─ API: Multiple instances behind load balancer
├─ Workers: Auto-scaling group (10-50 instances)
└─ Monitoring: Prometheus, Grafana, DataDog
```

---

This architecture is designed for **reliability**, **scalability**, and **simplicity**. Each component has a single responsibility, making it easy to understand, debug, and scale independently.
