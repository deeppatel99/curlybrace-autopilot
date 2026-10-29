# Review — Your User Closed the Tab. Your API Kept Working for 40 Seconds Anyway.

- Mode: `local`
- Tags: Aspnetcore, Dotnet, Entity Framework Core, Csharp, Performance
- Visuals: 5
- Claude usage: 123,965 in / 27,631 out tokens (Claude subscription — no extra charge)

## Your checklist

- [ ] Open https://deeppatel99.github.io/curlybrace-autopilot/posts/your-user-closed-the-tab-your-api-kept-working-for-40-seconds-anyway/paste.html (GitHub Pages), Ctrl+A, Ctrl+C, paste into https://medium.com/new-story
- [ ] Tags to add: Aspnetcore, Dotnet, Entity Framework Core, Csharp, Performance

## Format check

- All format checks passed.

## AI reviewer report

VERDICT: NEEDS FIXES

## Issues
- [severity: high] [location: section "The fix is almost insultingly simple", middleware sentence] "Register it early, before your own error-handling middleware" has the order backwards. Middleware registered first is the outermost layer. An inner `UseExceptionHandler` catches the exception first, logs it and handles it, so your outer filter never sees it. That puts the false alarms back on the dashboard, which is the exact problem the snippet is meant to stop. The built-in handler already logs client aborts at Debug level for `OperationCanceledException`, but it does not do this for the `SqlException` variant you describe. -> Change to: "Register it after `UseExceptionHandler`, so it sits inside the error handler and sees the exception first. The built-in handler already logs aborted requests at Debug level for `OperationCanceledException`. This filter also covers the `SqlException` case."
- [severity: medium] [location: asset "Where the token goes to die" and the fixed code] `.Select(g => new { g.Key, Sum = ... })` produces a list of an anonymous type, and the code then passes it to `SalesReport.From(totals, rates!)`. A named method parameter can't accept an anonymous type unless `From` is generic or takes `object`/`dynamic`. As shown, this does not compile. -> Add `public sealed record CurrencyTotal(string Currency, decimal Sum);` and project with `.Select(g => new CurrencyTotal(g.Key, g.Sum(o => o.Amount)))`. Make the same change in the gif code.
- [severity: medium] [location: cover asset] The cover code has no `return` and no closing for the method body's result, so it doesn't compile. It also drops the `to` filter, so it doesn't match the code in the article. -> Use the first lines of the gif code, or end the snippet with `// ...` and a `return` so it reads as a fragment, not a broken method.
- [severity: medium] [location: section "A kitchen that cooks for empty tables"] "The cook stays at the burner for the full 40 minutes" contradicts the 40 seconds used everywhere else. A reader working the 2.5/sec arithmetic two lines later will stumble. -> "for the full 40 seconds", or present the analogy explicitly in minutes ("think of each second as a minute") and use that scale consistently.
- [severity: medium] [location: subtitle vs section "The one place you should not pass it"] The subtitle and heading promise "the one place". The table lists three no-pass cases: SaveChanges after a charge, writes tied to an external call, and background work. -> Either rename to "Where you should not pass it" (and "the places you shouldn't pass it" in the subtitle), or make the single rule explicit: "after a side effect you can't undo". Then present the table rows as examples of that one rule.
- [severity: medium] [location: table row "Background or fire-and-forget work"] "It's cancelled the moment the response ends" is not what the API guarantees. `RequestAborted` fires when the connection is aborted, not when a request completes normally. The real hazard is that the `HttpContext` and its token are recycled after the response, so you can't rely on how they behave. -> "Its lifetime ends with the request, and the HttpContext is recycled. Use a token from `IHostApplicationLifetime` or your background service instead."
- [severity: low] [location: asset "60-Second Revision", term "RequestAborted"] "bound to any CancellationToken parameter" is too broad. Binding only happens for action and handler parameters, not service methods. That distinction is the root cause of this bug. -> "bound to CancellationToken parameters on controller actions and minimal API handlers".
- [severity: low] [location: section "The fix…", verification] The verification step names `number-of-active-connections` but never says how to watch it. -> Add the command: `dotnet-counters monitor --counters Microsoft.Data.SqlClient.EventSource -p <pid>`. Note that SqlClient event counters need Microsoft.Data.SqlClient 3.0+ on .NET Core 3.1+.
- [severity: low] [location: section "The first three guesses", guess two] "The pool errors stop for eleven minutes" is a precise figure in a reconstruction. It's acceptable, but it reads as a measured fact. -> "for a few minutes".
- [severity: low] [location: section "Make the compiler catch the lie"] The article doesn't mention CA2016's documented limit: it only triggers when the token is the method's last parameter. Readers with `(CancellationToken ct, int page)` signatures will get silence and think they're clean. -> Add one sentence: "It only checks methods whose token is the last parameter."

## Fact-check notes for the author
- CA2016 exists, catches calls with optional-token parameters and token overloads, and is "Enabled by default … as suggestion" -> VERIFIED https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2016
- Passing `CancellationToken.None` (or `default`) explicitly suppresses CA2016 -> VERIFIED (same page)
- `number-of-reclaimed-connections` counts connections reclaimed by the GC when Close/Dispose wasn't called; `number-of-active-connections` exists -> VERIFIED https://learn.microsoft.com/en-us/sql/connect/ado-net/event-counters
- The ASP.NET Core exception handler logs client aborts at Debug level (event RequestAborted) -> VERIFIED in source https://source.dot.net/Microsoft.AspNetCore.Diagnostics/DiagnosticsLoggerExtensions.cs.html. The middleware-order claim contradicts this, as described in the high-severity issue above.
- `Max Pool Size` default 100; `Connect Timeout` default 15 s, which also bounds the wait for a pooled connection -> VERIFIED (standard SqlClient defaults) https://learn.microsoft.com/en-us/dotnet/api/microsoft.data.sqlclient.sqlconnection.connectionstring
- Command timeout default 30 s -> VERIFIED https://learn.microsoft.com/en-us/dotnet/api/microsoft.data.sqlclient.sqlcommand.commandtimeout
- `HttpClient.Timeout` default 100 s -> VERIFIED https://learn.microsoft.com/en-us/dotnet/api/system.net.http.httpclient.timeout
- `CancellationToken` is bound to `HttpContext.RequestAborted` in minimal APIs -> VERIFIED https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/parameter-binding
- Primary constructors are C# 12 (.NET 8), and the Web SDK's implicit usings include `System.Net.Http.Json` -> VERIFIED (standard SDK behaviour) https://learn.microsoft.com/en-us/dotnet/core/project-sdk/overview#implicit-using-directives
- Cancellation can surface as `OperationCanceledException` or `SqlException` depending on timing -> UNVERIFIED as a documented guarantee. It matches observed SqlClient behaviour ("Operation cancelled by user"). Check the SqlClient GitHub issues on cancellation exceptions and phrase it as "in practice".
- Proxy behaviour: an upstream connection held open hides client disconnects -> UNVERIFIED in general. It depends on the proxy, so keep it as advice to test, not as a stated fact.
- Overlap: none found. The article links to the DI-lifetime and `.Result` articles without repeating them. The HttpClient article covers socket exhaustion, not token forwarding.

Sources:
- [CA2016 docs](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2016)
- [SqlClient event counters](https://learn.microsoft.com/en-us/sql/connect/ado-net/event-counters)
- [DiagnosticsLoggerExtensions.cs](https://source.dot.net/Microsoft.AspNetCore.Diagnostics/DiagnosticsLoggerExtensions.cs.html)
