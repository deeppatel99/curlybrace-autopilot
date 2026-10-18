# Review — Untitled

- Mode: `local`
- Tags: 
- Visuals: 10
- Claude usage: 6 in / 54,246 out tokens (Claude subscription — no extra charge)

## Your checklist

- [ ] Open D:\Claude-Workflows\Curlybrace_Autopilot\out\2026-10-18-untitled\paste.html in Chrome, Ctrl+A, Ctrl+C, paste into a new Medium story.
- [ ] Tags to add: 

## Format check

- Front matter is not valid YAML: mapping values are not allowed here
  in "<unicode string>", line 1, column 36:
    title: DI Lifetimes in ASP.NET Core: The Captive Dependency That Le ... 
                                       ^
- 'What they're actually testing' appears 0x for 12 questions.
- Expected exactly 5 tags, got 0: []

## AI reviewer report

VERDICT: NEEDS FIXES

## Issues

- [severity: high] [location: Q2 code / hook] The central example does not produce the symptoms the article describes. `PriceCatalog.GetPriceAsync` uses `.Select(p => p.Price).SingleAsync()`, and a scalar projection is not tracked by the change tracker. Every call therefore goes to the database and returns the current price. That means no stale prices and no memory growth from tracking. Only the concurrency exception would actually occur. A careful reader will notice that the hook's "old prices" and "memory climbed" cannot come from this code. -> Query the entity so it gets tracked:
  ```csharp
  public async Task<decimal> GetPriceAsync(int id) =>
      (await db.Products.FirstAsync(p => p.Id == id)).Price;
  ```
  or use `(await db.Products.FindAsync(id))!.Price`. Then add one sentence: "Because the entity is tracked, later calls return the tracked instance, so its price never refreshes." This also makes Q2 consistent with the `FindAsync` demo in Q3.

- [severity: medium] [location: Q5 "Say this" + asset "What each check catches"] The text says ValidateOnBuild "fails fast on missing dependencies and scoped-in-singleton chains." That is only true when ValidateScopes is also enabled. With `ValidateOnBuild = true` and `ValidateScopes = false`, the build checks only that every service can be constructed (missing registrations, unresolvable constructors). It does not report lifetime violations. -> Say this: "fails fast on missing dependencies and, when ValidateScopes is also on, on scoped-in-singleton chains." In the table, change ValidateOnBuild "Catches" to "Missing deps; scoped-in-singleton chains (with ValidateScopes on)".

- [severity: medium] [location: Q2 trap] The text says injecting `IServiceProvider` into the singleton "only hides the problem from validation." That is wrong for ValidateScopes. Resolving a scoped service from the root provider throws "Cannot resolve scoped service ... from root provider" at resolution time. The code in Q5 relies on exactly this behaviour, so the two sections contradict each other. -> Replace with: "It hides the problem from ValidateOnBuild, which cannot see runtime resolution. ValidateScopes still throws when the scoped service is resolved from the root, but only on that code path, and only where validation is on. In Production you silently get a root-level context."

- [severity: low] [location: Q3 trap] The question "What if the singleton grabbed the context from the first request instead of the root?" suggests constructor injection could do this. It cannot. Microsoft.Extensions.DependencyInjection always resolves a singleton's dependencies from the root, even when the first resolution happens inside a request. -> Change the setup to: "What if a request passed its own context to the singleton, for example through a method or property, and the singleton stored it?" Keep the `ObjectDisposedException` answer.

- [severity: low] [location: asset "Service lifetimes at a glance"] The Scoped row says "Once per scope (one per HTTP request)". The Q1 trap directly above it says scoped does not mean per request. -> Change the cell to "Once per scope (per HTTP request in ASP.NET Core)".

- [severity: low] [location: Q4 trap] The question is "Should it be on in production?", but the answer never says yes or no for ValidateScopes. "Development defaults are the floor, not the ceiling" is vague. -> State it plainly: "ValidateScopes adds a check on resolution, so most teams keep it off in Production and rely on non-production environments plus a CI startup test. ValidateOnBuild only costs startup time, so enabling it everywhere is reasonable."

