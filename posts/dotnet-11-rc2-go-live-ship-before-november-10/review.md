# Review — .NET 11 RC2 Has a Go-Live License. Should You Ship It Before November 10?

- Mode: `local`
- Tags: Dotnet, Csharp, Docker, Devops, Software Development
- Visuals: 3
- Claude usage: 529,723 in / 34,851 out tokens (Claude subscription — no extra charge)

## Your checklist

- [ ] Open https://deeppatel99.github.io/curlybrace-autopilot/posts/dotnet-11-rc2-go-live-ship-before-november-10/paste.html (GitHub Pages), Ctrl+A, Ctrl+C, paste into https://medium.com/new-story
- [ ] Tags to add: Dotnet, Csharp, Docker, Devops, Software Development

## Format check

- All format checks passed.

## AI reviewer report

VERDICT: NEEDS FIXES

## Issues
- [severity: medium] [location: section "Check 3: The new SDK brings new warnings…"] The code doesn't fix the problem the section describes. NU1510 is a NuGet restore warning, not an analyzer rule, so pinning `<AnalysisLevel>10.0</AnalysisLevel>` has no effect on it. Under `TreatWarningsAsErrors` the bump PR still fails, and readers will assume the pin covered it. -> Make the NU1510 fix part of the bump PR: delete the nine `PackageReference` lines, or add `<WarningsNotAsErrors>$(WarningsNotAsErrors);NU1510</WarningsNotAsErrors>` as a stopgap. Add one sentence explaining that `AnalysisLevel` controls CA/IDE rules only. Also mention, per the [breaking-change page](https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/extensions-in-shared-framework), that multi-targeted projects (`net10.0;net11.0`) don't get NU1510.
- [severity: medium] [location: section "Check 4" and "Do this today"] `dotnet list package --include-transitive | grep "11.0.0-rc"` lists every RC package, including the ones already on rc.3. It doesn't show whether a compatible build exists, and a grep can't "fail" the way the closing action says. -> Grep for the stale version (`grep "rc.2"`), and add `dotnet list package --outdated --include-prerelease` to show which packages have no rc.3 build. Note that NuGet reports the exact-pin conflict as NU1608. Reword the action as "if any package still shows rc.2 with no rc.3 available…".
- [severity: medium] [location: section "What shipped, in two sentences"] The fine print on the security release is missing, and this format requires it. (a) The [advisory](https://github.com/dotnet/announcements/issues/494) says ASP.NET Core request decompression and HttpClient Brotli decompression are off by default. Many services aren't exposed at all, which changes how urgent RC2 → RC3 is. (b) Self-contained and NativeAOT apps must be rebuilt and republished. A new base image doesn't patch a decoder already linked into the app. (c) The [RC3 notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc3/11.0.0-rc.3.md) say Blazor apps must update the `Microsoft.AspNetCore.Components.WebAssembly.Server`/`DevServer` package references for the CVE-2026-102870 fix. (d) There's a fourth CVE (CVE-2026-114148, Linux tarball ownership) that a newer archive doesn't fix in an existing install. -> Add a short "what RC3 doesn't fix by itself" paragraph covering (a)–(d). Link the advisory inline for the "out-of-bounds write" wording, because the release notes you link only say "Brotli library vulnerability".
- [severity: medium] [location: section "Who should ship now" / table note] The ".NET 8/9 → go to .NET 10" advice leaves out that the same CVE is patched in 10.0.14 (and 8.0.33, 9.0.22). Readers following it need the right patch level. -> Add "on 10.0.14 or later" and cite the advisory's fixed-version table.
- [severity: medium] [location: subtitle; section "My hot take"] "the four checks most upgrade PRs skip" and "Most teams skip at least two of them" read as findings, but nothing backs them up. -> Label them as opinion ("In my experience, teams often skip…") or cut them. Unless the author's notes back it, also soften "This is the one that surprises people in production" in Check 2.
- [severity: medium] [location: front matter] For a .NET release analysis the lead tag should be `Dotnet`, not `Devops`. -> `tags: [Dotnet, Csharp, Docker, Devops, Software Development]`.
- [severity: medium] [location: whole article] The house style asks for one analogy for the mechanism, and the article has none. -> Add one where "What go-live actually buys you" explains it. For example: go-live is a temporary occupancy permit. You can move in and the city backs you, but it expires on a fixed date whether or not the final inspection is done.
- [severity: medium] [location: section "Who should ship now" / diagram "You want .NET 11 features"] The article tells readers to choose .NET 11 "for its features and runtime improvements" but never names one. That leaves the format's "what changes in a developer's day-to-day" step and the upside of adopting empty. -> Name one or two features confirmed in the [RC2 post](https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/) with a short before/after, or drop the features bullet and say plainly that this piece is only about the upgrade decision.
- [severity: low] [location: section "Check 2" Dockerfile] The runtime stage is pinned, but the build stage uses the floating `sdk:11.0`, which contradicts the section's own advice. `COPY . .` before `publish` also defeats the restore-layer caching the linked CI/CD article recommends. -> Use `mcr.microsoft.com/dotnet/sdk:11.0.100-rc.3-resolute` (confirm the tag in the [dotnet-docker sdk README](https://github.com/dotnet/dotnet-docker/blob/main/README.sdk.md)), and copy the `*.csproj` files and run `dotnet restore` before `COPY . .`.
- [severity: low] [location: section "Check 3" XML] `<Project>` without `Sdk="Microsoft.NET.Sdk"` isn't a valid csproj. -> Label it `Directory.Build.props` or add the Sdk attribute.
- [severity: low] [location: section "Check 1"] "Inside a non-preview Visual Studio, it defaults to false" leaves out the docs' exception: it's true if **Use previews of the .NET SDK** is enabled. Also, recommending `latestFeature` and then quoting `disable` for lock files leaves the reader with two answers. -> Mention the VS option, and say which setting to use when (for example, "if you have `packages.lock.json`, use `disable` and bump the pin at GA").
- [severity: low] [location: slug] `ship-before-dotnet-conf` refers to an event the article never mentions or verifies. -> `dotnet-11-rc2-go-live-ship-before-november-10`.
- [severity: low] [location: section "What go-live actually buys you"] The [support policy page](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) lists RC2's go-live window only, with no RC3 entry. -> Say that RC3 is an out-of-band servicing release of the go-live RC, rather than implying it has its own listed window.
- [severity: low] [location: section "Check 4"] "When I checked, it was still open" depends on when it's read, and the issue was opened today. -> Add a date: "As of October 26, 2026, it was open with no maintainer response."
- [severity: low] [location: asset "60-Second Pre-Merge Checklist"] All eight lines repeat the body almost word for word. -> Cut it to the four checks plus "Ship RC3", or drop it. The diagram already gives the decision.
- [severity: low] [location: section "Check 3"] "which is a nice change" is filler. -> Cut it.

## Fact-check notes for the author
- RC2 shipped October 13, 2026 with a go-live license; supported in Visual Studio 2026 Insiders -> VERIFIED https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/
- RC3 out-of-band release on October 25, 2026, SDK 11.0.100-rc.3.26522.148, re-releases two incomplete October 13 fixes (CVE-2026-70197, CVE-2026-102870) -> VERIFIED https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc3/11.0.0-rc.3.md
- CVE-2026-111497 is a Brotli decoder out-of-bounds write -> VERIFIED https://github.com/dotnet/announcements/issues/494 (CVSS 8.1; not exposed by default; fixed in 8.0.33 / 9.0.22 / 10.0.14 / 11.0.0-rc.3)
- RC2 support October 13 – November 10, 2026 (28 days); .NET 8 and .NET 9 end November 10, 2026; .NET 10 LTS ends November 14, 2028; STS is two years -> VERIFIED https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core
- .NET 11 STS runs November 10, 2026 – November 9, 2028 -> VERIFIED https://github.com/dotnet/core/blob/main/release-notes/11.0/README.md (not yet on the policy page)
- Without global.json the highest SDK is used; `allowPrerelease` defaults to true outside VS; `latestFeature` semantics; `disable` recommended with lock files -> VERIFIED https://learn.microsoft.com/en-us/dotnet/core/tools/global-json (VS exception for the "Use previews" option left out)
- `aspnet:11.0` = Ubuntu 26.04 resolute, `10.0` = 24.04 noble, `11.0.0-rc.3-resolute` and `10.0-resolute` exist, `latest` = 10.0 -> VERIFIED https://github.com/dotnet/dotnet-docker/blob/main/README.aspnet.md
- `AnalysisLevel` defaults to `latest` for .NET 5+; `10.0` is an accepted value -> VERIFIED https://learn.microsoft.com/en-us/dotnet/core/project-sdk/msbuild-props
- Nine Microsoft.Extensions packages in the shared framework, NU1510, remove the PackageReference -> VERIFIED https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/extensions-in-shared-framework
- BackgroundService failure under StopHost now makes RunAsync/StopAsync fail with a non-zero exit; recommended action is to do nothing -> VERIFIED https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/ihost-runasync-stopasync-throw-backgroundservice-failure
- Npgsql issue #4111 opened October 26, rc.2 provider pins exact rc.2 EF Core, open with no maintainer response -> VERIFIED https://github.com/npgsql/efcore.pg/issues/4111 (as of October 26, 2026)
- Calendar: October 26, 2026 is a Monday; 15 days from October 26 to November 10 -> VERIFIED (date arithmetic)
- "Most teams skip at least two" of the checks -> UNVERIFIED: no source; label it as opinion or cut it
- RC3 is covered by the same go-live window -> UNVERIFIED: the policy page lists RC2 only; check https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core after it updates

Sources:
- [.NET 11 RC2 announcement](https://devblogs.microsoft.com/dotnet/dotnet-11-rc-2/)
- [11.0.0-rc.3 release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc3/11.0.0-rc.3.md)
- [CVE-2026-111497 advisory](https://github.com/dotnet/announcements/issues/494)
- [.NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)
- [.NET 11 release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/README.md)
- [global.json docs](https://learn.microsoft.com/en-us/dotnet/core/tools/global-json)
- [dotnet-docker aspnet README](https://github.com/dotnet/dotnet-docker/blob/main/README.aspnet.md)
- [MSBuild properties: AnalysisLevel](https://learn.microsoft.com/en-us/dotnet/core/project-sdk/msbuild-props)
- [Extensions in shared framework](https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/extensions-in-shared-framework)
- [Breaking changes in .NET 11](https://learn.microsoft.com/en-us/dotnet/core/compatibility/11)
- [BackgroundService breaking change](https://learn.microsoft.com/en-us/dotnet/core/compatibility/extensions/11/ihost-runasync-stopasync-throw-backgroundservice-failure)
- [Npgsql issue #4111](https://github.com/npgsql/efcore.pg/issues/4111)
