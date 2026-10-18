# EF Core Performance Interview Questions: N+1, No-Tracking, Split and Compiled Queries

## Twelve questions on N+1, tracking, split and compiled queries, with the answers interviewers expect.

![EF Core Performance: N+1, Tracking, Split and Compiled Queries](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/01-cover.png)

The endpoint was `GET /customers/{id}/orders`. It had answered in about 80 ms for a year. Then a developer added a `Lines` navigation property to `Order` so the response could include an order total. The pull request was eleven lines long and passed review.

In production, the same endpoint started taking 9 seconds for our largest customers. Smaller customers barely noticed. Support tickets said "the orders page hangs", and the on-call engineer saw no errors, no deadlocks and no CPU spike on the database.

It took two days to find. Query Store showed nothing slow, because no single query was slow. Every query took about 10 ms, round trip included. There were just 901 of them per request.

Root cause in one line: lazy loading was enabled, and the DTO mapping touched `order.Lines` once per order, which turned one query into one plus N.

After this article, you will be able to explain N+1 queries and how to find them, choose between tracking, no-tracking and identity resolution, explain cartesian explosion and when split queries fix it, and say exactly what compiled queries save and what they do not.

## Q1. What is the N+1 query problem, and how does it show up in EF Core?

**What they're actually testing:** Whether you understand that the cost is round trips, not query complexity. They also want to know if you can name the EF Core features that cause it.

**The analogy:** You need 900 items from a warehouse, so you walk to the shelf, bring back one item, walk back for the next, and repeat. Each trip is quick. The day is gone.

**The code:**
```csharp
public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public string Status { get; set; } = "New";
    public DateTime CreatedAt { get; set; }
    public virtual Customer Customer { get; set; } = null!;
    public virtual List<OrderLine> Lines { get; set; } = [];
    public virtual List<Shipment> Shipments { get; set; } = [];
}

// 1 query for the orders...
var orders = await db.Orders.Where(o => o.CustomerId == id).ToListAsync(ct);

// ...then N more, one per order, when lazy loading is enabled
var totals = orders.Select(o => o.Lines.Sum(l => l.Price * l.Quantity)).ToList();
```

**Say this in the interview:**
> N+1 is one query to load a list, then one extra query per item to load related data. In EF Core it usually comes from lazy loading, or from explicit loads or extra queries inside a loop. Each query is fast, so nothing looks slow in isolation. The latency comes from N network round trips stacked one after another.

**The trap / follow-up:** "Why did it only hurt some customers?" Because N is data-dependent. A customer with 5 orders makes 6 queries and nobody notices. A customer with 900 orders makes 901. Your test data rarely has the long tail that production has.

**Memory hook:** *Fast queries, multiplied by N, make a slow page.*

![How 80 ms became 9 s](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/02-gif-flow-1.gif)

---

## Q2. How would you detect N+1 queries in an existing application?

**What they're actually testing:** Whether you debug with evidence. They want to hear "count the commands per request", not "I would review the code".

**The analogy:** A slow checkout line is not one slow customer. You find it by counting how many times the cashier walks to the back room.

**The code:**
```csharp
builder.Services.AddDbContext<AppDbContext>(options => options
    .UseSqlServer(connectionString)
    .LogTo(
        Console.WriteLine,
        [DbLoggerCategory.Database.Command.Name],
        LogLevel.Information));

// See the SQL for a single LINQ query without running it
string sql = db.Orders.Where(o => o.CustomerId == id).ToQueryString();
```

**Say this in the interview:**
> In development I log the `Database.Command` category and look for the same SQL repeated with different parameter values. In production I look at the number of SQL dependency calls per request in Application Insights or OpenTelemetry traces, not at query duration. A request with hundreds of near-identical dependency calls is N+1.

**The trap / follow-up:** "Query Store shows no slow queries, so the database is fine, right?" Wrong signal. Query Store aggregates by query, so a fast query executed 900 times per request looks healthy. Look at execution count and per-request call counts instead.

**Memory hook:** *Count queries, not milliseconds.*

---

## Q3. How do you fix N+1: `Include`, projection, or something else?

**What they're actually testing:** Whether you know that `Include` is not the only answer, and that projection is often the better one for read endpoints.

