# Throwaway: EIP identity API probe

## Question

Can LITTLE_AVATOR obtain a supported, machine-to-machine identity contract from
EIP without exporting a browser Cookie, session, or token?

## Scope

Phase 1 uses a user-operated, already authenticated EIP browser session only to
observe the available identity-related interface. This prototype records only
redacted capability evidence.

It does not persist a name, employee identifier, Cookie, session, token,
password, private key, or raw response body. It does not submit any EIP form or
call an unobserved endpoint.

The observed result is `browser_only`: an authenticated EIP identity and
directory interface exist, but no AVATOR-supported API contract was established.
The A2A MVP therefore does not depend on EIP as a trust provider. It uses local
device identity, TOFU, and local capability policy instead. A future EIP API
could become an optional stronger trust provider.

## Success criteria

The redacted evidence can answer all of these without retaining personal data:

- an authenticated EIP identity state is observable;
- a supported AVATOR authentication contract is either identified or shown to be
  unavailable in the observation scope;
- the evidence explains whether it is usable by AVATOR without a browser
  session.

## Evidence format

Use [evidence.template.json](evidence.template.json) as a local worksheet.
Create `evidence.local.json` only if needed; it is ignored by Git and must keep
all values redacted.

## Verdict rules

- `supported_for_avator`: EIP documents an AVATOR authentication method and a
  read-only identity API.
- `browser_only`: identity is visible only through the current browser session.
- `not_found`: no supported identity interface was found during the agreed
  observation scope.

`browser_only` is useful evidence, but it is not a production identity API.
