# Example Service Documentation

## Overview

The Example Service is a FastAPI-based REST API that demonstrates SpecSync capabilities. This service provides user management functionality and serves as a reference implementation for maintaining synchronization between specifications, code, tests, and documentation.

**Version:** 1.0.0

## Features

- **Health Monitoring**: Simple health check endpoint for service status verification
- **User Management**: RESTful API for listing and retrieving user information
- **SpecSync Integration**: Demonstrates commit-time validation of spec-code-test-doc alignment

## Base URL

```
http://localhost:8000
```

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Running the Service

```bash
# Start the development server
uvicorn backend.main:app --reload
```

The service will be available at `http://localhost:8000`.

### API Documentation

Once running, you can access:
- Interactive API docs (Swagger UI): `http://localhost:8000/docs`
- Alternative API docs (ReDoc): `http://localhost:8000/redoc`

## API Endpoints

### Health Check

- [GET /health](api/health.md) - Check service health status

### User Management

- [GET /users](api/users.md) - List all users
- [GET /users/{id}](api/users.md#get-user-by-id) - Get a specific user by ID

## Data Models

### User

Represents a system user with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Unique identifier for the user |
| username | string | Yes | User's username |
| email | string | Yes | User's email address |

**Example:**
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com"
}
```

## Error Handling

The API uses standard HTTP status codes:

- `200 OK` - Request successful
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

Error responses follow this format:

```json
{
  "detail": "Error message description"
}
```

## SpecSync Integration

This service is managed by SpecSync, which ensures:

1. **Spec Alignment**: Code changes must align with `.kiro/specs/app.yaml`
2. **Test Coverage**: All endpoints require corresponding tests
3. **Documentation Sync**: API changes automatically trigger documentation validation

See [Architecture Documentation](architecture.md) for more details on the SpecSync system.
