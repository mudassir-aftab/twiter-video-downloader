# Documentation Index

## 📚 Start Here

**New to this project?** Start with one of these:

### ⚡ Quick Start (5 minutes)
👉 **[QUICKSTART.md](./QUICKSTART.md)**
- Get running in 5 minutes with Docker
- Basic tests to verify everything works
- Monitor services with simple commands

### 🎯 Complete Setup (Step-by-step)
👉 **[SETUP_GUIDE.md](./SETUP_GUIDE.md)**
- Detailed installation instructions
- Testing each component
- Troubleshooting common issues
- Docker Desktop tips

### 📖 Full Documentation
👉 **[README.md](./README.md)**
- Complete API reference
- Configuration options
- Scaling strategies
- Performance characteristics

---

## 🏗️ Understanding the Architecture

### 🎓 Architecture Overview
👉 **[ARCHITECTURE.md](./ARCHITECTURE.md)**
- System design and components
- Data flow diagrams
- Failure modes and recovery
- Scalability characteristics
- Security considerations
- Monitoring and observability

### 🔄 From v1 to v2
👉 **[MIGRATION.md](./MIGRATION.md)**
- What changed between versions
- API compatibility
- Code changes (if modifying)
- Performance comparison
- Testing checklist
- Rollback plan

### ✅ What's Implemented
👉 **[SUMMARY.md](./SUMMARY.md)**
- Files created and their purpose
- Key features implemented
- Performance metrics
- Configuration options
- Deployment readiness

---

## 🔧 Using the System

### API Endpoints
Reference the API in one of these ways:

1. **Interactive API Docs**: `http://localhost:8000/docs` (Swagger UI)
2. **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)
3. **README.md**: Endpoints section
4. **QUICKSTART.md**: Testing section

### Common Tasks

#### 🚀 Start Services
```bash
cd backend
cp .env.example .env
docker-compose up -d
```
👉 See **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** for detailed steps

