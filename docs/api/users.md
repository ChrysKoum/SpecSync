# User Endpoints

## GET /users

List all users in the system.

### Description

Retrieves a complete list of all users registered in the system. This endpoint returns an array of user objects, each containing the user's ID, username, and email address.

### Request

**Method:** `GET`

**URL:** `/users`

**Parameters:** None

**Headers:** None required

### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:** Array of User objects

### User Object Schema

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique identifier for the user |
| username | string | User's username |
| email | string | User's email address |

### Example

#### Request

```bash
curl -X GET http://localhost:8000/users
```

#### Response

```json
[
  {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com"
  },
  {
    "id": 2,
    "username": "bob",
    "email": "bob@example.com"
  },
  {
    "id": 3,
    "username": "charlie",
    "email": "charlie@example.com"
  }
]
```

### Use Cases

- **User Directory**: Display a list of all system users
- **User Selection**: Populate dropdown menus or selection lists
- **Admin Dashboard**: Show user overview in administrative interfaces
- **Reporting**: Generate user-based reports or analytics

### Notes

- Returns an empty array `[]` if no users exist
- No pagination is currently implemented
- No authentication is required for this endpoint

---

## GET /users/{id}

Get a specific user by their ID.

### Description

Retrieves detailed information about a single user identified by their unique ID. This endpoint returns a user object if found, or a 404 error if the user does not exist.

### Request

**Method:** `GET`

**URL:** `/users/{id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | integer | Yes | Unique identifier for the user |

**Headers:** None required

### Response

#### Success Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:** User object

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique identifier for the user |
| username | string | User's username |
| email | string | User's email address |

#### Error Response

**Status Code:** `404 Not Found`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "detail": "User not found"
}
```

### Examples

#### Request - User Found

```bash
curl -X GET http://localhost:8000/users/1
```

#### Response - User Found

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com"
}
```

#### Request - User Not Found

```bash
curl -X GET http://localhost:8000/users/999
```

#### Response - User Not Found

```json
{
  "detail": "User not found"
}
```

### Use Cases

- **User Profile**: Display detailed user information
- **User Lookup**: Retrieve user data by ID for processing
- **Verification**: Confirm user existence before performing operations
- **Data Retrieval**: Fetch user details for forms or displays

### Notes

- The ID must be a valid integer
- Returns `404 Not Found` if the user ID does not exist
- No authentication is required for this endpoint
- The response format matches the User model schema

### Specification Reference

These endpoints are defined in `.kiro/specs/app.yaml`:

```yaml
- path: "/users"
  method: "GET"
  description: "List all users in the system"
  tests_required: true

- path: "/users/{id}"
  method: "GET"
  description: "Get a specific user by their ID"
  parameters:
    - name: "id"
      type: "integer"
      location: "path"
      required: true
  tests_required: true
```
