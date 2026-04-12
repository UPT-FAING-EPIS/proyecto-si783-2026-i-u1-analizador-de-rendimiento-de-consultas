db.dropDatabase();

db.users.insertMany([
  {
    _id: 1,
    name: "Alice Johnson",
    email: "alice@example.com",
    age: 28,
    created_at: ISODate("2024-01-01T10:00:00Z"),
    status: "active",
    premium: true,
  },
  {
    _id: 2,
    name: "Bob Smith",
    email: "bob@example.com",
    age: 35,
    created_at: ISODate("2024-01-02T10:00:00Z"),
    status: "active",
    premium: false,
  },
  {
    _id: 3,
    name: "Charlie Brown",
    email: "charlie@example.com",
    age: 42,
    created_at: ISODate("2024-01-03T10:00:00Z"),
    status: "inactive",
    premium: true,
  },
  {
    _id: 4,
    name: "Diana Prince",
    email: "diana@example.com",
    age: 32,
    created_at: ISODate("2024-01-04T10:00:00Z"),
    status: "active",
    premium: false,
  },
  {
    _id: 5,
    name: "Eve Wilson",
    email: "eve@example.com",
    age: 29,
    created_at: ISODate("2024-01-05T10:00:00Z"),
    status: "active",
    premium: true,
  },
]);

db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ age: 1 });

db.logs.insertMany([
  {
    _id: 1,
    level: "INFO",
    message: "User login",
    timestamp: ISODate("2024-01-15T10:00:00Z"),
  },
  {
    _id: 2,
    level: "ERROR",
    message: "DB connection failed",
    timestamp: ISODate("2024-01-15T10:05:00Z"),
  },
  {
    _id: 3,
    level: "WARNING",
    message: "High memory usage",
    timestamp: ISODate("2024-01-15T10:10:00Z"),
  },
  {
    _id: 4,
    level: "ERROR",
    message: "Authentication error",
    timestamp: ISODate("2024-01-15T10:15:00Z"),
  },
  {
    _id: 5,
    level: "INFO",
    message: "Backup completed",
    timestamp: ISODate("2024-01-15T10:20:00Z"),
  },
]);


print("✅ MongoDB collections created and seeded!");
print("   - Collection 'users' with indexes on email and age");
print("   - Collection 'logs' WITHOUT indexes (for COLLSCAN testing)");
