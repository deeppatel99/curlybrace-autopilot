# Untitled

## 

![DI Lifetimes and the Captive Dependency Bug](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/01-cover.png)

A pricing API had been stable for months. Then, after a routine release, support tickets started to arrive. Customers saw old prices at checkout, and roughly one request in a few hundred failed with a 500.

The logs showed `InvalidOperationException: A second operation was started on this context instance before a previous operation completed.` Memory on each instance climbed steadily, and the pods were being restarted every couple of days. Nobody linked the three symptoms together.

It took three days to find. Locally everything worked, because the team ran with `ASPNETCORE_ENVIRONMENT=Local`, a custom environment name that quietly switched off the container's scope validation.

The root cause was one line: `builder.Services.AddSingleton<PriceCatalog>();`, where `PriceCatalog` took an `AppDbContext` in its constructor. One DbContext, created once, shared by every request for the life of the process.

![How a singleton captures a DbContext](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/02-gif-flow-1.gif)

After this article you will be able to explain the three lifetimes, define a captive dependency, say exactly what `ValidateScopes` and `ValidateOnBuild` catch and what they miss, and use a DbContext safely in background services, middleware and parallel code. The samples target .NET 10 (LTS) with C# 12+ syntax and share the `AppDbContext` defined in Q2.

## Q1. What are the three service lifetimes in ASP.NET Core, and when is each instance created and disposed?

**What they're testing:** Whether you know lifetimes in terms of ownership and disposal, not only "new every time" versus "one forever".

**The analogy:** A hotel. Towels are transient: you get a fresh one each time you ask. Your room is scoped: yours for the length of your stay. The lobby is a singleton: shared by every guest for as long as the hotel is open.

**The code:**
```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddTransient<TransientDep>();
builder.Services.AddScoped<ScopedDep>();
builder.Services.AddSingleton<SingletonDep>();

var app = builder.Build();

// Call twice: t1 != t2 always, s1 == s2 within a request, g never changes.
app.MapGet("/ids", (TransientDep t1, TransientDep t2, ScopedDep s1, ScopedDep s2, SingletonDep g) =>
    new { t1 = t1.Id, t2 = t2.Id, s1 = s1.Id, s2 = s2.Id, g = g.Id });

app.Run();

public sealed class TransientDep { public Guid Id { get; } = Guid.NewGuid(); }
public sealed class ScopedDep { public Guid Id { get; } = Guid.NewGuid(); }
public sealed class SingletonDep { public Guid Id { get; } = Guid.NewGuid(); }
```

**Say this in the interview:**
> Transient creates a new instance on every resolution. Scoped creates one instance per scope, and ASP.NET Core opens one scope per HTTP request. Singleton creates one instance for the whole application, on first resolution. Disposal follows ownership: the scope disposes the scoped and transient instances it created, and the root provider disposes singletons at shutdown.

**The trap / follow-up:** "So scoped means per request?" Not exactly. Scoped means per scope. ASP.NET Core creates a scope per request, Blazor Server creates one per circuit, and in a worker or console app nothing creates a scope unless you do it yourself.

![Service lifetimes at a glance](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/03-table-1.png)

**Memory hook:** *Towel, room, lobby.*

---

## Q2. What is a captive dependency? Show one.

**What they're testing:** Whether you can spot the bug in a registration and explain why it compiles, runs, and is still wrong.

**The analogy:** You rent a car for a day, and someone welds it to their garage. The rental contract says one day, but the car now lives as long as the garage.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("Db")));
builder.Services.AddSingleton<PriceCatalog>(); // BUG: captures a scoped DbContext

var app = builder.Build();
app.MapGet("/price/{id:int}", (int id, PriceCatalog catalog) => catalog.GetPriceAsync(id));
app.Run();

public sealed class PriceCatalog(AppDbContext db)
{
    // Tracked query: later calls return the tracked instance with its old Price.
    public async Task<decimal> GetPriceAsync(int id) =>
        (await db.Products.FirstAsync(p => p.Id == id)).Price;
}

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Product> Products => Set<Product>();
    public DbSet<OutboxMessage> OutboxMessages => Set<OutboxMessage>();
}

