---
title: "Middleware Order in ASP.NET Core: The Bug That Returned 401 to Everyone"
subtitle: A short demo article showing the format the autopilot produces — run it with `python run.py file samples/sample-article.md --dry-run`.
slug: middleware-order-demo
tags: [Aspnetcore, Dotnet, Csharp, Programming, Interview]
---

```asset
{"type":"cover","kicker":"Interview Ready · Demo","title":"Middleware Order: The Bug That Returned 401 to Everyone","subtitle":"Why one moved line took down login for 40 minutes","filename":"Program.cs","language":"csharp","code":"var app = builder.Build();\n\napp.UseExceptionHandler(\"/error\");\napp.UseRouting();\napp.UseAuthentication();\napp.UseAuthorization();\n\napp.MapControllers();\napp.Run();"}
```

At 9:12 on a Monday, every authenticated endpoint started returning 401. Tokens were valid. The identity provider was healthy. Nothing in the auth code had changed.

The only change in the release was a tidy-up of `Program.cs`. Someone had moved `app.UseAuthorization()` above `app.UseRouting()`.

It took 40 minutes to find, because nobody suspected that the *order* of five lines could matter more than the code inside them.

By the end of this demo you can explain why — and the same template scales to the full 12-question article.

```asset
{"type":"diagram","style":"flow","title":"How a request moves through middleware","nodes":[{"title":"Kestrel","subtitle":"Accepts HTTP request"},{"title":"Exception handler","subtitle":"Wraps everything after it"},{"title":"Routing","subtitle":"Picks the endpoint"},{"title":"AuthN / AuthZ","subtitle":"Who are you, may you?"},{"title":"Endpoint","subtitle":"Your controller runs"}],"note":"The response travels back through the same middleware in reverse order."}
```

## Q1. Why does the order of middleware matter?

**What they're actually testing:** Whether you understand the pipeline is a chain of delegates, not a list of features.

**The analogy:** Airport security. Checking the boarding pass before you know which gate the passenger is going to means you cannot apply the gate's rules.

**The code:**
```csharp
app.UseRouting();        // selects the endpoint + its metadata
app.UseAuthentication(); // sets HttpContext.User
app.UseAuthorization();  // reads [Authorize] from the endpoint
app.MapControllers();
```

**Say this in the interview:**
> Middleware runs in the order it is registered on the way in and in reverse on the way out. Authorization needs the endpoint metadata that routing selects, so UseRouting must come before UseAuthorization.

**The trap / follow-up:** "Where does UseCors go?" — after UseRouting and before UseAuthorization, so preflight requests are answered before auth rejects them.

**Memory hook:** *Route first, then ask who you are, then ask if you may.*

```asset
{"type":"table","title":"Use vs Run vs Map","headers":["Method","Calls next?","Typical use"],"rows":[["Use","Yes (optional)","Logging, auth, anything that wraps the request"],["Run","No — terminal","Last-resort handler, health ping"],["Map","Branches pipeline","Path-based sub-pipelines like /admin"]],"note":"Rule of thumb: Run ends the line, Use passes it on, Map forks it."}
```

---

## Q2. How do you write custom middleware?

**What they're actually testing:** That you know the convention-based shape and what happens before and after `next`.

**The analogy:** A relay runner who starts a stopwatch, hands the baton on, and stops the watch when the baton comes back.

**The code:**
```csharp
public class TimingMiddleware(RequestDelegate next)
{
    public async Task InvokeAsync(HttpContext ctx)
    {
        var sw = Stopwatch.StartNew();
        await next(ctx);
        ctx.Response.Headers["X-Elapsed"] = sw.ElapsedMilliseconds.ToString();
    }
}
```

**Say this in the interview:**
> Middleware is a class with a RequestDelegate and an InvokeAsync method. Code before await next runs on the way in, code after it runs on the way out, and not calling next short-circuits the pipeline.

**The trap / follow-up:** Setting a response header after the response has started throws — use `ctx.Response.OnStarting` for headers that depend on timing.

**Memory hook:** *Before next is the request, after next is the response.*

```asset
{"type":"gif","style":"code","title":"Custom middleware, line by line","filename":"TimingMiddleware.cs","language":"csharp","code":"public class TimingMiddleware(RequestDelegate next)\n{\n    public async Task InvokeAsync(HttpContext ctx)\n    {\n        var sw = Stopwatch.StartNew();\n        await next(ctx);\n        ctx.Response.Headers[\"X-Elapsed\"] =\n            sw.ElapsedMilliseconds.ToString();\n    }\n}","steps":[{"lines":[1,1],"caption":"The primary constructor receives the next delegate in the chain."},{"lines":[5,5],"caption":"Work before next runs on the way in."},{"lines":[6,6],"caption":"await next(ctx) runs everything downstream."},{"lines":[7,8],"caption":"Work after next runs on the way out."}]}
```

```asset
{"type":"gif","style":"flow","title":"Request in, response out","nodes":[{"title":"Request","subtitle":"GET /orders"},{"title":"Auth","subtitle":"Validates JWT"},{"title":"Endpoint","subtitle":"Returns 200"},{"title":"Response","subtitle":"Unwinds the pipeline"}],"steps":[{"focus":0,"caption":"Kestrel hands the request to the first middleware."},{"focus":1,"caption":"Auth validates the token and sets HttpContext.User."},{"focus":2,"caption":"The endpoint runs your controller action."},{"focus":3,"caption":"The response travels back through every middleware in reverse."}]}
```

```asset
{"type":"diagram","style":"compare","title":"Middleware vs Filters","left":{"title":"Middleware","points":["Runs for every request","No access to action arguments","Registered in Program.cs"]},"right":{"title":"Action filters","points":["Runs only for MVC endpoints","Sees model-bound arguments and results","Scoped per controller or action"]},"verdict":"Middleware for transport concerns, filters for MVC concerns."}
```

Screenshot this before your interview.

```asset
{"type":"revision","title":"60-Second Revision","points":[{"term":"Order is the contract","line":"Top-down on the way in, bottom-up on the way out."},{"term":"Routing before auth","line":"Authorization needs the endpoint metadata routing selects."},{"term":"Run is terminal","line":"Nothing registered after app.Run executes."},{"term":"Exception handler first","line":"It can only catch what comes after it."},{"term":"Before / after next","line":"Request work before await next, response work after."},{"term":"Short-circuit","line":"Not calling next stops the pipeline."}]}
```

## 5-Question Self-Check

1. Why must UseRouting come before UseAuthorization?
2. What is the difference between Use and Run?
3. Where does UseCors belong?
4. What happens if middleware never calls next?
5. Why can setting a header after next throw?

**Answers:** 1) Authorization reads endpoint metadata. 2) Run is terminal. 3) After routing, before authorization. 4) The pipeline short-circuits. 5) The response may already have started.

## Coming next

Dependency Injection lifetimes — and the captive dependency bug that quietly shares one DbContext across every request.

**Which question came up in your interview that isn't here? Drop it in the responses — I'll add it to the next revision with credit.**