**The analogy:** `Include` brings the whole filing cabinet to your desk. Projection brings a photocopy of the three lines you needed.

**The code:**
```csharp
// Option A: eager load full entities (needed if you will modify them)
var orders = await db.Orders
    .Include(o => o.Lines)
    .Where(o => o.CustomerId == id)
    .ToListAsync(ct);

// Option B: project exactly what the endpoint returns
var summaries = await db.Orders
    .Where(o => o.CustomerId == id)
    .Select(o => new OrderSummary(o.Id, o.Lines.Sum(l => l.Price * l.Quantity)))
    .ToListAsync(ct);

public record OrderSummary(int Id, decimal Total);
```

**Say this in the interview:**
> Both fix N+1 by turning N+1 round trips into one. `Include` loads full entities and the related rows, which I use when I need entities to update. For read endpoints I prefer a `Select` projection into a DTO. EF Core translates the aggregate into SQL, fetches only the columns I list, and the result is not tracked.

**The trap / follow-up:** "What happens if you add `Include` to a query that ends in `Select`?" If the projection does not return the entity type, the `Include` is ignored. The projection already decides what gets loaded. Candidates often stack both and assume `Include` is doing work.

**Memory hook:** *Include for writes, Select for reads.*

![Loading related data in EF Core](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/03-table-1.png)

The animation below walks through the exact change that fixed the endpoint from the opening story.

![From N+1 to one query](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/04-gif-code-1.gif)

---

## Q4. Should you enable lazy loading in an ASP.NET Core API?

**What they're actually testing:** Whether you understand that lazy loading hides database calls inside property getters, and why that is risky in request-scoped code.

**The analogy:** A light switch that also orders a pizza. Harmless once. Dangerous when someone flips it in a loop.

**The code:**
```csharp
// Opt-in: requires Microsoft.EntityFrameworkCore.Proxies and virtual navigations
options.UseSqlServer(connectionString).UseLazyLoadingProxies();

// Preferred in APIs: load related data on purpose, where you can see it
var order = await db.Orders.SingleAsync(o => o.Id == id, ct);
await db.Entry(order).Collection(o => o.Lines).LoadAsync(ct);
```

**Say this in the interview:**
> Lazy loading is off by default in EF Core and needs either the Proxies package with virtual navigations or an injected `ILazyLoader`. I avoid it in APIs because any property access can become a database call, including inside mappers and serializers. I prefer explicit `Include`, projection, or explicit loading so every query is visible in the code.

**The trap / follow-up:** "What happens if a lazy navigation is accessed after the `DbContext` is disposed?" EF Core throws an `InvalidOperationException` by default, because the `LazyLoadOnDisposedContextWarning` is configured as an error. This often shows up when entities are returned from a service and serialized after the scope ends.

**Memory hook:** *If a getter can hit the database, a loop can hit it 900 times.*

---

## Q5. What does change tracking cost, and when do you use `AsNoTracking`?

**What they're actually testing:** Whether you know what the change tracker actually stores, not just that "no-tracking is faster".

**The analogy:** Tracking is a librarian who photocopies every book you borrow so they can spot your pencil marks later. If you only came to read, skip the photocopies.

**The code:**
```csharp
// Per query
var orders = await db.Orders
    .AsNoTracking()
    .Where(o => o.CustomerId == id)
    .ToListAsync(ct);

// Or as the default for a read-heavy context; opt back in with AsTracking()
options.UseSqlServer(connectionString)
       .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking);
```

**Say this in the interview:**
> A tracked query registers every entity in the change tracker, keeps a snapshot of its original values and maintains an identity map so each key maps to one instance. `SaveChanges` then compares current values with those snapshots. For read-only queries that work is wasted, so I use `AsNoTracking`, or set no-tracking as the default on contexts that mostly read.

**The trap / follow-up:** "Is a projection into a DTO tracked?" No. Only entity instances are tracked. But if your projection contains an entity, for example `new { o.Id, o.Customer }`, that `Customer` is tracked in a tracking query. And never quote a speedup figure you have not measured; say you would benchmark it with BenchmarkDotNet on realistic data.

**Memory hook:** *Read-only data does not need a receipt.*

