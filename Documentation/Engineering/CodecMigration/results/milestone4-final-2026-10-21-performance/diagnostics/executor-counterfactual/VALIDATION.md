# Counterfactual build and correctness preflight

The single original-Consumer release build completed with exit 0 on 21 October
2026, using explicit Command Line Tools Swift 6.4. Its warning for `await` on the
now-synchronous owned decode call is retained in `benchmark-build.log`.

All six 37×23 cases (12/16-bit flat, ramp and noise) passed the original
Consumer's complete sample verification and byte-equality checks. They ran with
zero warmups and one emitted observation solely as correctness preflights.
Those durations are retained and are not performance evidence.

The executable SHA-256 is
`8d098f8ef8b2ce8aa39d9da818922525b660a873e33a0e651aad8a9521d51292`.
The one-line signature patch SHA-256 is
`411365a163290261bad2f08a7afd8b1526c25010e365e47d70d03fa9aca0ef3f`.
The full diagnostic patch SHA-256 is
`3363c2b8856fcb4e591a7e12b49272a545a0bd3930ea8f28b20ac257735d5227`.

Every other source/test byte and the Consumer were checked unchanged.
`build-identity.json` retains exact inputs, command and six preflight results.
No tests of a modified production contract, production promotion, qualified
timing or acceptance waiver are implied. This synchronous API is a deliberately
noncompliant diagnostic counterfactual; the production executor policy remains
required.
