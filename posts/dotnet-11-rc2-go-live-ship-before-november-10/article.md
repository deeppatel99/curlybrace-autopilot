# .NET 11 RC2 Has a Go-Live License. Should You Ship It Before November 10?

## Yes, for well-tested stateless services, but only after four pre-merge checks. And the build you actually ship isn't RC2.

![.NET 11 RC2 Has a Go-Live License. Should You Ship It Before November 10?](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/dotnet-11-rc2-go-live-ship-before-november-10/images/01-cover.png)

It's Monday, October 26. Your team's PR is titled "Bump to net11.0".

It was opened on October 13, the day RC2 shipped. Builds are green and two people have approved it. Nobody has clicked merge.

Then someone posts in the channel: "RC3 dropped yesterday. Security fixes. Are we still on RC2?"

So the question is whether you merge now or wait for GA on November 10. Here's how I'd decide.

## What shipped, in two sentences

[.NET 11 RC2 shipped on October 13, 2026](https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/) with a go-live support license, so Microsoft supports it in production. On October 25 Microsoft shipped [11.0.0-rc.3 as an out-of-band security release](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc3/11.0.0-rc.3.md), fixing a [Brotli decoder out-of-bounds write](https://github.com/dotnet/announcements/issues/494) (CVE-2026-111497) and re-releasing two October 13 fixes that were incomplete.

If you're going to ship .NET 11 before GA, ship RC3. The go-live license is the reason you're allowed to ship at all. The CVE list is why RC2 shouldn't be the build you choose.

Read the fine print before you treat this as an emergency, though. According to [the advisory](https://github.com/dotnet/announcements/issues/494), ASP.NET Core request decompression and HttpClient Brotli decompression are both off by default, so many services aren't exposed at all. RC3 also doesn't fix everything on its own:

- Self-contained and NativeAOT apps have to be rebuilt and republished. A new base image doesn't patch a decoder that's already linked into your app.
- Blazor apps have to update their `Microsoft.AspNetCore.Components.WebAssembly.Server` and `DevServer` package references to get the CVE-2026-102870 fix, according to the RC3 notes.
- A fourth CVE, CVE-2026-114148 (Linux tarball file ownership), isn't fixed in an existing install by extracting a newer archive. The RC3 notes cover what to do on machines you've already set up.

## What "go-live" actually buys you

Go-live doesn't mean "nearly GA, so roughly the same thing". On the [official support policy page](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), RC2's support starts on October 13, 2026 and ends on November 10, 2026. That's 28 days. That page doesn't list RC3 separately. RC3 is an out-of-band servicing release of the go-live RC, not a release with its own listed window.

Think of go-live as a temporary occupancy permit. You can move in and the city backs you, but the permit expires on a fixed date whether or not the final inspection is done.

So you get a supported runtime for four weeks. After that you have to move to the GA build. Merging now doesn't avoid an upgrade. It splits one upgrade into two: the real one now (new TFM, new SDK, new base image) and a version-string change in November.

Here's the calendar the launch posts don't put side by side:

![The November 2026 support calendar](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/dotnet-11-rc2-go-live-ship-before-november-10/images/02-table-1.png)

Look at the last two rows. [The .NET 11 release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/README.md) put its STS support at November 10, 2026 to November 9, 2028. .NET 10 LTS runs until November 14, 2028. The newer release ends five days earlier.

That changes the argument. If you're on .NET 8 or 9 and racing the November 10 cutoff, go to .NET 10, on 10.0.14 or later. It's GA, it's patched every month, and it lasts just as long. The same Brotli CVE is fixed in 10.0.14, and in 8.0.33 and 9.0.22 for the time you have left on those, according to [the advisory's fixed-version table](https://github.com/dotnet/announcements/issues/494). (If Azure Functions on the in-process model are part of that race, I covered the [November 10 Functions migration](https://medium.com/@thecurlybrace/your-azure-functions-lose-support-on-november-10-2026-migrate-without-breaking-them-c640ad96dc3a) separately.) Choose .NET 11 because you want what's in it, not to escape an end-of-support deadline. This piece is only about the upgrade decision. The [RC2 post](https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/) covers what's new.

## My hot take: the PR isn't ready just because CI is green

A TFM bump that compiles has proved very little. Most of what goes wrong in a major-version upgrade happens outside `Program.cs`: the SDK your CI agent picks, the OS inside your container, analyzers and restore warnings that turn into errors, and NuGet packages that pin exact versions.

My stance: RC3 is a reasonable production bet for a stateless service with good integration tests and a fast rollback. That's true only after the four checks below. In my experience, teams often skip at least two of them.

## Check 1: Pin the SDK, or CI will choose one for you

Without a `global.json`, the SDK resolver picks the highest SDK installed on the machine. According to the [global.json docs](https://learn.microsoft.com/en-us/dotnet/core/tools/global-json), whether prerelease SDKs count depends on where `dotnet` runs. Outside Visual Studio, `allowPrerelease` defaults to `true`. Inside a non-preview Visual Studio, it defaults to `false` unless **Use previews of the .NET SDK** is enabled.

So one repo can build on your laptop with the rc.2 SDK, on the build agent with whatever image it has that week, and in Visual Studio with nothing at all. The RC2 post says this release is supported in Visual Studio 2026 Insiders, so your team's stable Visual Studio may not see the SDK.

Pin it explicitly in the PR:

```json
{
  "sdk": {
    "version": "11.0.100-rc.3.26522.148",
    "rollForward": "latestFeature",
    "allowPrerelease": true
  }
}
```

`latestFeature` accepts this SDK or any higher 11.0 feature band and patch that's installed, which should let the GA 11.0.1xx SDK satisfy the pin. Confirm it the day GA lands by having CI print `dotnet --version`, so you don't assume it.

Which setting should you use? Without lock files, use `latestFeature` as above. If you have `packages.lock.json`, the docs recommend `"rollForward": "disable"` so the SDK and the dependency graph stay in lockstep. In that case, use `disable` and bump the exact pin when GA ships.

## Check 2: Your base image just changed operating system

This is the one I'd expect to bite in production. The default `10.0` tag of `mcr.microsoft.com/dotnet/aspnet` is Ubuntu 24.04 (noble). The default `11.0` tag, per the [dotnet-docker README](https://github.com/dotnet/dotnet-docker/blob/main/README.aspnet.md), is **Ubuntu 26.04 (resolute)**.

Changing `10.0` to `11.0` in a Dockerfile looks like a runtime bump. It also upgrades the OS. Any `apt-get install` line, native library, font package or ICU assumption in your Dockerfile now runs on a newer distro. Also, `latest` stays on .NET 10 until GA, so a Dockerfile using `latest` hasn't upgraded at all, whatever your csproj says.

Pin both stages to the patched RC and name the OS explicitly:

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:11.0.100-rc.3-resolute AS build
WORKDIR /src
COPY *.csproj global.json ./
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:11.0.0-rc.3-resolute
WORKDIR /app
COPY --from=build /app .
ENTRYPOINT ["dotnet", "MyService.dll"]
```

Copying the project files and restoring before `COPY . .` keeps the restore layer cached until your dependencies change.

If you want to change only one thing at a time, `10.0-resolute` exists. Move your .NET 10 service to Ubuntu 26.04 first, ship that, then change the runtime. Those are two different kinds of failure, and you'll want to know which one paged you. (If your image build is already slow, my [CI/CD and Docker piece](https://medium.com/@thecurlybrace/ci-cd-docker-your-pipeline-takes-forty-minutes-make-it-faster-4173447928f5) covers layer caching, which helps here.)

## Check 3: The new SDK brings new warnings, and some of them are errors

`AnalysisLevel` defaults to `latest` for any project targeting .NET 5 or later. A new SDK means a new set of analyzer rules running against old code. With `TreatWarningsAsErrors` on, you get build failures you didn't ask for.

There's one I'd expect almost every service to hit, and it isn't an analyzer rule. In .NET 11, [nine Microsoft.Extensions packages moved into the shared framework](https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/extensions-in-shared-framework), including `Logging.Abstractions`, `Options` and `DependencyInjection.Abstractions`. If you reference them explicitly, NuGet restore gives you NU1510. Projects that multi-target (`net10.0;net11.0`) don't get it. The fix is to delete those `PackageReference` lines. Do it in the bump PR, deliberately, so you don't find out about it at 4 p.m. on release day.

Keep the rest of the upgrade PR about the runtime and pin the analyzers for now:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net11.0</TargetFramework>
    <AnalysisLevel>10.0</AnalysisLevel>
    <!-- Stopgap only, until the PackageReference lines are deleted -->
    <WarningsNotAsErrors>$(WarningsNotAsErrors);NU1510</WarningsNotAsErrors>
  </PropertyGroup>
</Project>
```

`AnalysisLevel` controls the CA and IDE analyzer rules only. NU1510 comes from NuGet restore, so the `AnalysisLevel` pin does nothing for it. Either delete the references or use the `WarningsNotAsErrors` stopgap.

Then open a second PR that removes the analyzer pin and fixes what appears. That way a reviewer can read each diff.

## Check 4: Your NuGet graph has to support RC3

NuGet will happily restore `net10.0` libraries into a `net11.0` app. The trouble comes from packages that are tied to a specific framework release. EF Core providers are the classic case.

There's a live example. On October 26, someone opened [an issue on the Npgsql EF Core provider](https://github.com/npgsql/efcore.pg/issues/4111): the provider's `11.0.0-rc.2` release pins exact rc.2 EF Core versions. Move your other EF Core packages to rc.3 and you get version conflicts, which NuGet reports as NU1608 and which become build failures under `TreatWarningsAsErrors`. As of October 26, 2026, the issue was open with no maintainer response.

This creates a real conflict between the two RCs. The security fix says go to RC3, but your database provider may still require RC2. Before you merge, find every package with a version tied to the framework (EF Core and its provider, ASP.NET Core packages, anything versioned `11.0.0-rc.*`) that is still on rc.2, then check whether an rc.3 build exists:

```bash
# Anything still on rc.2?
dotnet list package --include-transitive | grep "rc.2"

# Which packages have a newer prerelease available?
dotnet list package --outdated --include-prerelease
```

If a package still shows rc.2 and the outdated list shows no rc.3 build for it, that service isn't ready. Wait for GA.

## The behaviour change your monitoring will notice first

One item from the [.NET 11 breaking changes list](https://learn.microsoft.com/en-us/dotnet/core/compatibility/11) matters for anything running in an orchestrator. In .NET 11, when a `BackgroundService` throws and the host stops (the default `StopHost` behaviour), `RunAsync` and `StopAsync` now fail instead of completing successfully. Your process exits non-zero.

That's the correct behaviour, and Microsoft's recommended action is to do nothing. But a worker that used to crash with exit code 0 will now show up as a failed container, a restarting pod or a CrashLoopBackOff. Restart counts and alerts may jump the day you deploy, even though nothing new is failing. Tell whoever is on call before you deploy.

## Who should ship now, and who should wait

![Merge now vs wait for GA](https://raw.githubusercontent.com/deeppatel99/curlybrace-autopilot/main/posts/dotnet-11-rc2-go-live-ship-before-november-10/images/03-diagram-compare-1.png)

My honest view: for most teams, the biggest benefit of merging now isn't production. It's finding out what breaks while the PR is fresh and the people who wrote it still remember why. Do all four checks, deploy RC3 to staging today, and promote one low-risk service to production. When GA ships, the GA PR is mostly version strings.

If any of the four checks fails, don't ship the RC. The go-live window ends in 15 days anyway. Just wait for GA.

> Go-live means Microsoft supports the RC in production for four weeks. It doesn't mean your upgrade PR is ready.

Do this today: open your bump PR, change the base image tag to `11.0.0-rc.3-resolute`, and run the two package commands from Check 4. If the image doesn't build, or a package still shows rc.2 with no rc.3 available, you have your answer.

Now the argument I want to have: if you're on .NET 8 this week, are you going to .NET 10 LTS or straight to .NET 11 to skip a hop? I say anyone choosing 11 for the support window hasn't done the arithmetic. Tell me I'm wrong.

**Follow The Curly Brace for more backend war stories — no theory, only scars.**