![Tracking vs AsNoTracking](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/05-diagram-compare-1.png)

---

## Q6. What is the difference between `AsNoTracking` and `AsNoTrackingWithIdentityResolution`?

**What they're actually testing:** Whether you know that no-tracking queries can return duplicate object instances, and how to get a clean graph without full tracking.

**The analogy:** A guest list where the same person appears on every line they RSVP'd for. Identity resolution merges those lines into one person, without keeping a permanent file on them.

**The code:**
```csharp
// Assume both orders belong to the same customer
var orders = await db.Orders
    .AsNoTracking()
    .Include(o => o.Customer)
    .ToListAsync(ct);

bool sameInstance = ReferenceEquals(orders[0].Customer, orders[1].Customer); // false

var resolved = await db.Orders
    .AsNoTrackingWithIdentityResolution()
    .Include(o => o.Customer)
    .ToListAsync(ct);
// One Customer instance per key; nothing stays tracked after the query
```

**Say this in the interview:**
> Plain `AsNoTracking` creates a new instance for every row, so a customer shared by 100 orders becomes 100 `Customer` objects. `AsNoTrackingWithIdentityResolution`, added in EF Core 5, uses a temporary tracker during the query to return one instance per key, then discards it. I use it for read-only graphs with shared references where duplicate instances waste memory or break reference-based logic.

**The trap / follow-up:** "Is identity resolution free?" No. It does some of the tracker's work during materialization, so it costs more than plain no-tracking. Use it when the graph has real shared references, not by default.

**Memory hook:** *No-tracking forgets who is who. Identity resolution remembers until the query ends.*

![Query tracking modes](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/06-table-2.png)

---

## Q7. A developer loads an entity with `AsNoTracking`, changes it and calls `SaveChanges`. What happens?

**What they're actually testing:** Whether you understand that `SaveChanges` only writes what the context is tracking, and whether you know the cost of `Update`.

**The analogy:** You edit a photocopy of a contract and hand it back. The original in the filing cabinet does not change.

**The code:**
```csharp
var order = await db.Orders.AsNoTracking().SingleAsync(o => o.Id == id, ct);
order.Status = "Shipped";
await db.SaveChangesAsync(ct);      // writes nothing: the context never saw this entity

// Narrow fix: attach and mark only the changed property
db.Orders.Attach(order);
db.Entry(order).Property(o => o.Status).IsModified = true;
await db.SaveChangesAsync(ct);      // UPDATE ... SET Status = @p0 WHERE Id = @p1
```

**Say this in the interview:**
> Nothing is saved, and no error is thrown, because the entity is not in the change tracker. For update flows I either load the entity with tracking, or attach it and mark the specific properties as modified. For set-based updates I skip loading entirely and use `ExecuteUpdateAsync`.

**The trap / follow-up:** "Why not just call `db.Orders.Update(order)`?" `Update` marks every property of the entity as modified and also walks reachable navigations, so the SQL updates all columns and can touch related rows you did not intend to change. It can also overwrite another user's changes unless you have a concurrency token.

**Memory hook:** *If the context did not see it, SaveChanges will not save it.*

---

## Q8. What is cartesian explosion, and how do you recognize it?

**What they're actually testing:** Whether you know what SQL `Include` generates, and why including two collections in one query can return far more rows than you have data.

**The analogy:** Seating every guest at every table to find out who sat where. Correct in the end, but the room is full.

**The code:**
```csharp
// One SQL statement with two collection JOINs
var orders = await db.Orders
    .Include(o => o.Lines)
    .Include(o => o.Shipments)
    .Where(o => o.CustomerId == id)
    .ToListAsync(ct);
```

**Say this in the interview:**
> By default EF Core loads includes in a single SQL query using JOINs. When you include two sibling collections, each parent row is multiplied by the size of both collections. An order with 50 lines and 20 shipments returns 1,000 rows, and the parent's columns repeat on every one. EF Core then deduplicates it all back into objects in memory.

**The trap / follow-up:** "Does EF Core warn you?" Yes. When a query includes more than one collection navigation and no query splitting behavior is configured, EF Core logs `MultipleCollectionIncludeWarning`. Even a single collection duplicates the parent's columns, which hurts when the parent has wide columns such as large text or JSON.