public sealed class Product { public int Id { get; set; } public decimal Price { get; set; } }
public sealed class OutboxMessage { public int Id { get; set; } public DateTime? SentAt { get; set; } }
```

**Say this in the interview:**
> A captive dependency is a service that depends on something with a shorter lifetime, so the dependency gets held for the longer lifetime. The classic case is a singleton taking a scoped DbContext in its constructor: the singleton is built once, so one DbContext is shared by every request. Because the entity is tracked, later calls return the tracked instance, so its price never refreshes. The fix is to make the consumer scoped, or have it create short-lived contexts through IServiceScopeFactory or IDbContextFactory.

**The trap / follow-up:** "Can I inject IServiceProvider into the singleton and resolve the context later?" A singleton receives the root provider, so resolving a scoped service from it still gives you a root-level instance. It hides the problem from ValidateOnBuild, which cannot see runtime resolution. ValidateScopes still throws when the scoped service is resolved from the root, but only on that code path, and only where validation is on. In Production you silently get a root-level context. Wrapping the resolution in a factory lambda has the same effect.

The rule: a service may depend only on services that live at least as long as it does.

![Who can safely depend on whom](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/04-table-2.png)

**Memory hook:** *Never let a long life hold a short one.*

---

## Q3. Why is a captured DbContext worse than most captive dependencies?

**What they're testing:** Whether you understand DbContext internals: the change tracker, identity resolution and lack of thread safety.

**The analogy:** A shared notebook at a busy reception desk. Everyone writes in it, nobody tears pages out, and two people cannot write at the same time.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;

static async Task ShowStaleRead(AppDbContext db)
{
    var first = await db.Products.FindAsync(42);   // queries the database, starts tracking
    // ...another process updates the price of product 42 here...
    var second = await db.Products.FindAsync(42);  // served from the change tracker
    Console.WriteLine(ReferenceEquals(first, second)); // True: same object, old price
    Console.WriteLine(db.ChangeTracker.Entries().Count()); // grows with every tracked query
}
```

**Say this in the interview:**
> A DbContext is a unit of work designed to live for one operation. When it is captured, its change tracker keeps every tracked entity, so memory grows and reads return stale tracked values instead of fresh data. It is also not thread-safe, so two overlapping requests produce "A second operation was started on this context instance" exceptions, or worse, silent corruption.

**The trap / follow-up:** "What if a request passed its own context to the singleton, for example through a method or property, and the singleton stored it?" Then the request scope disposes it, and every later call throws `ObjectDisposedException` ("Cannot access a disposed context instance"). Note that a captured context does not normally leak connections: EF Core opens and closes the connection per operation unless you open it yourself.

![One captured context over time](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/05-diagram-flow-1.png)

**Memory hook:** *A DbContext is a unit of work, not a connection pool.*

---

## Q4. What does ValidateScopes do, and why did this bug pass every local test?

**What they're testing:** Whether you know that validation is environment-dependent, and how to turn it on deliberately.

**The analogy:** A smoke detector that only works when the "test mode" switch is on. Someone renamed the switch, and nobody noticed it was off.

**The code:**
```csharp
var builder = WebApplication.CreateBuilder(args);

// On by default only when the environment is Development.
// Set it explicitly so a custom environment name cannot switch it off.
builder.Host.UseDefaultServiceProvider(options =>
{
    options.ValidateScopes = !builder.Environment.IsProduction();
    options.ValidateOnBuild = true;
});
```

**Say this in the interview:**
> ValidateScopes makes the container throw when a scoped service is consumed by a singleton or resolved from the root provider. The messages are "Cannot consume scoped service from singleton" and "Cannot resolve scoped service from root provider". ASP.NET Core enables it by default only in the Development environment, so a custom environment name or a production-only code path skips it. I set it explicitly with UseDefaultServiceProvider.

**The trap / follow-up:** "Should it be on in production?" ValidateScopes adds a check on resolution, so most teams keep it off in Production and rely on non-production environments plus a CI startup test. ValidateOnBuild only costs startup time, so enabling it everywhere is reasonable.

**Memory hook:** *Development-only validation is only as good as your environment name.*

---

## Q5. What does ValidateOnBuild catch, and what can still slip past it?

**What they're testing:** Whether you treat validation as a safety net with known holes, not a guarantee.

**The analogy:** An airport scanner checks every bag on the belt. It cannot check what someone hands you after security.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

var services = new ServiceCollection();
services.AddDbContext<AppDbContext>(o => o.UseSqlServer("Server=.;Database=Shop"));

// Caught at build: the container can read PriceCatalog's constructor.
// services.AddSingleton<PriceCatalog>();

// Not caught at build: the container cannot see inside the lambda.
services.AddSingleton(sp => new PriceCatalog(sp.GetRequiredService<AppDbContext>()));

using var provider = services.BuildServiceProvider(new ServiceProviderOptions
{
    ValidateScopes = true,
    ValidateOnBuild = true
});

