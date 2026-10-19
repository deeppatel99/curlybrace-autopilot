# Review — Your Azure Functions Lose Support on November 10, 2026. Migrate Without Breaking Them.

- Mode: `local`
- Tags: Azure, Azure Functions, Dotnet, Csharp, Serverless
- Visuals: 5
- Claude usage: 572,520 in / 35,246 out tokens (Claude subscription — no extra charge)

## Your checklist

- [ ] Open https://deeppatel99.github.io/curlybrace-autopilot/posts/azure-functions-in-process-to-isolated-worker-migration/paste.html (GitHub Pages), Ctrl+A, Ctrl+C, paste into https://medium.com/new-story
- [ ] Tags to add: Azure, Azure Functions, Dotnet, Csharp, Serverless

## Format check

- All format checks passed.

## AI reviewer report

VERDICT: NEEDS FIXES**

## Issues
- [severity: medium] [location: subtitle / whole article] The subtitle promises "the five breaking changes most migrations miss", but the article never counts or names five. A reader can find about six candidates: scope validation, sync I/O, log filtering, JSON attributes, the runtime/payload mismatch and the Linux Consumption limit. None is labelled as one of the five. -> Pick the five and number them in the headings (for example "Break 1: scope validation fails your startup"), or change the subtitle to "...and the breaking changes most migrations miss".
- [severity: medium] [location: section "The project file is now a console app", last paragraph; asset "Pre-flight Checklist" → "Hosting plan"] "You need Flex Consumption" is too strong. Docs say .NET 9 is the last .NET version on Linux Consumption. Windows Consumption, Premium and Dedicated plans still run .NET 10. The bigger gap: moving from Linux Consumption to Flex means a new app, and Flex has no slots. Your staging-slot cutover cannot work for exactly these readers. -> Write: ".NET 10 can't run on Linux Consumption (.NET 9 was the last version there). Move to Flex Consumption, which means a new function app and no slot swap, or to Windows Consumption, Premium or Dedicated." Then link this to the no-slots paragraph in the cutover section.
- [severity: medium] [location: asset "In-process vs isolated worker", right title; section "What end of support means"] The diagram lists isolated .NET 8 and 9 as targets. Both reach end of support on November 10, 2026, the same day as in-process. A reader who moves to isolated on .NET 8 to "play it safe" lands on an unsupported runtime the same day. -> Add to the second paragraph: ".NET 9 also leaves support that day, so isolated on .NET 8 or 9 doesn't get you past the deadline. Target .NET 10 (LTS, supported to November 2028)." Change the diagram title to "Isolated worker (.NET 10 or Fx 4.8 after Nov 2026)".
- [severity: medium] [location: section "HttpRequest, not HttpRequestData", first paragraph] "Microsoft keeps it mainly for backward compatibility" is not backed by any doc I could find. The chunked-body claim is real and documented, so keep that. -> Remove the backward-compatibility clause, or replace it with what the docs say: ASP.NET Core integration is what the migration guide uses "when supported" and is what supports streaming.
- [severity: low] [location: section "What end of support means", first link] The azure.microsoft.com/updates URL loads an empty Azure Updates filter page ("0 Updates found"), so readers see nothing. -> Use the link the migration guide itself uses: https://aka.ms/azure-functions-retirements/in-process-model.
- [severity: low] [location: section "When not to rush it", Durable paragraph] "Orchestrator code has stricter threading rules (no ConfigureAwait(false) in orchestrators)" implies this rule is new in isolated. Orchestrators had replay and determinism rules in-process too. The real change is the SDK and types (`TaskOrchestrationContext`, `DurableTaskClient`, `CurrentDateTimeUtc`). -> Write: "...a different SDK with its own client and context types (`TaskOrchestrationContext` instead of `IDurableOrchestrationContext`). Every orchestrator API call changes. Read its migration guide before you start."
- [severity: low] [location: section "The project file is now a console app", csproj] The guide's .NET 10 project file also adds `<Using Include="System.Threading.ExecutionContext" Alias="ExecutionContext"/>`. Your file leaves it out without saying why. Readers who copy your file instead of the guide's get a different result. -> Add the ItemGroup, or say in one line why you dropped it. Also note that the HTTP AspNetCore extension is already at 2.1.1, which fits your "treat as a floor" line.
- [severity: low] [location: section "Function signatures"] The prose paragraph before the table repeats the table almost row for row (FunctionName→Function, ILogger, ExecutionContext, Input/Output suffixes). Also, the first table row says "Same signature; a find-and-replace works", but the logger row right below it shows signatures do change. -> Cut the paragraph down to one sentence ("Most of it is mechanical. Output bindings change the most:"). Change the table note to "Attribute has the same constructor; rename it".
- [severity: low] [location: cover asset vs section "Startup.cs becomes Program.cs"] The cover registers `ErrorLogging`; the article's class is `ErrorLoggingMiddleware`. -> Use `ErrorLoggingMiddleware` in the cover code.
- [severity: low] [location: section "Function signatures", HTTP example] `using Microsoft.Azure.Functions.Worker.Http;` is not used (`[HttpResult]` is in `Microsoft.Azure.Functions.Worker`). `System.IO` and `System.Threading.Tasks` are redundant with ImplicitUsings on. "Real-shaped" is awkward English. -> Remove the unused usings. Change the lead-in to "Here's a typical HTTP function that also writes to a queue, after migration:".
- [severity: low] [location: "Do this today" line] The grep is noisy and has gaps. `ReadToEnd()` matches harmless file-stream reads. It misses `[JsonIgnore]`, `IAsyncCollector`, `IBinder` and WebJobs package references, and it scans bin/obj. -> `grep -rnE "JsonProperty\(|JsonIgnore|ReadToEnd\(\)|FunctionsStartup|IAsyncCollector|IBinder|Microsoft\.Azure\.WebJobs" --include=*.cs --include=*.csproj src/`
- [severity: low] [location: title, cover] "November 10" has no year, and the global audience reads this a few weeks before the deadline. -> "Your Azure Functions Lose Support on November 10, 2026. Migrate Without Breaking Them." Make the same change in the cover asset title.
- [severity: low] [location: closing question] "Tell me I'm wrong" asks about something the article already settled: you say yourself that HttpRequestData is only for Fx 4.8. That gives readers little to answer. -> Ask something open: "Which of your function apps can't make November 10, and what's blocking it: Durable, Linux Consumption, or a WebJobs-only extension?"
- [severity: low] [location: section "The cutover"] Flex Consumption has no slots, but it does have rolling updates (site update strategy). Readers will ask whether that replaces a slot swap. It doesn't, because the runtime setting and the deployment are still two restarts. -> Add one sentence: "Flex's rolling updates don't help here: the runtime switch and the deploy are still two separate restarts."