- [severity: low] [location: Q11 code] The bug comment refers to `RatesClient`, which is never defined. The registration is also a named client (`"rates"`), not a typed client, although the question is about typed clients. -> Either add `// builder.Services.AddHttpClient<RatesClient>(...)` next to the bug comment, or rename the question to "a typed or named HttpClient".

- [severity: low] [location: Q6 asset "A scope per tick in a BackgroundService"] The GIF repeats the Q6 code block almost line for line. It adds nothing the code and "Say this" do not already show. -> Either remove it, or contrast it with the wrong version (one scope created above the loop) so the animation shows the difference between the two.

- [severity: low] [location: Q3 asset "Life of a captured DbContext"] This flow largely restates the hook GIF and the Q3 "Say this" (stale reads, memory growth, overlapping requests). -> Remove it, or replace it with something new, such as a timeline showing `ChangeTracker.Entries().Count()` growing per request alongside the moment the second operation fails.

- [severity: low] [location: Q2 asset "Who owns what"] The layers diagram repeats the ownership and disposal rules already covered by the Q1 table and the Q1 "Say this". The "Who can safely depend on whom" table already carries the rule. -> Remove the layers diagram, or keep only "The rule" layer as a callout line in the prose.

- [severity: low] [location: Q6 code] `ExecuteAsync` has no try/catch around a unit of work. Since .NET 6, an unhandled exception in a `BackgroundService` stops the host by default. This matters for an interview answer about production workers. -> Wrap each tick's body in try/catch, log the failure, and continue. Alternatively, add one line to the trap mentioning `BackgroundServiceExceptionBehavior`.

- [severity: low] [location: Q8 code] A custom `IClock`/`SystemClock` ignores the built-in `TimeProvider` (.NET 8+), and the article targets .NET 10. The name `SystemClock` also collides with existing ASP.NET Core and caching types if someone pastes the code into a web project. -> Use `TimeProvider.System` registered as a singleton, or rename to `UtcClock`.

## Fact-check notes for the author

- Confirm that ValidateOnBuild reports scoped-in-singleton only when ValidateScopes is also true. Check: learn.microsoft.com, "Dependency injection in .NET" → "Scope validation", and the `ServiceProviderOptions.ValidateOnBuild` API docs. The runtime source (`ServiceProvider` constructor and `CallSiteValidator`) is definitive.
- Confirm that both options default to `IsDevelopment()` for `WebApplicationBuilder` and the generic host. Check: "Dependency injection in ASP.NET Core" → "Scope validation".
- Confirm that ValidateOnBuild skips open generic registrations. Check: the `ServiceProviderOptions.ValidateOnBuild` remarks.
- Confirm that scalar projections are untracked, and that `FindAsync` returns the tracked instance without a query. Check: EF Core docs, "Tracking vs. No-Tracking Queries" → "Tracking and custom projections", and "Querying data" → "Find".
- Confirm that EF Core's concurrent-use detection is best-effort and that MARS does not make DbContext thread-safe. Check: EF Core docs, "DbContext Lifetime, Configuration, and Initialization" → "Avoiding DbContext threading issues".
- Confirm that `AddDbContextFactory` defaults to a singleton lifetime and also registers the context type as scoped (EF Core 6+). Check: "DbContext Lifetime..." → "Using a DbContext factory".
- Confirm that `CreateAsyncScope` was introduced in .NET 6, and that disposing a scope synchronously throws for services that implement only `IAsyncDisposable`. Check: the `ServiceProviderServiceExtensions.CreateAsyncScope` API docs.
- Confirm that typed clients are registered as transient and must not be captured in singletons, and check the `PooledConnectionLifetime` guidance. Check: "Use IHttpClientFactory to implement resilient HTTP requests" and "Guidelines for using HttpClient".
- Confirm that conventional middleware is constructed once with the root provider, so constructor injection of a scoped service throws under ValidateScopes. Check: "Write custom ASP.NET Core middleware" → "Per-request middleware dependencies".
- Confirm that the self-check answer 1 wording matches the real output. At `builder.Build()` with ValidateOnBuild on, the error is wrapped in `AggregateException: Some services are not able to be constructed`, and the inner exception carries "Cannot consume scoped service 'AppDbContext' from singleton 'PriceCatalog'."
- House style: confirm the CTA matches the required exact text character for character, including the em dash, and that "Aspnetcore" is the publication's required lead tag.
