# SimpleFIN / MX Security Review

**Last reviewed:** 2026-11-17
**Scope:** Whether it is reasonable to link our bank accounts to this app via SimpleFIN Bridge (which uses MX underneath). Two users (household), self-hosted on a Raspberry Pi.
**Status:** Based on public documentation only. No independent audit or penetration test was performed. Re-verify the linked sources before relying on this, since policies change.

## TL;DR

- SimpleFIN access is **read-only**. The protocol shares account balances and transactions; it has no ability to move money.
- Our bank usernames and passwords are entered **only at SimpleFIN Bridge**, which hands them to **MX**. They never touch this app and, per SimpleFIN, never touch SimpleFIN's servers.
- The app only holds an **Access URL**, a revocable bearer credential that can read (not write) our data.
- The real risks are: (1) MX is a large third party holding our credentials and data, (2) SimpleFIN is a small operator with limited public assurance, (3) a leaked Access URL exposes our transaction history until revoked, and (4) there was one disclosed cross-user data exposure incident in May 2026.
- Verdict: acceptable for a personal budgeting app **if** we protect the Access URL, enable 2FA on the Bridge account, and are comfortable with the residual third-party risk described below.

## How it works

1. We sign in to SimpleFIN Bridge and link our banks there (not in this app).
2. The Bridge issues a one-time **Setup Token** (a base64-encoded claim URL).
3. This app POSTs to the claim URL once and receives a permanent **Access URL** with HTTP Basic credentials embedded in it. The Setup Token is dead after that.
4. The app calls `GET {ACCESS_URL}/accounts` to read balances and transactions.
5. We can disable the Access URL at any time from the Bridge.

## What SimpleFIN is

- Operated by One Part Rain, LLC (d/b/a SimpleFIN), a small company, not a large financial institution.
- Implements an open protocol for sharing read-only financial data with third parties.
- Per its security page:
  - Sign-in is passwordless (passkey or emailed code); TOTP 2FA is recommended for sensitive actions.
  - You are notified whenever your transaction data is accessed from a new IP address.
  - Bank credentials are outsourced to MX and never touch SimpleFIN servers.
  - Staff can view transactions for debugging only if the user grants access; access is logged and expires.
  - Hosted on DigitalOcean; server access via VPN and keyed SSH; rate limiting against brute force.
  - Third-party security firms perform regular testing (auditor and results are not named publicly).
  - Billing is handled by Stripe, email by Postmark.
- Per its privacy policy:
  - The Bridge itself does not retain banking data; MX does.
  - MX retains account and transaction data indefinitely so it can be re-requested. Deleting an account or connection removes the data from MX within about 2 weeks.
  - Our email address may be used for service messages and to inform us about SimpleFIN products.
  - Information may be transferred in a sale, merger, or similar event.
  - There is no guarantee of security; the policy states plainly that no system is impenetrable.
- The security page opens by acknowledging there is inherent risk in giving bank credentials to any website, including theirs.

## What MX is

- A large, privately held B2B financial data aggregator (Lehi, Utah) that works with thousands of financial institutions. SimpleFIN uses it to connect to banks and to store credentials.
- MX states it maintains **SOC 2 Type II** and **PCI DSS** compliance, updated annually, encrypts data in transit and at rest (AES-256/TLS), hosts in U.S. data centers, and uses OAuth where banks support it so that credentials are not shared.
- MX publishes a trust center and a security whitepaper, and offers its reports to customers under NDA. We (as a SimpleFIN end user) cannot see the reports.
- Most of the above is **vendor-stated**. We have not read the SOC 2 report.
- Not verified: which of our institutions connect to MX via OAuth versus credential-based access. If a bank uses credential-based access, MX stores our bank login (encrypted). This is the standard aggregator tradeoff.

## Disclosed incident

**2026-05-28 — Account mixing (MX bug).** According to SimpleFIN's security page, a bug deployed on MX's system caused up to 39 users to potentially see each other's data for about 4 hours. Exposed data was limited to what the SimpleFIN API returns (transactions, balances, account names). No bank credentials were exposed. Affected users were notified.

Takeaway: SimpleFIN disclosed it publicly, which is a good sign. It also shows our exposure includes MX's engineering quality. I found no other public SimpleFIN incidents and no public record of an MX credential breach, but absence of evidence is not proof; MX's detailed breach history is not freely available.

## Risk summary

