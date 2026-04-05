# Admin Dashboard Features - Complete Reference

## Overview
The admin dashboard provides comprehensive management tools for the Twitter/X video downloader system, including task management, analytics, and dynamic proxy configuration.

---

## 1. Authentication System

### Login
- **Route**: `GET /admin/login`
- **Method**: HTML form submission
- **Credentials (Demo)**:
  - Email: `admin@local.com`
  - Password: `admin123`
- **Session**: Uses httponly cookies for security

### Logout
- **Route**: `POST /admin/logout`
- **Method**: JSON response with cookie deletion
- **Authentication**: Requires active session

---

## 2. Dashboard Tabs

### Tab 1: Dashboard (Stats Overview)
- **Route**: `GET /admin/dashboard`
- **Display Elements**:
  - Total Tasks: Total count of all download tasks ever processed
  - Active Downloads: Currently processing tasks
  - Completed: Successfully finished downloads
  - Failed: Tasks that failed during processing

**Stats Data Source**: Redis (real-time from task state tracking)

### Tab 2: Proxy Manager
- **Route**: `GET /admin/proxies/list` (fetch all proxies)
- **Operations**:
  - Add new proxy
  - Delete existing proxy
  - View all proxies (demo + admin-added)
  - **Test a proxy** to verify connectivity (button next to each item)

**Add Proxy Form**:
```json
POST /admin/proxies/add
{
  "url": "http://user:pass@ip:port",
  "name": "Optional proxy name"
}
```

**Delete Proxy**:
```json
POST /admin/proxies/delete
{
  "proxy": "http://user:pass@ip:port"
}
```

**Test Proxy**:
```json
POST /admin/proxies/test
{
  "proxy": "http://user:pass@ip:port"
}
```

The server will attempt a simple request (https://httpbin.org/ip) through the
specified proxy and return success or error information. A status badge is also
shown inline in the UI.

**Features**:
- Default demo proxies cannot be deleted
- Admin-added proxies are stored in Redis (`system:proxies` list)
- Proxies are automatically used by the worker process
- Proxy connectivity can be validated on demand

### Tab 3: Analytics
- **Route**: `GET /api/v1/tasks` (fetch task data)
- **Display**: Recent tasks with status and progress

---

## 3. Proxy System Architecture

### Storage Layers
1. **Default Proxies** (config.py):
   - Hardcoded demo proxies
   - Cannot be modified from admin panel
   - Always available as fallback

2. **Admin Proxies** (Redis):
   - User-added proxies via admin panel
   - Stored in Redis key: `system:proxies`
   - Persist until manually deleted

### Proxy Selection Logic
- **Source**: `config.get_random_proxy()`
- **Algorithm**:
  1. Get admin proxies from Redis
  2. Combine with default PROXIES
  3. 50% chance return None (direct connection)
  4. 50% chance return random proxy from combined list

### Worker Integration
- Worker automatically uses `get_random_proxy()` from config
- No restart needed after adding/removing proxies
- Dynamic proxy changes apply immediately

---

## 4. UI Components

### Responsive Design
- Mobile-friendly layout
- Gradient backgrounds (purple/blue theme)
- Tab-based navigation
- Status badges and progress bars

### Forms & Controls
- Proxy URL input with validation
- Optional proxy name field
- Add/Delete buttons with confirmation dialogs
- Real-time alerts for user feedback

### Data Tables
- Task tracking table with columns:
  - Task ID (truncated)
  - URL (truncated)
  - Status (color-coded badge)
  - Progress percentage
  - Created timestamp

---

## 5. API Endpoints Summary

| Method | Route | Authentication | Purpose |
|--------|-------|-----------------|---------|
| GET | `/admin/login` | None | Display login form |
| POST | `/admin/login` | Form | Authenticate user |
| GET | `/admin/dashboard` | Required | Dashboard page |
| GET | `/admin/tasks` | Required | Tasks management page |
| POST | `/admin/logout` | None | End session |
| GET | `/admin/proxies/list` | None | List all proxies |
| POST | `/admin/proxies/add` | Required | Add new proxy |
| POST | `/admin/proxies/delete` | Required | Delete proxy |

---

## 6. Security Considerations

- **Authentication**: Session-based with httponly cookies
- **Authorization**: Admin dependency checks for sensitive operations
- **Default Protection**: Demo proxies cannot be deleted by default
- **Validation**: URL format validation for proxy inputs
- **Error Handling**: Safe error responses without sensitive data

---

## 7. Data Persistence

### Redis Keys Used
- `task:{task_id}` - Task state (JSON)
- `system:proxies` - Admin proxies list
- Admin session tokens - Temporary
- Task cache - 7-day TTL

### No Database Required
- All data stored in Redis
- Proxies load from config + Redis on demand
- No database migration needed

---

## 8. Usage Examples

### Add a New Proxy via Admin Panel
1. Navigate to `/admin/login`
2. Login with `admin@local.com` / `admin123`
3. Click "Proxy Manager" tab
4. Enter proxy URL: `http://user:pass@123.45.67.89:8080`
5. Enter proxy name: `US-Server-01`
6. Click "Add Proxy"
7. Proxy is immediately available for downloads

### Monitor Downloads
1. Click "Dashboard" tab to see live stats
2. Click "Analytics" tab to see recent tasks
3. View status, progress, and timestamps in real-time

---

## 9. Future Enhancements

Potential additions:
- Proxy health checks and testing
- CRM features (customer tracking)
- Advanced analytics and reporting
- Proxy rotation statistics
- Rate limiting configuration UI
- User management system

---

## 10. Troubleshooting

### Proxies Not Being Used
- Check if Redis is running
- Verify `system:proxies` key exists in Redis
- Check worker logs for proxy selection

### Admin Login Fails
- Verify email: `admin@local.com`
- Verify password: `admin123`
- Check browser cookies are enabled
- Clear cookies and retry

### Proxies Disappear After Server Restart
- Admin proxies are stored in Redis, not persisted to disk
- Use config.py PROXIES for persistent defaults
- Add frequently-used proxies to PROXIES list in code

---

Generated: 2024 | Twitter/X Video Downloader Admin System
