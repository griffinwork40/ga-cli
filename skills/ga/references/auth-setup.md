# GA CLI — Authentication Setup

The `ga` CLI uses **user OAuth** (an installed/"Desktop" client), read-only
scope `https://www.googleapis.com/auth/analytics.readonly` **only**. It never
requests write/admin-write scopes.

## 1. Google Cloud project + enable BOTH APIs

In the [Google Cloud Console](https://console.cloud.google.com/):

1. Create (or select) a project.
2. Enable **both** of these APIs (APIs & Services → Library):
   - **Google Analytics Admin API** — powers `ga properties` (accountSummaries).
   - **Google Analytics Data API** — powers `ga report` and all canned reports
     (runReport / getMetadata).

   Enabling only one will half-break the CLI: property discovery needs Admin,
   every data report needs Data.

## 2. Create a Desktop OAuth client

1. APIs & Services → **Credentials** → **Create Credentials** → **OAuth client ID**.
2. Application type: **Desktop app**.
3. Download the client JSON and save it to:

   ```
   ~/.config/ga-cli/client_secret.json
   ```

   Or override the path with the `GA_CLIENT_SECRET` environment variable.

## 3. Configure the OAuth consent screen (scope)

1. APIs & Services → **OAuth consent screen**.
2. User type: **External** is fine for a personal project.
3. Add the scope: `.../auth/analytics.readonly` (read-only Analytics).
4. Add your Google account (the one with GA access) as a **Test user** while the
   app is in **Testing** mode.

## 4. First-run browser consent

The first API call (or `ga auth --reauth`) opens a browser for consent:

```bash
ga auth --reauth
```

Because the app is unverified (Testing mode), Google shows a
**"Google hasn't verified this app"** screen. This is expected:

- Click **Advanced** → **Go to \<app\> (unsafe)** → allow **read-only Analytics**.

On success the refresh token is cached to:

```
~/.config/ga-cli/token.json      # chmod 0600, contains the refresh token
```

After the first consent, every subsequent command refreshes silently from this
cached token — **no browser**. `ga auth` (without `--reauth`) just loads/refreshes
and prints an `authorized / token cached` status; it never prints token contents.

## Token cache locations & overrides

| Purpose | Default path | Env override |
|---|---|---|
| OAuth client secret | `~/.config/ga-cli/client_secret.json` | `GA_CLIENT_SECRET` |
| Cached refresh token | `~/.config/ga-cli/token.json` | `GA_TOKEN` |

The CLI never prints, logs, or echoes the contents of either file.

## ⚠️ CAVEAT — Testing-mode tokens expire in ~7 days

**This is the single most important operational gotcha.** While the OAuth
consent screen is in **Testing** (unverified) mode, Google issues refresh tokens
that **expire after ~7 days**. Interactive use is unaffected (you just re-consent
in the browser), but this **will break any unattended / daemon / scheduled run**:
after ~7 days the cached token stops refreshing and every command fails with a
token-refresh error until a human re-runs `ga auth --reauth`.

**Fix (choose one) before wiring `ga` into any scheduled/headless job:**

1. **Publish the OAuth consent screen** (APIs & Services → OAuth consent screen →
   **Publish app** → move from Testing to In production). Published apps issue
   long-lived refresh tokens that don't expire on the 7-day clock. For a
   read-only, single-user internal tool this is low-friction (you can leave it
   unverified; the "unverified app" screen persists but the token stops expiring).
2. **Use a service account** for the scheduled leg instead of user OAuth: create
   a service account, grant it **Viewer** on the GA4 property (Analytics Admin →
   Property Access Management → add the service-account email as Viewer), and
   authenticate via its key file. Service-account credentials don't ride the
   7-day Testing-mode clock. *(The current CLI is wired for user OAuth; adding a
   service-account auth path is a small follow-on if/when a scheduled leg needs
   it.)*

Until one of those is done, treat `ga` as an **interactive** tool and expect to
re-consent roughly weekly.