#### 📊 Monitor Services
```bash
docker-compose logs -f
```
👉 See **[SETUP_GUIDE.md - Monitoring](./SETUP_GUIDE.md#monitoring-services)** section

#### 📈 Scale Workers
```bash
docker-compose up -d --scale worker=3
```
👉 See **[README.md - Scaling Workers](./README.md#scaling-workers)** section

#### 🧪 Test API
See examples in:
- **[QUICKSTART.md](./QUICKSTART.md)** - Simple curl examples
- **[SETUP_GUIDE.md - Testing](./SETUP_GUIDE.md#testing-the-api)** - Detailed test steps

#### ❌ Troubleshoot Issues
👉 See **[SETUP_GUIDE.md - Troubleshooting](./SETUP_GUIDE.md#troubleshooting)** section

---

## 📁 File Structure

```
backend/
│
├── 📄 Documentation
│   ├── INDEX.md              ← You are here
│   ├── README.md             ← Full documentation
│   ├── QUICKSTART.md         ← 5-minute setup
│   ├── SETUP_GUIDE.md        ← Detailed setup & troubleshooting
│   ├── ARCHITECTURE.md       ← Technical deep dive
│   ├── MIGRATION.md          ← v1 → v2 guide
│   └── SUMMARY.md            ← Implementation overview
│
├── 🐍 Application Code
│   ├── main.py               ← FastAPI server
│   ├── worker.py             ← Worker process
│   ├── config.py             ← Configuration
│   ├── models.py             ← Data models
│   ├── redis_client.py       ← Redis wrapper
│   ├── rabbitmq_client.py    ← RabbitMQ client
│   └── main_original.py      ← Original v1 implementation
│
├── 🐳 Docker Files
│   ├── docker-compose.yml    ← Multi-service compose
│   ├── Dockerfile.api        ← API image
│   ├── Dockerfile.worker     ← Worker image
│   └── requirements.txt      ← Python dependencies
│
└── ⚙️ Configuration
    └── .env.example          ← Environment template
```

---

## 🎯 Choose Your Path

### Path 1: "Just Make It Work" ⚡
```
1. QUICKSTART.md
2. docker-compose up -d
3. curl http://localhost:8000/health
4. Done!
```

### Path 2: "Understand Everything" 📚
```
1. SUMMARY.md (overview)
2. ARCHITECTURE.md (how it works)
3. SETUP_GUIDE.md (hands-on setup)
4. README.md (reference)
5. MIGRATION.md (if upgrading)
```

### Path 3: "I'm Modifying the Code" 🔧
```
1. main_original.py (understand original)
2. ARCHITECTURE.md (system design)
3. main.py, worker.py (new implementation)
4. models.py, redis_client.py, rabbitmq_client.py (supporting code)
5. MIGRATION.md (compatibility notes)
```

### Path 4: "Troubleshooting Issues" 🔧
```
1. SETUP_GUIDE.md - Troubleshooting section
2. docker-compose logs -f (view logs)
3. curl http://localhost:8000/health (check health)
4. ARCHITECTURE.md (understand components)
```

---

## 🚀 Quick Commands Reference

### Service Management
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose stop

# Restart services
docker-compose restart

# Clean shutdown (delete data)
docker-compose down -v

# View running services
docker-compose ps
```

### Monitoring
```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f worker

# View logs with line count
docker-compose logs -n 100
```

### Scaling
```bash
# Scale to 3 workers
docker-compose up -d --scale worker=3

# Scale to 1 worker
docker-compose up -d --scale worker=1
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Get video info
curl -X POST "http://localhost:8000/api/v1/info?url=<url>"

# Start download
curl -X POST "http://localhost:8000/api/v1/download" -H "Content-Type: application/json" -d '{"url":"<url>"}'

# Check status
curl "http://localhost:8000/api/v1/status/<task_id>"

# See all tasks
curl "http://localhost:8000/api/v1/tasks"
```

### Interfaces
```
API Documentation:    http://localhost:8000/docs
RabbitMQ UI:          http://localhost:15672 (guest/guest)
Redis CLI:            docker exec -it backend_redis_1 redis-cli
Worker Logs:          docker-compose logs -f worker
```

---

## 📊 System Overview

### What This System Does
- ✅ Downloads videos from Twitter/X
- ✅ Caches video info in Redis
- ✅ Distributes downloads via RabbitMQ
- ✅ Scales to multiple workers
- ✅ Tracks progress in real-time
- ✅ Persists state across restarts

### Key Technologies
| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI | HTTP endpoints |
| Queue | RabbitMQ | Task distribution |
| Cache | Redis | State & caching |
| Worker | Python + asyncio | Video downloads |
| Download | yt-dlp | Twitter/X video grabbing |
| Container | Docker | Deployment |

### Scaling Model
```
1 Worker    = 3 concurrent downloads
3 Workers   = 9 concurrent downloads
10 Workers  = 30 concurrent downloads
N Workers   = 3N concurrent downloads
```

---

## ❓ FAQ

### Q: How do I get started?
**A:** Follow [QUICKSTART.md](./QUICKSTART.md) - takes 5 minutes.

### Q: How do I scale to multiple workers?
**A:** Run `docker-compose up -d --scale worker=3`
👉 See [README.md - Scaling Workers](./README.md#scaling-workers)

### Q: Where is my video file?
**A:** In the downloads volume. Access via API: `GET /api/v1/download/{task_id}`

### Q: How do I monitor progress?
**A:** Poll `GET /api/v1/status/{task_id}` to see progress in real-time.

### Q: Can I modify the download logic?
**A:** Yes, but the current implementation using yt-dlp is already comprehensive.
👉 See [worker.py](./worker.py) for the download implementation.

### Q: How long do tasks stay in the system?
**A:** 7 days by default (configurable via `TASK_TTL_SECONDS` in .env)

### Q: How do I reset everything?
**A:** Run `docker-compose down -v && docker-compose up -d`

### Q: Is this production-ready?
**A:** It's production-ready for the Docker Desktop environment. For production deployment, add authentication, TLS, clustering, and monitoring. See [ARCHITECTURE.md](./ARCHITECTURE.md#deployment-strategies)

---

## 🔗 Cross-References

### By Use Case

**"I want to download a video"**
- QUICKSTART.md (Testing section)
- SETUP_GUIDE.md (Testing the API section)

**"I want to scale to 3 workers"**
- README.md (Scaling Workers section)
- SETUP_GUIDE.md (Scaling Up section)

**"I want to upgrade from v1"**
- MIGRATION.md (entire document)

**"I'm getting errors"**
- SETUP_GUIDE.md (Troubleshooting section)
- docker-compose logs

**"I want to understand the architecture"**
- ARCHITECTURE.md (entire document)
- SUMMARY.md (Architecture Highlights section)

**"I want to deploy to production"**
- ARCHITECTURE.md (Deployment Strategies section)
- README.md (performance characteristics)

---

## 📞 Support

### Getting Help

1. **Check logs first**
   ```bash
   docker-compose logs -f
   ```

2. **Check health**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Read troubleshooting**
   - [SETUP_GUIDE.md - Troubleshooting](./SETUP_GUIDE.md#troubleshooting)

4. **Review architecture**
   - [ARCHITECTURE.md - Failure Modes](./ARCHITECTURE.md#failure-modes--recovery)

5. **Check API docs**
   - http://localhost:8000/docs (interactive)
   - [README.md - API Endpoints](./README.md#api-endpoints)

---

## 🎉 You're Ready!

Everything you need is documented. Pick a path above and get started!

**Most common next steps:**
1. Run `cd backend && docker-compose up -d`
2. Wait 10 seconds
3. Visit `http://localhost:8000/health`
4. Test API with examples from QUICKSTART.md

**Happy downloading!** 🚀

---

**Last Updated:** March 2024  
**Version:** 2.0 (Distributed Architecture)  
**Status:** Production-Ready for Docker Desktop
