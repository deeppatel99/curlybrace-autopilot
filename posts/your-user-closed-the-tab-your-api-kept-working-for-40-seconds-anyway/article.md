# Your User Closed the Tab. Your API Kept Working for 40 Seconds Anyway.

## The connection pool exhaustion that starts with a CancellationToken nobody passes on, why that parameter is worse than having none, and the places you shouldn't pass it.

![Your User Closed the Tab. Your API Kept Working for 40 Seconds Anyway.](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/images/01-cover.png)

It's 9:04 on the first Monday of the month. Month-end reporting day.

The dashboard turns red. Not just the reports page. Login, search, checkout: all of them.

The logs show one line, thousands of times:

`Timeout expired. The timeout period elapsed prior to obtaining a connection from the pool. This may have occurred because all pooled connections were in use and max pool size was reached.`

The database CPU looks fine. The servers look fine. Every connection is in use anyway, and nobody can say what is using them.

This is a reconstruction of a failure that is common in real systems, and it usually goes like this. The question it answers: **what does your API do with a request whose user has already left?**

## The first three guesses, and why each was reasonable

**Guess one: a connection leak.** The error message practically suggests it, and in older ADO.NET code it usually was a leak. But everything here goes through a scoped `DbContext` that the container disposes at the end of each request. That's worth confirming. A singleton holding a context is a classic leak (I wrote up that exact one in [DI Lifetimes in ASP.NET Core: The Captive Dependency That Leaked Our DbContext](https://medium.com/@thecurlybrace/di-lifetimes-in-asp-net-core-the-captive-dependency-that-leaked-our-dbcontext-a9c56ef3a42e)). Here, the `number-of-reclaimed-connections` counter, which counts connections the GC had to clean up because nobody disposed them, sits at zero. No leak.

**Guess two: just raise the pool size.** `Max Pool Size` defaults to 100. Someone sets it to 300 and redeploys. The pool errors stop for a few minutes. Then the database starts struggling under 300 concurrent heavy queries, and the errors come back with new friends. Raising the limit doesn't fix demand that never stops. It only moves the bottleneck.

**Guess three: the report query got slow.** It didn't. It has taken about 40 seconds for months. That is why someone set `sql => sql.CommandTimeout(120)` on the reporting context last quarter, after reports started hitting the 30-second default. Remember that line. It matters later.

## The clue: more running reports than people reading them

Someone runs this during the next spike:

```sql
SELECT r.session_id,
       r.status,
       r.total_elapsed_time / 1000 AS elapsed_s,
       s.program_name
FROM sys.dm_exec_requests AS r
JOIN sys.dm_exec_sessions AS s ON s.session_id = r.session_id
WHERE s.is_user_process = 1;
```

It returns about a hundred rows, and almost all of them are the same sales-report query. Meanwhile, the front-end analytics show roughly a third that many people actually on the reports page.

So someone tries the obvious repro. Click **Generate report**, close the tab after three seconds, then rerun the query. The session is still there. Ten seconds later, still there. It finishes at about the 40-second mark and hands its results to a browser that is no longer listening.

Now picture month-end behaviour. A user clicks Generate, waits, gets impatient and refreshes. That's two queries. They refresh again: three. Every refresh starts a new 40-second query, and none of the old ones stop.

## A kitchen that cooks for empty tables

Think of the connection pool as a kitchen with 100 burners. A customer orders, waits a while, and walks out. Nobody tells the kitchen. The cook stays at the burner for the full 40 seconds, plates the dish and carries it to an empty table. Meanwhile the queue at the door gets longer, and some of those people are the same customers who walked out and came back to order again.

The arithmetic is unforgiving. If each report holds a connection for 40 seconds, a pool of 100 is full at 100 / 40 = **2.5 report requests per second**. That's a small number for a whole company refreshing a page at 9 a.m. And once the pool is full, every other endpoint that needs a connection waits 15 seconds (the default `Connect Timeout`) and then fails.

![How a closed tab becomes an outage](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/images/02-diagram-flow-1.png)

## The root cause is a polite lie in a method signature

ASP.NET Core already knows the user left. [`HttpContext.RequestAborted`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.http.httpcontext.requestaborted) is a token that fires when the underlying connection is aborted. Add a `CancellationToken` parameter to a controller action or a minimal API handler and the framework binds that same token for you. The [minimal API binding docs](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/parameter-binding) list it as a special type that maps to `HttpContext.RequestAborted`.

The controller did this correctly. The token died one layer down:

![Where the token goes to die](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/images/03-gif-code-1.gif)

That's my position, and it's the point of this article: **a `CancellationToken` parameter you never pass on is worse than having no parameter at all.** With no parameter, a reviewer can see that cancellation is missing. With one, the signature says "this method stops when asked", the controller author believes it, the reviewer believes it, and the code ignores it. You get the cost of the feature and none of the protection.

## The fix is almost insultingly simple