| Risk | Likelihood | Impact | Notes |
| --- | --- | --- | --- |
| Funds stolen via SimpleFIN | Very low | High | Read-only by design; no payment capability |
| Bank credentials leaked via aggregator | Low | High | Held by MX, not SimpleFIN or this app; MX is SOC 2 Type II per its own claims |
| Transaction data exposed via MX/SimpleFIN bug or breach | Low-medium | Medium | Has happened once (May 2026); data is balances, transactions, account names |
| Access URL leaked from our Pi/repo/logs | Low-medium | Medium | Grants read access until revoked; fully within our control |
| SimpleFIN account takeover (email/passkey) | Low | Medium-high | Mitigate with passkey + TOTP; attacker could mint new tokens |
| SimpleFIN disappears or changes terms | Low-medium | Low | Small operator; our data in the app is a cache of Sheets/own storage |
| Token disabled due to over-polling | Medium (if buggy) | Low | Limit is about 24 requests/day |

## Recommendations

### On the SimpleFIN account

1. Sign in with a **passkey** and enable **TOTP 2FA**.
2. Use an email account with strong 2FA, since email is the recovery path for the Bridge.
3. Pay attention to the **new-IP access alert emails**. Our Pi has a stable IP, so an alert from a new IP means something is wrong: revoke the Access URL immediately.
4. Decide deliberately whether to use **one Bridge account for both of us or one each**. A shared account gives a single Access URL covering all linked accounts; separate accounts give independent revocation and smaller blast radius per credential.
5. Do not grant debugging access to SimpleFIN staff unless actively working a support issue.
6. Confirm the canonical Bridge hostname before bookmarking it. The official docs use both `bridge.simplefin.org` and `beta-bridge.simplefin.org`. Type or bookmark it ourselves rather than following emailed links.

### On the bank side

1. Enable 2FA and transaction alerts at each bank.
2. Check whether each bank offers OAuth-based connections to MX, and prefer those when available.
3. Periodically review authorized third-party access in each bank's settings.

### On this app (Raspberry Pi)

 1. Treat the Access URL like a password. Keep it in an environment variable or a file readable only by the app's user (mode 600), outside the repo. `.gitignore` already excludes `*.env`; keep it that way and never commit the URL or Setup Tokens.
 2. Never log the Access URL (it contains credentials in the URL itself). Check error messages, tracebacks, and request logs for leakage.
 3. Require HTTPS when calling the Access URL and refuse redirects so credentials are never replayed to another host.
 4. Do not expose the Flask app directly to the internet. Keep it on the LAN or behind a VPN/authenticated reverse proxy. The dashboard will show real transactions and has no auth today.
 5. Set conservative sync behavior: cache aggressively, poll at most a few times per day, use a random minute rather than the top of the hour, and surface any `errlist` errors from the API rather than swallowing them.
 6. Encrypt the Pi's disk or at least restrict physical/SSH access, since the Access URL and any cached transaction data live there.
 7. Store only the data the app needs, and have a plan to delete cached transaction data when we disconnect.

### Operational

 1. Know the revocation drill: disable the Access URL in the Bridge, mint a new Setup Token, claim it, and update the app's config. Test this once so it isn't first attempted during an incident.
 2. If we ever disconnect, **delete the connection and account at the Bridge** so MX removes the data (about 2 weeks per the privacy policy).
 3. Re-review this document when SimpleFIN or MX announce incidents or policy changes, and at least annually.

## Open questions / not verified

- Which of our banks connect via OAuth versus stored credentials in MX.
- Who SimpleFIN's third-party auditors are and what they found.
- MX's SOC 2 Type II report contents (available only under NDA to customers).
- Whether SimpleFIN holds any attestation of its own (none found publicly).

## Sources

- SimpleFIN Bridge security policy: <https://beta-bridge.simplefin.org/info/security>
- SimpleFIN Bridge privacy policy (effective 2026-10-27): <https://beta-bridge.simplefin.org/info/privacy>
- SimpleFIN Bridge developer guide: <https://beta-bridge.simplefin.org/info/developers>
- SimpleFIN protocol: <https://www.simplefin.org/protocol-v1.html>
- MX trust center: <https://mx.com/trust>
- MX security whitepaper: <https://mx.com/assets/resources/whitepapers/security-whitepaper.pdf>
- FINRA on data aggregation risks: <https://www.finra.org/investors/insights/be-mindful-data-aggregation-risks>
