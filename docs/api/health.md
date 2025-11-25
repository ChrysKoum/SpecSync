# Health Check Endpoint

## GET /health

Health check endpoint that returns service status and current timestamp.

### Description

This endpoint provides a simple way to verify that the service is running and responsive. It returns the current health status and a timestamp, which can be used for monitoring and health check purposes.

### Request

**Method:** `GET`

**URL:** `/health`

**Parameters:** None

**Headers:** None required

### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:**

| Field | Type | Description |
|-------|------|-------------|
| status | string | Service health status (always "healthy" when service is running) |
| timestamp | string | Current server timestamp in ISO 8601 format with UTC timezone |

### Example

#### Request

```bash
curl -X GET http://localhost:8000/health
```

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2025-11-24T10:30:00Z"
}
```

### Use Cases

- **Service Monitoring**: Use this endpoint in monitoring tools to verify service availability
- **Load Balancer Health Checks**: Configure load balancers to poll this endpoint
- **Deployment Verification**: Confirm successful deployment by checking health status
- **Uptime Monitoring**: Track service uptime by periodically calling this endpoint

### Notes

- This endpoint always returns `200 OK` when the service is running
- The timestamp is in UTC timezone (indicated by the 'Z' suffix)
- No authentication is required for this endpoint
- This endpoint has minimal overhead and can be called frequently

### Specification Reference

This endpoint is defined in `.kiro/specs/app.yaml`:

```yaml
- path: "/health"
  method: "GET"
  description: "Health check endpoint that returns service status and current timestamp"
  tests_required: true
```
