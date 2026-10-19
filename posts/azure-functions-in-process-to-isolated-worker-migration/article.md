# Your Azure Functions Lose Support on November 10, 2026. Migrate Without Breaking Them.

## In-process apps keep running after the deadline but stop getting fixes. Here is the move to the isolated worker on .NET 10, and the breaking changes most migrations miss.

![Your Azure Functions Lose Support on November 10, 2026. Migrate Without Breaking Them.](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/azure-functions-in-process-to-isolated-worker-migration/images/01-cover.png)

It's November 11. Nothing is on fire.

Your order-processing function app ran overnight like it always does. The dashboards are green. Then someone opens a portal notification and reads it twice: *in-process model, end of support*.

The app still works, and that is the trap. Nothing changes on the morning of the deadline. What changes is that nobody is patching the host your code runs inside anymore.

So what actually happens on November 10, and how do you get off the in-process model without breaking a running system?

## What "end of support" means for an app that's already running

According to the [Azure retirement notice](https://aka.ms/azure-functions-retirements/in-process-model), in-process apps keep running after November 10, 2026, but they stop receiving security and feature updates. Nothing is switched off. You're on your own from then on.

There's a second deadline on the same day. The in-process model on Functions 4.x supports only .NET 8, and .NET 8 itself leaves support on November 10, 2026. So after that date, an in-process app runs on an unpatched hosting model *and* an unpatched runtime. .NET 9 also leaves support that day, so isolated on .NET 8 or 9 doesn't get you past the deadline. Target .NET 10 (LTS, supported to November 2028).

There's no "upgrade in place" option either. In-process will never support .NET 10. The [supported versions table](https://learn.microsoft.com/en-us/azure/azure-functions/dotnet-isolated-process-guide) lists .NET 10 only under the isolated worker model.

## The lodger and the flat next door

In the in-process model, your function DLL is a lodger in the Functions host's house. It eats what the host cooks: the host's version of `Microsoft.Extensions.*`, its Newtonsoft.Json, its logging pipeline. That's why you couldn't upgrade some packages. The host had already loaded them.

In the isolated model, your app moves into its own flat next door. It's a plain .NET console app with its own `Main`, its own DI container and its own package versions. The host still owns the triggers and calls your worker over gRPC, a bit like an intercom between the flats.

![In-process vs isolated worker](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/azure-functions-in-process-to-isolated-worker-migration/images/02-diagram-compare-1.png)

Nearly every breaking change below comes from that one fact. When you live in your own flat, you set up your own utilities.

## The project file is now a console app

Start with the `.csproj`. The current [migration guide](https://learn.microsoft.com/en-us/azure/azure-functions/migrate-dotnet-to-isolated-model) switches the project SDK to `Azure.Functions.Sdk`, targets `net10.0`, and replaces `Microsoft.NET.Sdk.Functions` with the worker packages:

```xml
<Project Sdk="Azure.Functions.Sdk/1.0.0">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <FrameworkReference Include="Microsoft.AspNetCore.App" />
    <PackageReference Include="Microsoft.Azure.Functions.Worker" Version="2.52.0" />
    <PackageReference Include="Microsoft.Azure.Functions.Worker.Extensions.Http.AspNetCore" Version="2.1.0" />
    <PackageReference Include="Microsoft.Azure.Functions.Worker.Extensions.Storage.Queues" Version="5.5.0" />
    <PackageReference Include="Microsoft.ApplicationInsights.WorkerService" Version="2.22.0" />
    <PackageReference Include="Microsoft.Azure.Functions.Worker.ApplicationInsights" Version="1.2.0" />
  </ItemGroup>
  <ItemGroup>
    <Using Include="System.Threading.ExecutionContext" Alias="ExecutionContext" />
  </ItemGroup>
</Project>
```

The worker and Application Insights versions, and the `ExecutionContext` using alias, are the ones the guide shows. Treat every version number as a floor and take the latest stable from NuGet; the HTTP AspNetCore extension, for example, is already at 2.1.1. The Queues line stands in for whichever trigger extensions you use.

The rule the guide puts in bold: **no `Microsoft.Azure.WebJobs.*` package and no `Microsoft.Azure.Functions.Extensions` may remain.** Each WebJobs extension has an isolated twin (`...WebJobs.Extensions.ServiceBus` becomes `...Functions.Worker.Extensions.ServiceBus`, and so on). Watch for major-version jumps. The guide warns that the Service Bus extension changed its `host.json` structure between 4.x and 5.x.

If you deploy to Linux on the old Consumption plan, stop and plan for this: .NET 10 can't run on Linux Consumption (.NET 9 was the last version there). Move to Flex Consumption, which means a new function app and no slot swap, or to Windows Consumption, Premium or Dedicated. If you pick Flex, read the no-slots caveat in the cutover section below before you plan the switch.

## Startup.cs becomes Program.cs, and you finally get middleware

Your `FunctionsStartup` class goes away. Its `Configure` body moves into `Program.cs` mostly unchanged, because `builder.Services` is the same `IServiceCollection` you already know:

```csharp
using System.Linq;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = FunctionsApplication.CreateBuilder(args);

builder.ConfigureFunctionsWebApplication();
builder.UseMiddleware<ErrorLoggingMiddleware>();

builder.Services
    .AddApplicationInsightsTelemetryWorkerService()
    .ConfigureFunctionsApplicationInsights();

// Let Information-level logs through (explained below).
builder.Services.Configure<LoggerFilterOptions>(options =>
{
    var aiDefault = options.Rules.FirstOrDefault(r => r.ProviderName ==
        "Microsoft.Extensions.Logging.ApplicationInsights.ApplicationInsightsLoggerProvider");
    if (aiDefault is not null) options.Rules.Remove(aiDefault);
});

// Everything from FunctionsStartup.Configure moves here.

builder.Build().Run();
```

The in-process model had no real middleware story. The isolated worker gives you a pipeline around every invocation, whatever the trigger:

```csharp
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Middleware;
using Microsoft.Extensions.Logging;

public sealed class ErrorLoggingMiddleware(ILogger<ErrorLoggingMiddleware> logger)
    : IFunctionsWorkerMiddleware
{
    public async Task Invoke(FunctionContext context, FunctionExecutionDelegate next)
    {
        try
        {
            await next(context);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Function {Name} failed", context.FunctionDefinition.Name);
            throw;
        }
    }
}
```

Look closely at the DI. With version 2.x of `Microsoft.Azure.Functions.Worker`, **service provider scope validation is on by default in the Development environment**, the same as ASP.NET Core. If your in-process app quietly injected a scoped service into a singleton, the migrated app will now fail on startup when you run it locally. That's a good thing. (I've written about why that bug matters in [The Captive Dependency That Leaked Our DbContext](https://medium.com/@thecurlybrace/di-lifetimes-in-asp-net-core-the-captive-dependency-that-leaked-our-dbcontext-a9c56ef3a42e).)

## Function signatures: rename, inject, return

Most of it is mechanical. Output bindings change the most:

![In-process to isolated: what changes in your code](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/azure-functions-in-process-to-isolated-worker-migration/images/03-table-1.png)

Here's a typical HTTP function that also writes to a queue, after migration:

```csharp
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

public class CreateOrder(ILogger<CreateOrder> logger)
{
    [Function("CreateOrder")]
    public async Task<CreateOrderOutput> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post")] HttpRequest req)
    {
        using var reader = new StreamReader(req.Body);
        string body = await reader.ReadToEndAsync();

        logger.LogInformation("Order received ({Length} bytes)", body.Length);

        return new CreateOrderOutput { Result = new AcceptedResult(), Message = body };
    }
}

public class CreateOrderOutput
{
    [HttpResult]
    public IActionResult Result { get; set; } = default!;

    [QueueOutput("orders")]
    public string? Message { get; set; }
}
```

There are two things to notice. First, `[HttpResult]` tells the worker which property is the HTTP response. Without it, your response and your queue message compete for the same return value. Second, the body read is `ReadToEndAsync`, and that's not a style choice.

## HttpRequest, not HttpRequestData, with one sharp edge

The isolated worker offers two HTTP models. The built-in one uses `HttpRequestData`/`HttpResponseData`. With `HttpRequestData`, a chunked request with no `Content-Length` header gives you a null `Body` stream. The ASP.NET Core integration (`ConfigureFunctionsWebApplication`) is what the migration guide uses when it's supported, and it's the model that supports streaming. It gives you the `HttpRequest` and `IActionResult` you already use, which makes migrated code look almost the same as before.

My position: if you're on .NET 10, use ASP.NET Core integration. `HttpRequestData` only makes sense for .NET Framework 4.8, where the integration isn't available.

The sharp edge is that ASP.NET Core disallows synchronous I/O by default. A leftover `reader.ReadToEnd()` that worked fine in-process now throws `InvalidOperationException: Synchronous operations are disallowed`. Make it async. Don't reach for the `AllowSynchronousIO` switch unless a dependency gives you no choice. (It's disallowed for the same thread-pool reason I covered in [One Innocent Line (.Result) Froze My Entire API](https://medium.com/@thecurlybrace/one-innocent-line-result-froze-my-entire-api-i-was-blocking-async-without-knowing-it-8be867b6f4fd).)

## The two silent breaks: your logs and your JSON

These two don't throw errors. They change behaviour quietly, and you find out from a customer.

**Logging.** In the isolated model, `host.json` controls only the host's logs. Your code's log levels are configured in the worker. On top of that, the Application Insights Worker Service SDK captures only Warning and above by default. Migrate, deploy, and your `LogInformation` breadcrumbs disappear from Application Insights. The filter-rule removal in the `Program.cs` above brings them back. Then set the levels you actually want in code or `appsettings.json`. Microsoft's isolated guide now leans towards OpenTelemetry with the Azure Monitor exporter. That's worth adopting, but in a separate change from the migration.

**JSON.** The in-process model used Newtonsoft.Json. The isolated worker defaults to System.Text.Json. As the migration guide warns, System.Text.Json **ignores `[JsonProperty]` and `[JsonIgnore]` and binds the affected property to its default value without reporting an error**. A queue message with `[JsonProperty("order_id")]` arrives with `OrderId` set to `0`. Search your solution for `Newtonsoft.Json` attributes before you deploy anything.

## The cutover: two changes, one swap

In Azure, the migration is two changes: set `FUNCTIONS_WORKER_RUNTIME` to `dotnet-isolated`, and deploy the isolated build. Each one restarts the app. Between them, the runtime and the payload don't match, and the app logs `AZFD0013` errors.

That's why you make both changes in a staging slot, not in production:

![Cutting over without an outage](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/azure-functions-in-process-to-isolated-worker-migration/images/04-gif-flow-1.gif)

Two caveats. Update your IaC and pipelines too, or the next Bicep deployment will set the runtime back to `dotnet`. And check that your plan supports slots before counting on them: Flex Consumption, for one, didn't at the time of writing. Flex's rolling updates don't help here: the runtime switch and the deploy are still two separate restarts. Without slots, schedule a short maintenance window and make the two changes back to back.

## When not to rush it

Migrating twelve function apps in three weeks is how you cause the incident you were trying to avoid. Prioritise apps exposed to the internet, then everything else. An internal timer job can wait a sprint past the deadline. The risk there is real, but it's lower.

Treat Durable Functions apps as a separate project. The isolated package is a different SDK with its own client and context types (`TaskOrchestrationContext` instead of `IDurableOrchestrationContext`). Every orchestrator API call changes. Read its migration guide before you start.

![Pre-flight Checklist](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/azure-functions-in-process-to-isolated-worker-migration/images/05-revision.png)

> Moving to the isolated worker is mostly mechanical. The danger is in what fails silently: logs you no longer see, and JSON properties that quietly become zero.

Do this today: run `grep -rnE "JsonProperty\(|JsonIgnore|ReadToEnd\(\)|FunctionsStartup|IAsyncCollector|IBinder|Microsoft\.Azure\.WebJobs" --include=*.cs --include=*.csproj src/` on your biggest function app and count the hits. That count is roughly how much work you have before November 10.

Which of your function apps can't make November 10, and what's blocking it: Durable, Linux Consumption, or a WebJobs-only extension?

**Follow The Curly Brace for more backend war stories — no theory, only scars.**
