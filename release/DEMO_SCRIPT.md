# Demo script (3 minutes)

1. **Owners (0:00–0:30).** Screen 1: seven independent owners (five buyers, a factory, an engineer), 700 registered
   workers, and the number of genuine NVIDIA NIM decisions, each with its provider response ID. Each card shows the
   owner's goal and the only fields it publishes.
2. **Discovery (0:30–0:55).** Screen 2: seven signed intents. The matcher finds 5 × 20 = 100 units, which meets the
   factory's minimum order of 100; no buyer could order alone. Supplier prices stay private, so price feasibility is
   decided later, in negotiation.
3. **Negotiation (0:55–1:50).** Screen 3: version 1 at $480 ($96 per buyer). An injected test event raises the
   factory's price; version 2 at $540 ($108 per buyer) is rejected by all five buyers; the cheaper design D-C fails the
   engineer's test fixture; version 3 with design D-B at $495 ($99 per buyer) is accepted by all seven, each with its
   own signature.
4. **Execution (1:50–2:20).** Screen 4: 100 units manufactured, the lot certified, five shipments of 20 and five
   ledger payments, all simulated. Every action shows the owner's own admission decision.
5. **Judge and payments (2:20–3:00).** Screen 5: the independent Judge passes every check and detects every tamper
   test. Baselines: buyers alone cannot order; known peers and discovery plus federation complete the deal; a central
   matcher finds the same group. Show the PayPal status exactly as recorded. Finally, press the red button: an
   unregistered peer asks the factory for its unit cost and is refused, with no side effect.

Mention the failures too: the first attempt failed closed on an AI provider error, and the second failed the Judge
because a private value leaked into a rationale. Both are kept as evidence.