**Memory hook:** *Two collections in one JOIN multiply; they do not add.*

![One order, 4 MB on the wire](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/07-diagram-flow-1.png)

---

## Q9. How do split queries work, and what do they cost?

**What they're actually testing:** Whether you know `AsSplitQuery` as a targeted tool with real trade-offs, not a setting to turn on everywhere.

**The analogy:** Instead of one giant delivery with every box packed inside every other box, you get three smaller trucks that arrive one after another.

**The code:**
```csharp
var orders = await db.Orders
    .Include(o => o.Lines)
    .Include(o => o.Shipments)
    .Where(o => o.CustomerId == id)
    .AsSplitQuery()
    .ToListAsync(ct);

// Or make split the default and opt individual queries back with AsSingleQuery()
options.UseSqlServer(connectionString,
    sql => sql.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery));
```

**Say this in the interview:**
> `AsSplitQuery`, available since EF Core 5, sends one SQL query for the parent rows and one per included collection, each joined back to the same filter. Rows grow by addition instead of multiplication. The costs are extra round trips and no consistency guarantee between the statements, because data can change between them. I use it when a query includes multiple or large collections, and I measure against the single-query version.

**The trap / follow-up:** "What about paging with split queries?" Each split query repeats the `Skip`/`Take`, so the ordering must be unique or each statement can pick a different page of parents. Order by a unique key, for example `OrderBy(o => o.CreatedAt).ThenBy(o => o.Id)`. If you need a consistent view across the statements, run them inside a transaction with snapshot or serializable isolation.

**Memory hook:** *Split trades row explosion for round trips.*

![Single query vs split query](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/08-table-3.png)

---

## Q10. What does a compiled query actually save, and when is it worth it?

**What they're actually testing:** Whether you know EF Core already caches query translation, so compiled queries remove a smaller, specific cost. Candidates often overstate the benefit.

**The analogy:** A regular customer who orders "the usual". The kitchen already knows the recipe either way; the usual just skips reading the menu and confirming the order.

**The code:**
```csharp
public static class OrderQueries
{
    public static readonly Func<AppDbContext, int, Task<Order?>> ById =
        EF.CompileAsyncQuery((AppDbContext db, int id) =>
            db.Orders.AsNoTracking().FirstOrDefault(o => o.Id == id));

    public static readonly Func<AppDbContext, int, IAsyncEnumerable<Order>> ByCustomer =
        EF.CompileAsyncQuery((AppDbContext db, int customerId) =>
            db.Orders.AsNoTracking().Where(o => o.CustomerId == customerId));
}

// Usage
Order? order = await OrderQueries.ById(db, 42);
await foreach (var o in OrderQueries.ByCustomer(db, 7)) { /* ... */ }
```

**Say this in the interview:**
> EF Core caches the SQL translation for each query shape, so a normal LINQ query is not re-translated on every call. It still builds the expression tree, extracts parameters and looks the tree up in the query cache each time. `EF.CompileAsyncQuery` does that work once and gives me a delegate. The saving is per-call CPU in EF itself, so it only matters on very hot queries, and I would confirm it with a benchmark.

**The trap / follow-up:** "Is that the same as a compiled model?" No. A compiled model, generated with `dotnet ef dbcontext optimize` since EF Core 6, reduces startup time for large models. Compiled queries reduce per-execution overhead. Also, a compiled query has a fixed shape: you cannot add `Where` or `OrderBy` to its result and have it run in SQL.

**Memory hook:** *Compiled queries skip the cache lookup, not the database.*

![What runs on every EF Core query execution](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/09-diagram-layers-1.png)

---

## Q11. Why can two queries that look the same produce different SQL text, and why does it matter?

**What they're actually testing:** Whether you understand parameterization at two levels: EF Core's query cache and SQL Server's plan cache. Also whether you can spot SQL injection in raw SQL calls.

**The analogy:** A form with a blank to fill in can be photocopied once. A form with the name pre-printed has to be reprinted for every person.

