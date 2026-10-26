# Common Ground — PNC housing opportunity pilot

A buildless static dashboard for the four supplied housing peer cases. Open `index.html` directly or serve this directory with `python -m http.server 8765`.

## Presenting the demo

1. Open Community matches. Explain that the match score measures conditional institution–intervention fit, while the supplied affordability and access scores measure housing outcomes.
2. Select Bucks County and open Peer comparison. Show every peer and the affordable-unit ratio. Avoid describing aggregate mortgage denial rates as Bucks’s primary barrier.
3. Open Action plan, then Institution toolkit. Show the link between the barrier, existing PNC capabilities, delivery partners and outcome measures. Highlight mortgage hardship assistance as a separate retention pathway for eligible existing borrowers.
4. Open Configure priorities & capacity. Change the resource scenario or weights, then show Score breakdown. Ratings and resource envelopes are illustrative judgments, not verified PNC commitments or calibrated forecasts.
5. Show Lafayette to demonstrate evidence discipline: a high denial rate triggers a denial-reason review before selecting an underwriting intervention.
6. Finish with Evidence & method and Export analysis.

Suggested framing: “Our existing ML analysis identifies comparable markets and divergence. Common Ground adds an evidence-informed decision layer: which barriers a financial institution can plausibly address, with which tools, under which resource and eligibility conditions. Today’s prototype uses prepared evidence and transparent scoring; a future AI service would retrieve and synthesize new evidence while keeping the score auditable.”

## Static versus live AI

This version supports interactive filtering, weighted scoring, capacity scenarios, peer comparison and analysis exports entirely in the browser. It does not call a live AI model, accept private institution uploads or authenticate users. GitHub Pages can serve it without a backend.

A live service would add a secure API backend, authentication, institution-specific data, saved scenarios, source ingestion and AI-assisted synthesis of new programs and communities. It would have operating costs, latency and evidence-quality controls. GitHub Pages could still host the interface, with the backend hosted separately. Never place API secrets in static JavaScript.

## Scoring

Score = 100 × sum(weight × rating / 5) / sum(weights). Five factors initially have equal weight. All-zero weights produce an undefined score shown as a dash. Factor ratings are provisional analyst assessments and should be independently reviewed.

Capacity uses an explicit tier-based demonstration heuristic; business priority adjusts expansion feasibility. Budget, staffing, timeline, approvals and local program eligibility are not verified PNC information. Unknown eligibility means conditional readiness, not an approved match. Evidence contributes as the fifth factor and is also displayed as a qualitative label.

## Data provenance and limits

Peer groups and outcome values come from the user-supplied `peer divergence model`. The affordability definition follows its 75% price-to-income / 25% rent-to-income scorecard. Existing composite scores are preserved because their normalization is unavailable. There are 20 case rows and 19 unique counties (Bucks appears twice).

Current program capabilities and local barrier leads were checked against official linked sources. User research helped identify preservation, wildfire and flood pathways. Historical, city-level and draft sources are labeled. Local evidence does not establish causal attribution to the supplied score gaps. Original ML models were not rerun. PNC’s local resources, eligibility and expected intervention effects remain unverified.

## GitHub Pages

Publish these files in `housing-match/` within the supplied `izzyh-gif.github.io` repository. The intended URL is `https://izzyh-gif.github.io/housing-match/`. Preserve the existing root homepage and other projects. A successful push is not itself proof that GitHub Pages finished deployment.

## Future access controls

Add authentication through a backend identity provider, institution-scoped authorization, private data storage, audit logs and server-side secret handling. A visual login screen alone would not protect private data. No personal borrower records are used here.

Independent case competition prototype. Not affiliated with or endorsed by PNC.