// Only throws here, on first resolution, because ValidateScopes is on.
var catalog = provider.GetRequiredService<PriceCatalog>();
```

**Say this in the interview:**
> ValidateOnBuild, available since .NET Core 3.0, walks every registration when the provider is built and fails fast on missing dependencies and, when ValidateScopes is also on, on scoped-in-singleton chains. It cannot see inside factory lambdas and it skips open generic registrations. It also never flags a singleton holding a transient, because that is legal.

**The trap / follow-up:** "How do you protect against the factory case?" Keep ValidateScopes on in test environments and actually resolve the service: an integration test that boots the host in Development and calls the main endpoints will hit it. Better still, avoid factory registrations unless you need them.

![What each check catches](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/06-table-3.png)

**Memory hook:** *The container can read constructors, not lambdas.*

---

## Q6. How do you use a DbContext inside a BackgroundService?

**What they're testing:** Whether you know hosted services are singletons, and how to create a scope per unit of work.

**The analogy:** A night-shift worker does not keep one cup of coffee for the whole year. They make a fresh one every round.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;

// Registration: builder.Services.AddHostedService<OutboxWorker>();
public sealed class OutboxWorker(IServiceScopeFactory scopeFactory, ILogger<OutboxWorker> logger)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(10));
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                await using var scope = scopeFactory.CreateAsyncScope();
                var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

                var batch = await db.OutboxMessages
                    .Where(m => m.SentAt == null)
                    .Take(100)
                    .ToListAsync(stoppingToken);

                foreach (var message in batch)
                    message.SentAt = DateTime.UtcNow; // publish first in real code

                await db.SaveChangesAsync(stoppingToken);
                logger.LogInformation("Sent {Count} outbox messages", batch.Count);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                // Since .NET 6 an unhandled exception here stops the host by default.
                logger.LogError(ex, "Outbox tick failed; retrying on the next tick");
            }
        }
    }
}
```

**Say this in the interview:**
> AddHostedService registers the worker as a singleton, so injecting a DbContext into its constructor is a captive dependency. I inject IServiceScopeFactory and create an async scope for each unit of work, resolve the DbContext from that scope, and let await using dispose it. CreateAsyncScope, added in .NET 6, matters because it disposes services that only implement IAsyncDisposable correctly.

![Wrong scope vs right scope in a worker](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/07-gif-code-1.gif)

**The trap / follow-up:** "Why not create one scope at the top of ExecuteAsync?" That scope lives as long as the worker, so you have rebuilt the captive dependency by hand. The scope must match the unit of work: one tick, one message or one batch.

**Memory hook:** *One unit of work, one scope.*

---

## Q7. IServiceScopeFactory or IDbContextFactory: when do you pick which?

**What they're testing:** Whether you choose the narrowest tool and understand who owns disposal.

**The analogy:** Booking a whole hotel room versus borrowing one towel. If you only need the towel, don't book the room.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContextFactory<AppDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("Db")));
builder.Services.AddSingleton<ReportService>(); // safe: the factory is a singleton

public sealed class ReportService(IDbContextFactory<AppDbContext> contextFactory)
{
    public async Task<int> CountProductsAsync(CancellationToken ct)
    {
        await using var db = await contextFactory.CreateDbContextAsync(ct);
        return await db.Products.CountAsync(ct);
    }
}
```

**Say this in the interview:**
> If the work only needs a DbContext, I use IDbContextFactory: it is registered as a singleton by default, so any service can inject it, and I own the disposal of each context I create. If the work needs other scoped services, like repositories or handlers that themselves take the DbContext, I use IServiceScopeFactory so the whole graph shares one scope.

**The trap / follow-up:** "Can you mix them?" A context from the factory is a separate instance from the scoped one, so a repository using the scoped context and your code using a factory context are two units of work with two transactions. Pick one per operation.

![IServiceScopeFactory vs IDbContextFactory](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/08-diagram-compare-1.png)

**Memory hook:** *Room for a graph, towel for a context.*

---

## Q8. Is it safe for a singleton to depend on a transient service?

**What they're testing:** Whether you know that validation stays silent here, and that transient disposables resolved from the root leak.

**The analogy:** A disposable cup handed to a permanent desk becomes a permanent cup. Fine if it's metal; not fine if it was meant to be thrown away.

**The code:**
```csharp
using Microsoft.Extensions.DependencyInjection;

var services = new ServiceCollection();
services.AddTransient<IClock, UtcClock>();
services.AddSingleton<TokenIssuer>(); // holds one IClock forever: fine, it is stateless
services.AddTransient<ExportWriter>();

using var root = services.BuildServiceProvider();