Pass it on. Every call that accepts a token gets the token.

```csharp
public sealed class SalesReportService(ReportingDbContext db, HttpClient fx)
{
    public async Task<SalesReport> BuildAsync(DateTime from, DateTime to, CancellationToken ct)
    {
        var totals = await db.Orders
            .Where(o => o.PlacedAt >= from && o.PlacedAt < to)
            .GroupBy(o => o.Currency)
            .Select(g => new CurrencyTotal(g.Key, g.Sum(o => o.Amount)))
            .ToListAsync(ct);

        var rates = await fx.GetFromJsonAsync<RateTable>("rates", ct);
        return SalesReport.From(totals, rates!);
    }
}

public sealed record CurrencyTotal(string Currency, decimal Sum);
```

This assumes .NET 8+ (primary constructors are C# 12) and an ASP.NET Core project, where the Web SDK's implicit usings bring in `System.Net.Http.Json`. Add `using Microsoft.EntityFrameworkCore;` for `ToListAsync`. Note that `= default` is gone. Callers now have to decide what to pass, and that decision is the whole point.

When the token fires, EF Core hands it to SqlClient, which tells SQL Server to cancel the running command. The connection goes back to the pool instead of sitting on a burner for 40 seconds.

The exception you get can vary. In practice, depending on where the cancel lands, SqlClient can surface it as an `OperationCanceledException` or as a `SqlException`. So don't catch by type. Catch by cause, once, near the top of the pipeline:

```csharp
app.Use(async (context, next) =>
{
    try
    {
        await next(context);
    }
    catch (Exception) when (context.RequestAborted.IsCancellationRequested)
    {
        // The client is gone. Nothing to send, nobody to page.
    }
});
```

Register it after `UseExceptionHandler`, so it sits inside the error handler and sees the exception first. The built-in handler already logs aborted requests at Debug level for `OperationCanceledException`. This filter also covers the `SqlException` case.

**Verification:** repeat the repro. Click Generate, close the tab and rerun the DMV query. The session is gone. Then replay the month-end pattern with refreshes in a load test and watch `number-of-active-connections` from the [SqlClient event counters](https://learn.microsoft.com/en-us/sql/connect/ado-net/event-counters) with `dotnet-counters monitor --counters Microsoft.Data.SqlClient.EventSource -p <pid>` (the counters need Microsoft.Data.SqlClient 3.0+ on .NET Core 3.1+). It should track the number of people actually waiting, not the number of times they hit refresh.

## Where you should not pass it

Cancellation means "the caller no longer wants the answer." It doesn't mean "undo the world." Sometimes the user leaving should **not** stop the work.

![Should RequestAborted reach this call?](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/images/04-table-1.png)

When you choose not to cancel, write `CancellationToken.None` explicitly and add a comment saying why. That records the decision in the code, and it also tells the analyzer below that you meant it. For background work, take a token from `IHostApplicationLifetime` or your background service instead.

## The three ways this will still surprise you

**Your proxy may never tell you.** Kestrel can only signal `RequestAborted` when it sees its own connection close. If a reverse proxy or gateway in front of your app keeps the upstream connection open after the browser leaves, your app never finds out. Run the close-the-tab test in your real hosting setup, not just on localhost.

**Synchronous code ignores tokens entirely.** A `.ToList()` or a `.Result` deep in a call chain blocks with no token to check, and it can starve the thread pool while it waits. (That failure mode has its own article: [One Innocent Line (.Result) Froze My Entire API](https://medium.com/@thecurlybrace/one-innocent-line-result-froze-my-entire-api-i-was-blocking-async-without-knowing-it-8be867b6f4fd).)

**That `CommandTimeout(120)` hid this for months.** With the 30-second default, the reports would have failed loudly. Raising the timeout fixed the symptom and made every abandoned query live four times longer. When you raise a timeout, ask what will now be allowed to run that long without anyone waiting for it.

## Make the compiler catch the lie

The .NET SDK analyzers already include [CA2016: Forward the CancellationToken parameter to methods that take one](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2016). It flags exactly this bug: a method that receives a token and then calls something that accepts one without passing it. By default it is only a suggestion, which in practice means nobody sees it. Promote it:

```yaml
# .editorconfig
[*.cs]
dotnet_diagnostic.CA2016.severity = error
```

Expect a wall of errors the first time you build. Each one is a call that ignores the token it was given. The rule has limits, though. It only checks methods whose token is the last parameter. It can't help when a method takes no token at all, so review new async methods for a missing parameter too.

![60-Second Revision](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/images/05-revision.png)

> A cancellation token you accept and never pass on is a promise your code breaks every time a user gives up.

Tonight, set CA2016 to `error` in one service and build it. Count the errors.

Here's my question for the responses: should `= default` on a `CancellationToken` parameter be banned in application code, or is it a fair convenience? Tell me I'm wrong.

**Follow The Curly Brace for more backend war stories — no theory, only scars.**