No overlap problem: the links to the captive-dependency and `.Result` articles build on them without repeating them. The house-style elements are all present: cold open, one analogy, a "when not to" section, the blockquote, one action, one question, and the CTA verbatim and last.

## Fact-check notes for the author
- In-process support ends November 10, 2026 -> VERIFIED https://learn.microsoft.com/en-us/azure/azure-functions/migrate-dotnet-to-isolated-model
- Apps keep running after the date but get no security or feature updates -> UNVERIFIED on your linked page, which shows an empty updates filter. Check https://aka.ms/azure-functions-retirements/in-process-model
- .NET 8 (and .NET 9) end of support November 10, 2026; .NET 10 LTS to November 2028 -> VERIFIED https://devblogs.microsoft.com/dotnet/dotnet-8-9-end-of-support/
- csproj: `Azure.Functions.Sdk/1.0.0`, `net10.0`, Worker 2.52.0, Http.AspNetCore 2.1.0, AI WorkerService 2.22.0, Worker.ApplicationInsights 1.2.0 -> VERIFIED https://learn.microsoft.com/en-us/azure/azure-functions/migrate-dotnet-to-isolated-model (the guide also adds an `ExecutionContext` using alias)
- Queues extension 5.5.0 -> UNVERIFIED. Check https://www.nuget.org/packages/Microsoft.Azure.Functions.Worker.Extensions.Storage.Queues
- Bold rule: no `Microsoft.Azure.WebJobs.*` or `Microsoft.Azure.Functions.Extensions` -> VERIFIED (migration guide)
- Service Bus host.json structure changed between 4.x and 5.x -> VERIFIED (migration guide)
- .NET 10 not supported on Linux Consumption -> VERIFIED (.NET 9 is the last version), https://learn.microsoft.com/azure/azure-functions/consumption-plan. "Need Flex" is too strong; Windows Consumption, Premium and Dedicated also work.
- Scope validation on by default in Development with Worker 2.x, matching ASP.NET Core -> VERIFIED https://learn.microsoft.com/en-us/azure/azure-functions/dotnet-isolated-process-guide
- Sync I/O throws `InvalidOperationException: Synchronous operations are disallowed`; `AllowSynchronousIO` is a compatibility option -> VERIFIED (migration guide, "Migrate to asynchronous HTTP stream I/O")
- HttpRequestData Body is a null stream for chunked requests with no Content-Length -> VERIFIED https://learn.microsoft.com/en-us/azure/azure-functions/dotnet-isolated-process-guide and https://github.com/Azure/azure-functions-dotnet-worker/issues/1295
- HttpRequestData "kept mainly for backward compatibility" -> UNVERIFIED. No official wording found. Check the HTTP trigger section of the isolated guide.
- ASP.NET Core integration not available on .NET Framework 4.8 -> VERIFIED: the migration guide's Fx 4.8 tab uses `ConfigureFunctionsWorkerDefaults` and `HttpRequestData`.
- host.json controls only host logs in isolated -> VERIFIED (migration guide)
- AI Worker Service SDK filters to Warning and above by default; remove the `ApplicationInsightsLoggerProvider` rule -> VERIFIED https://learn.microsoft.com/en-us/azure/azure-functions/dotnet-isolated-process-guide (managing log levels)
- Isolated guide now leans towards OpenTelemetry with the Azure Monitor exporter -> VERIFIED (isolated guide, start-up section)
- System.Text.Json ignores `[JsonProperty]`/`[JsonIgnore]` and binds default values without an error -> VERIFIED (migration guide, "JSON serialization")
- Two changes, each restarts the app, `AZFD0013` in between; don't mark `FUNCTIONS_WORKER_RUNTIME` as a slot setting; update the stack; keep IaC in sync -> VERIFIED (migration guide, "Update your function app in Azure")
- Flex Consumption doesn't support deployment slots -> VERIFIED https://learn.microsoft.com/en-in/azure/azure-functions/functions-deployment-slots
- No `ConfigureAwait(false)` in orchestrators -> UNVERIFIED as an isolated-specific rule. Check https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-code-constraints
- IAsyncCollector<T> → T[]; IBinder → injected client; input/output attributes gain Input/Output; triggers keep their names -> VERIFIED (migration guide)