for (var i = 0; i < 10_000; i++)
    _ = root.GetRequiredService<ExportWriter>(); // root keeps all 10,000 until it is disposed

using (var scope = root.CreateScope())
    _ = scope.ServiceProvider.GetRequiredService<ExportWriter>(); // released with the scope

public interface IClock { DateTimeOffset UtcNow { get; } }
public sealed class UtcClock : IClock { public DateTimeOffset UtcNow => DateTimeOffset.UtcNow; }
public sealed class TokenIssuer(IClock clock) { public DateTimeOffset IssuedAt() => clock.UtcNow; }
public sealed class ExportWriter : IDisposable { public void Dispose() { } }
```

**Say this in the interview:**
> It is legal and validation never flags it, but the transient effectively becomes a singleton. That is fine for stateless, thread-safe services and wrong for anything with per-use state or a scoped dependency of its own. Separately, transient IDisposable services resolved from the root provider are tracked until shutdown, so resolving them in a loop is a memory leak.

**The trap / follow-up:** "Does disposing the transient yourself fix the leak?" No. The root provider still holds a reference in its disposal list. Resolve it from a scope that ends, or construct it yourself if the container does not need to own it.

**Memory hook:** *A transient in a singleton is a singleton.*

---

## Q9. How do you use a scoped service, such as a DbContext, inside custom middleware?

**What they're testing:** Whether you know conventional middleware is constructed once, and where scoped services can be injected.

**The analogy:** A turnstile is installed once at the entrance. Each visitor brings their own ticket; the ticket is not bolted to the turnstile.

**The code:**
```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddScoped<TenantContext>();

var app = builder.Build();
app.UseMiddleware<TenantMiddleware>();
app.MapGet("/", (TenantContext tenant) => tenant.TenantId ?? "none");
app.Run();

public sealed class TenantMiddleware(RequestDelegate next)
{
    // Constructor runs once for the app: only singletons belong here.
    // Scoped services (TenantContext, AppDbContext) go on InvokeAsync.
    public async Task InvokeAsync(HttpContext context, TenantContext tenant)
    {
        tenant.TenantId = context.Request.Headers["X-Tenant"];
        await next(context);
    }
}

public sealed class TenantContext { public string? TenantId { get; set; } }
```

**Say this in the interview:**
> Convention-based middleware is created once when the pipeline is built, so its constructor is effectively singleton territory. Scoped services go into InvokeAsync parameters, which are resolved from the request's services on every call. The alternative is factory-based middleware: implement IMiddleware and register it with a scoped or transient lifetime, then constructor injection works per request.

**The trap / follow-up:** "What happens if I inject AppDbContext into the middleware constructor?" With scope validation on, startup fails because a scoped service is resolved from the root provider. With validation off, you get the exact bug from the introduction: one context for every request.

**Memory hook:** *Middleware constructor once, InvokeAsync every time.*

---

## Q10. A singleton needs configuration that can change at runtime. Which options interface do you inject?

**What they're testing:** Whether you know IOptionsSnapshot is scoped, and that injecting it into a singleton is a captive dependency.

**The analogy:** A printed timetable (IOptions), a timetable reprinted every morning (IOptionsSnapshot), and a live departures board (IOptionsMonitor).

**The code:**
```csharp
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);
builder.Services.Configure<FeatureOptions>(builder.Configuration.GetSection("Features"));
builder.Services.AddSingleton<FeatureGate>();

public sealed class FeatureGate(IOptionsMonitor<FeatureOptions> options)
{
    // CurrentValue reflects reloaded configuration without a restart.
    public bool IsOn(string name) => options.CurrentValue.Enabled.Contains(name);
}

public sealed class FeatureOptions { public List<string> Enabled { get; set; } = []; }
```

**Say this in the interview:**
> In a singleton I inject IOptionsMonitor and read CurrentValue each time, or subscribe with OnChange. IOptionsSnapshot is registered as scoped, so injecting it into a singleton is a captive dependency and scope validation will reject it. IOptions is a singleton too, but its value is computed once and never reflects reloads.

**The trap / follow-up:** "Can I store options.CurrentValue in a field in the constructor?" Then you have frozen it, which is the same as IOptions. Read CurrentValue at the point of use.

![Options interfaces and lifetimes](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/09-table-4.png)

**Memory hook:** *Snapshot per request, monitor forever.*

---

## Q11. Why is injecting a typed HttpClient into a singleton a problem?

**What they're testing:** Whether you recognise a captive dependency that no validation option will catch.

**The analogy:** Saving a taxi driver's personal phone number instead of calling the dispatch line. It works until that driver moves away.

**The code:**
```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHttpClient("rates", c => c.BaseAddress = new Uri("https://rates.example.com/"));
builder.Services.AddSingleton<RateCache>();

