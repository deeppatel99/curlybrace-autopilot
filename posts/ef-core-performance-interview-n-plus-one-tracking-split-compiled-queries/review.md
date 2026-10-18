# Review — EF Core Performance Interview Questions: N+1, No-Tracking, Split and Compiled Queries

- Mode: `local`
- Tags: Entity Framework Core, Dotnet, Csharp, Performance, Sql
- Visuals: 11
- Claude usage: 29,921 in / 43,085 out tokens (Claude subscription — no extra charge)

## Your checklist

- [ ] Open /home/runner/work/curlybrace-autopilot/curlybrace-autopilot/out/2026-10-18-ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/paste.html in Chrome, Ctrl+A, Ctrl+C, paste into a new Medium story.
- [ ] Tags to add: Entity Framework Core, Dotnet, Csharp, Performance, Sql

- [ ] Open https://deeppatel99.github.io/curlybrace-autopilot/posts/ef-core-performance-interview-n-plus-one-tracking-split-compiled-queries/paste.html (GitHub Pages), Ctrl+A, Ctrl+C, paste into https://medium.com/new-story

## Format check

- All format checks passed.

## AI reviewer report

VERDICT: NEEDS FIXES

## Issues
- [severity: medium] [location: Q11 code] The "injection hole" example concatenates `customerId`, which is an `int` in the `Order` model. An integer cannot carry an injection payload, so the code does not prove the claim. An interviewer reading closely would notice. -> Use a string input to show injection, for example `.FromSqlRaw("SELECT * FROM Orders WHERE Status = '" + status + "'")`, with the comment `// status = "x' OR 1=1 --" returns every row`. Keep the `int` version only to illustrate plan-cache churn, or drop it.
- [severity: medium] [location: front matter tags] The lead tag is `Sql`, but the article is about EF Core and SQL is secondary. -> Change to `tags: [Entity Framework Core, Dotnet, Csharp, Performance, Sql]`. If the publication requires a fixed lead tag such as `Dotnet`, put that first and keep `Entity Framework Core` second.
- [severity: low] [location: hook vs asset "How 80 ms became 9 s"] The numbers do not agree. The hook says "Every query took a few milliseconds", but the GIF uses "about 10 ms each" to reach 9 s. 900 × "a few ms" gives about 3 s, not 9 s. -> In the hook, write "Every query took about 10 ms, round trip included." Also change the GIF node `"GET /orders"` to `"GET /customers/{id}/orders"` so it matches the story.
- [severity: low] [location: asset "From N+1 to one query", steps for lines 5–6] `var totals = orders.Select(...)` has no `.ToList()`. This LINQ-to-Objects sequence is deferred, so nothing runs at that line, and the caption "triggers a lazy load" is inaccurate as written. -> Append `.ToList()` to line 6 (`.Select(o => o.Lines.Sum(l => l.Price * l.Quantity)).ToList();`), as Q1 already does.
- [severity: low] [location: cover asset code] The cover combines `.AsNoTracking()` with a DTO `Select`. Q5 states that DTO projections are not tracked, so the cover shows a redundant call the article itself argues against. -> Remove `.AsNoTracking()` from the cover snippet.
- [severity: low] [location: asset "Loading related data in EF Core", Include row] "1, or 1 per collection with split" reads as a single round trip in split mode. -> Change to "1, or 1 + one per collection with AsSplitQuery".
- [severity: low] [location: asset "60-Second Revision", Split queries line] "no consistency" overstates the issue. The statements can be made consistent with a transaction. -> "One SQL per collection. Fewer rows, more round trips, no cross-statement consistency without a transaction."
- [severity: low] [location: asset "How one order becomes 1,000 rows"] The diagram repeats the Q8 prose (50 × 20 = 1,000, parent columns repeated) and adds nothing new. -> Either delete it, or make it show something the prose lacks. One option is a wide parent column: "Notes NVARCHAR(MAX) 4 KB × 1,000 rows = ~4 MB for one order", contrasted with split mode at "1 + 50 + 20 = 71 rows".
- [severity: low] [location: asset "Single query vs split query"] Most rows restate the Q9 prose. -> Replace one redundant row with information the prose lacks, for example ["SQL Server without MARS", "Streams results", "Buffers earlier result sets in memory"].
- [severity: low] [location: subtitle] "separate developers who use EF Core from engineers who can make it fast" is a well-worn framing. -> "Twelve questions on N+1, tracking, split and compiled queries, with the answers interviewers expect."
- [severity: low] [location: assets, general] The layer subtitles in "What runs on every EF Core query execution" run to about 80–90 characters each. -> Check them against the asset size limit for diagram subtitles and shorten if needed (e.g. "New tree on every call. Compiled queries skip it.").

## Fact-check notes for the author
- Q4 trap: confirm that accessing a lazy navigation on a disposed context throws by default because `CoreEventId.LazyLoadOnDisposedContextWarning` is configured as an error. Check "Breaking changes in EF Core 3.x" and the `CoreEventId` API reference on learn.microsoft.com.
- Q11: SQL Server simple parameterization can auto-parameterize trivial statements like `SELECT * FROM Orders WHERE CustomerId = 5`, which weakens the "fills the plan cache" claim for that exact example. Check the "Simple parameterization" section of SQL Server's "Query Processing Architecture Guide".
- Q12: confirm the EF Core 10 change that lets `ExecuteUpdateAsync` setters be a regular (non-expression) lambda, and its exact signature. Check "What's New in EF Core 10".
- Q12 trap: confirm the wording on transactions. `ExecuteUpdate` and `ExecuteDelete` do join an explicit `BeginTransaction` transaction if one exists. They are only "outside" the implicit `SaveChanges` transaction. Check "ExecuteUpdate and ExecuteDelete" under EF Core "Saving data".
- Q9: confirm the paging and unique-ordering requirement, and the snapshot/serializable recommendation. Check "Single vs. Split Queries" in the EF Core docs.
- Q8: confirm that `MultipleCollectionIncludeWarning` fires only when no `QuerySplittingBehavior` is configured. Check the `RelationalEventId` API reference.
- Q10: confirm the description of what compiled queries skip (expression tree construction, parameter extraction, cache lookup) and the `dotnet ef dbcontext optimize` version (EF Core 6). Check "Advanced Performance Topics → Compiled queries" and "Compiled models".
- Q3: confirm that `Include` is silently ignored when the final projection does not contain the entity type. Check "Eager Loading of Related Data" in the EF Core docs.
