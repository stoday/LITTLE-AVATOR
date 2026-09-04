# Throwaway: EIP onboarding plus A2A TOFU gate

## Question

Does the user experience make the intended boundary clear: a real EIP browser
login is completed by the user, then AVATOR checks local device continuity
before it permits the existing A2A negotiation to start?

## Security boundary

This prototype opens EIP but does not read, export, persist, hash, or transmit
an EIP Cookie, session, token, password, account name, or API response. EIP
login is a user-operated onboarding ceremony, not machine-verifiable evidence.

The pre-negotiation gate simulates two local device identities and exercises
TOFU continuity. A changed fingerprint causes `rejected_key_changed` and the
existing four-agent negotiation is not started.

## Run

1. Start the EIP onboarding page:

   ```powershell
   C:\Python313\python.exe .\prototypes\a2a_admin_secretary_failure_reporting\run_with_eip_onboarding.py
   ```

2. Complete EIP login yourself in the opened browser. Do not give the program
   credentials or copy browser data.
3. Verify the identity gate without running the model:

   ```powershell
   C:\Python313\python.exe .\prototypes\a2a_admin_secretary_failure_reporting\run_with_eip_onboarding.py --eip-login-confirmed
   ```

4. Prove that a changed key blocks before negotiation:

   ```powershell
   C:\Python313\python.exe .\prototypes\a2a_admin_secretary_failure_reporting\run_with_eip_onboarding.py --eip-login-confirmed --simulate-key-change
   ```

5. Only after the successful gate, run the existing four-agent failure case:

   ```powershell
   C:\Python313\python.exe .\prototypes\a2a_admin_secretary_failure_reporting\run_with_eip_onboarding.py --eip-login-confirmed --run-negotiation
   ```

## What this proves

- the intended user-mediated EIP onboarding flow is usable;
- a local TOFU gate precedes A2A negotiation;
- a changed key blocks before any schedule write or agent negotiation.

It does not prove EIP issued a device identity, verified a public key, or
provides an AVATOR API.
