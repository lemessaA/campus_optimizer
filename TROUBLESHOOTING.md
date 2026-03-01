# Troubleshooting Guide

## Common Issues

### API won't start

**Symptom**: `uvicorn src.main:app` fails with connection error.

**Causes**:
- PostgreSQL not running or wrong `DATABASE_URL`
- Redis not running or wrong `REDIS_URL`

**Fix**:
```bash
# Check PostgreSQL
psql -h localhost -U postgres -d campus -c "SELECT 1"

# Check Redis
redis-cli ping
# Expected: PONG

# Verify .env has correct DATABASE_URL and REDIS_URL
```

### Health check shows "disconnected"

**Symptom**: `GET /health` returns `database: "disconnected"` or `redis: "disconnected"`.

**Fix**:
- Ensure PostgreSQL and Redis are running
- Check firewall/network if using remote hosts
- For Docker: ensure containers are up (`docker-compose ps`)

### Course creation returns 422

**Symptom**: `POST /api/v1/courses` returns validation error.

**Fix**:
- Ensure `schedule_time` is in `HH:MM` format (e.g. `"10:00"`)
- `students_count` must be 1–499
- `duration_minutes` must be 1–240

### Equipment booking fails

**Symptom**: `POST /api/v1/equipment/book` returns error.

**Fix**:
- `time_slot` must be ISO format: `2024-01-15T10:00:00`
- `equipment_id` must exist in database
- Check for conflicting bookings

### Support query returns "LLM is not configured"

**Symptom**: FAQ fallback returns generic message.

**Fix**:
- Set `GROQ_API_KEY` in `.env`
- Restart the API after changing env

### Streamlit "API error"

**Symptom**: UI shows "API error" when loading data.

**Fix**:
- Ensure API is running on port 8000
- If API is elsewhere, set `API_BASE_URL` env var for Streamlit
- Check CORS if API and UI are on different origins

### Tests fail with database/Redis errors

**Symptom**: `pytest` fails with connection errors.

**Fix**:
- Tests use mocked DB/Redis by default; check `conftest.py`
- For integration tests, ensure test DB/Redis are available
- Use `pytest src/tests/ -v` to see which test fails

## Logs

- **API logs**: stdout; file `campus_optimizer.log` if `setup_logging()` is called
- **Streamlit**: stdout
- **Debug**: Set `LOG_LEVEL=DEBUG` in `.env`

## Recovery

1. **Restart services**: `docker-compose restart` or restart uvicorn/streamlit
2. **Reset DB**: Run migrations; seed data if needed
3. **Clear Redis**: `redis-cli FLUSHDB` (clears cache; use with caution)