**The code:**
```csharp
// Parameterized: one SQL text, one cached plan, safe from injection
var safe = await db.Orders
    .FromSql($"SELECT * FROM Orders WHERE Status = {status}")
    .ToListAsync(ct);

// Concatenated: new SQL text for every value, and an injection hole
// status = "x' OR 1=1 --" returns every row
var unsafeQuery = await db.Orders
    .FromSqlRaw("SELECT * FROM Orders WHERE Status = '" + status + "'")
    .ToListAsync(ct);

// LINQ: a captured variable becomes a parameter automatically
var linq = await db.Orders.Where(o => o.Status == status).ToListAsync(ct);
```

**Say this in the interview:**
> In LINQ, captured variables become SQL parameters, so one query shape gives one SQL text and one cached plan. `FromSql`, added in EF Core 7, turns interpolated values into parameters too. Concatenating values into `FromSqlRaw` creates new SQL text for every value, which can fill the SQL Server plan cache with single-use plans and opens a SQL injection hole.

**The trap / follow-up:** "Can parameterization make things worse?" Yes, through parameter sniffing: SQL Server compiles one plan for the first parameter value it sees, which can be a poor plan for very different values. The answer is to diagnose it in Query Store and fix it at the database level, for example with a forced plan or a query hint, not to stop parameterizing.

**Memory hook:** *Parameters for values, never string concatenation.*

---

## Q12. You need to expire 50,000 old orders. How do you do it with EF Core?

**What they're actually testing:** Whether you reach for set-based updates instead of loading thousands of entities into the change tracker, and whether you know what you give up.

**The analogy:** You do not phone 50,000 customers one at a time to tell them a policy changed. You send one notice.

**The code:**
```csharp
var cutoff = DateTime.UtcNow.AddDays(-30);

int expired = await db.Orders
    .Where(o => o.Status == "New" && o.CreatedAt < cutoff)
    .ExecuteUpdateAsync(s => s.SetProperty(o => o.Status, "Expired"), ct);

int purged = await db.Orders
    .Where(o => o.Status == "Expired" && o.CreatedAt < cutoff.AddYears(-1))
    .ExecuteDeleteAsync(ct);
```

**Say this in the interview:**
> I use `ExecuteUpdateAsync` and `ExecuteDeleteAsync`, available since EF Core 7. They translate to a single `UPDATE` or `DELETE` statement and run immediately, without loading entities or calling `SaveChanges`. That replaces 50,000 materialized entities and a large batched save with one statement.

**The trap / follow-up:** "What do you lose?" They bypass the change tracker, so entities already tracked in the same context keep their old values. `SaveChanges` interceptors and logic in overridden `SaveChanges` do not run. They are not part of the implicit `SaveChanges` transaction, so if they must commit together with other changes, open an explicit transaction with `BeginTransactionAsync`; they join it. Since EF Core 10, the setters argument can be a regular lambda, which makes conditional setters easier to write.

**Memory hook:** *Set-based work deserves a set-based statement.*

Use the table below as a quick map from the symptom you see to the question that explains it.

![EF Core performance: symptom to fix](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/10-table-4.png)

Screenshot this before your interview.

![60-Second Revision](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/images/11-revision.png)

## 5-Question Self-Check

1. Why does an N+1 problem often not appear in Query Store as a slow query?
2. What happens to an `Include` when the query ends in a `Select` that does not return the entity?
3. You load an entity with `AsNoTracking`, change a property and call `SaveChanges`. What is written to the database?
4. An order with 30 lines and 10 shipments is loaded with two collection `Include` calls in single-query mode. How many rows come back?
5. EF Core already caches query translation. What does `EF.CompileAsyncQuery` save?

**Answers:**

1. Each query is fast; the cost is the number of executions per request, which per-query statistics hide.
2. It is ignored, because the projection decides what is loaded.
3. Nothing, because the context is not tracking that entity.
4. 300 rows, because the JOINs multiply 30 by 10.
5. Building the expression tree, extracting parameters and looking up the query cache on every call.

## Coming next

Fast queries do not help if a message is processed twice or lost in a retry loop. Next, we cover Azure Service Bus in production: how retries and lock renewal actually behave, when messages land in the dead-letter queue, how sessions give you ordering, and how to build idempotent consumers that survive redelivery.

**Which question came up in your interview that isn't here? Drop it in the responses — I'll add it to the next revision with credit.**