// BUG version: builder.Services.AddHttpClient<RatesClient>(...);
//              public sealed class RateCache(RatesClient client)
// The typed client is transient; the singleton pins it and its handler forever.

public sealed class RateCache(IHttpClientFactory httpClientFactory)
{
    public Task<string> GetLatestAsync(CancellationToken ct) =>
        httpClientFactory.CreateClient("rates").GetStringAsync("latest", ct);
}
```

**Say this in the interview:**
> Typed clients from AddHttpClient are registered as transient so the factory can rotate the underlying handlers. A singleton that captures one keeps the same handler for the life of the app, so it can miss DNS changes, which is the problem IHttpClientFactory exists to solve. In a singleton I inject IHttpClientFactory and create a client per call, or use a single HttpClient over a SocketsHttpHandler with PooledConnectionLifetime set.

**The trap / follow-up:** "Why didn't ValidateScopes complain?" Because a transient inside a singleton is legal as far as the container knows. Validation only understands scoped services; everything else is your responsibility.

**Memory hook:** *Call dispatch, don't keep the driver.*

---

## Q12. You want to run two queries in parallel inside one request. What goes wrong, and how do you fix it?

**What they're testing:** Whether you understand that scoped does not mean thread-safe.

**The analogy:** Two cashiers cannot share one card machine at the same moment. Give each cashier their own machine.

**The code:**
```csharp
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContextFactory<AppDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("Db")));
var app = builder.Build();

// BUG: await Task.WhenAll(db.Products.CountAsync(), db.OutboxMessages.CountAsync());
// Same scoped DbContext, two concurrent operations.

app.MapGet("/dashboard", async (IDbContextFactory<AppDbContext> factory, CancellationToken ct) =>
{
    async Task<int> RunAsync(Func<AppDbContext, Task<int>> query)
    {
        await using var db = await factory.CreateDbContextAsync(ct);
        return await query(db);
    }

    var products = RunAsync(db => db.Products.CountAsync(ct));
    var pending = RunAsync(db => db.OutboxMessages.CountAsync(m => m.SentAt == null, ct));
    await Task.WhenAll(products, pending);

    return new { products = await products, pending = await pending };
});

app.Run();
```

**Say this in the interview:**
> The request's scoped DbContext is not thread-safe, so starting two queries on it concurrently throws "A second operation was started on this context instance". If I need real parallelism, each task gets its own context from IDbContextFactory. Most of the time the better answer is to await the queries one after another, or combine them into one query.

**The trap / follow-up:** "Won't MultipleActiveResultSets fix it?" No. MARS is a SQL Server connection feature; it does not make DbContext safe for concurrent use. EF Core's detection of concurrent use is also best-effort, so the absence of an exception does not prove the code is safe.

**Memory hook:** *Scoped is not thread-safe.*

---

Screenshot this before your interview.

![60-Second Revision](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/untitled/images/10-revision.png)

## 5-Question Self-Check

1. A singleton's constructor takes `AppDbContext`. What happens by default in Development, and what happens in Production?
2. Which registration style slips past `ValidateOnBuild` but is still caught by `ValidateScopes` at first resolution?
3. What is the correct way to use a DbContext inside a `BackgroundService`?
4. A singleton needs configuration that reloads without a restart. Which interface do you inject?
5. Why does capturing a typed `HttpClient` in a singleton pass validation, and why is it still wrong?

**Answers:**

1. Development: `builder.Build()` fails with "Some services are not able to be constructed", and the inner exception reads "Cannot consume scoped service 'AppDbContext' from singleton 'PriceCatalog'"; Production: no error, one context is shared by every request.
2. A factory lambda registration, such as `AddSingleton(sp => new PriceCatalog(sp.GetRequiredService<AppDbContext>()))`.
3. Inject `IServiceScopeFactory` and create an async scope per unit of work, or inject `IDbContextFactory` and dispose each context.
4. `IOptionsMonitor<T>`, reading `CurrentValue` at the point of use.
5. Typed clients are transient, which validation ignores, but the singleton pins one handler forever and misses DNS changes.

## Coming next

Fixing the lifetime of your DbContext is step one; making it fast is step two. Next, we take EF Core performance apart: how N+1 queries hide in innocent loops, when tracking versus no-tracking actually matters, and where split queries and compiled queries earn their place.

**Which question came up in your interview that isn't here? Drop it in the responses — I'll add it to the next revision with credit.**
