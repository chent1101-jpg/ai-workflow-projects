# GTM Container Audit — EXAMPLECARE

**Container** `GTM-EXAMPL1` &nbsp;·&nbsp; **Audited** 2026-07-28 &nbsp;·&nbsp; **Site profile** healthcare clinic

19 tags · 8 triggers · 1 user variable · 17 built-in variables

## Executive summary

**27 findings.** 1 critical · 13 high · 7 medium · 6 low

Ranked by business impact rather than by severity — a high-severity finding on unused config matters less than a medium-severity one that silently corrupts reported numbers.

1. **cHTML - Transfer Query Parameters** — Regulatory exposure  
   The 'cHTML - Transfer Query Parameters' tag appends Google Ads click identifiers (gclid) to links going to 'hipaa-submit.formvendor.com', coupling an ad click ID with a health-intake funnel — precisely the pattern that has triggered health-privacy regulatory actions.

2. **StackAdapt Script** — Regulatory exposure  
   StackAdapt fires unconditionally on every page, sending page views on condition-specific and treatment pages to an ad retargeting platform before any consent decision, which on a healthcare site risks disclosing health-inferred browsing behavior to a third-party ad vendor.

3. **EXAMPLECARE** — Regulatory exposure  
   Every tag in the container — including the four custom HTML/image tags that can execute arbitrary code — loads without any consent gate, violating regulatory consent requirements and exposing the clinic to CCPA/state-privacy enforcement regardless of whether individual tags transmit data.

4. **Request Appointment Existing - GA4, Request Appointment All - GA4** — Decision-corrupting data  
   When a user submits an appointment request, both 'request_appointment_all' and 'request_appointment_existing' fire, artificially doubling the conversion count and making cost-per-acquisition look half as expensive as it really is.

5. **Request Appointment New Trigger - GA4, Request Appointment All - GA4** — Decision-corrupting data  
   When a new patient submits an appointment request, both 'request_appointment_all' and 'request_appointment_new' fire, doubling the recorded conversion and understating true ad-attributed cost-per-acquisition by roughly half.

## Findings

### Critical (1)

#### `GTM007` EXAMPLECARE

*container · privacy · determined by rule*

19 of 19 tags have consentStatus NOT_SET — no tag in this container is gated on consent. Includes 4 custom HTML/image tag(s), which are the highest-risk category.

**Business impact (rank 3).** Every tag in the container — including the four custom HTML/image tags that can execute arbitrary code — loads without any consent gate, violating regulatory consent requirements and exposing the clinic to CCPA/state-privacy enforcement regardless of whether individual tags transmit data.

**Fix.** Configure Consent Mode and set additional consent checks on marketing tags.

<details><summary>Evidence</summary>

  - Tags without consent: 19
  - Total tags: 19
  - Ungated custom html: `StackAdapt Script`, `AccessiBe`, `cHTML - Transfer Query Parameters`, `CALLVENDOR Base Script & DNI`

</details>

### High (13)

#### `LLM001` StackAdapt Script

*tag · third party risk · determined by model judgment*

Injects the StackAdapt advertising pixel library (events.js) asynchronously, initializes a global saq() queue function, and immediately calls saq('ts', 'DEMOSTACKADAPTTOKEN000') to register a tracking session tied to this site's unique advertiser token on every page load. StackAdapt is a programmatic advertising/retargeting platform, not analytics — it exists to build audience profiles for ad targeting. Firing unconditionally on 'All Pages' with consent mode NOT_SET means every visitor's page views (including visits to condition-specific, treatment, or appointment pages) are sent to an ad-tech vendor before any consent decision, which on a healthcare site risks disclosing information reasonably inferable as related to a person's health condition or care-seeking behavior to a third party for advertising purposes.

**Business impact (rank 2).** StackAdapt fires unconditionally on every page, sending page views on condition-specific and treatment pages to an ad retargeting platform before any consent decision, which on a healthcare site risks disclosing health-inferred browsing behavior to a third-party ad vendor.

**Fix.** Gate this tag behind explicit, opt-in consent (e.g., Consent Mode 'ad_storage'/'ad_user_data' granted) before it fires, restrict firing on pages that could reveal specific conditions, treatments, or appointment types, and confirm with legal/compliance whether a Business Associate Agreement or de-identification approach is needed before sending any page-path data to StackAdapt.

<details><summary>Evidence</summary>

  - Category: advertising
  - Third party hosts: `tags.srv.stackadapt.com`
  - Data exposure: `Page URL and path of every page visited`, `Referrer URL`, `Browser/user-agent and device data collected implicitly by the script`, `IP address (implicit in any HTTP request)`, `StackAdapt-set cookie/device ID used to build an ad-targeting or retargeting profile`, `Site-specific advertiser token ('ts' parameter) linking browsing activity to this clinic's ad account`
  - Rationale: The tag loads a known third-party ad retargeting script and reports page-level browsing on every pageview with no consent gate, which is the exact unconditional-tracking-plus-advertising-vendor pattern cited in recent FTC and HHS OCR enforcement actions against health systems using pixels like Meta/Google ads tags. The site name/URL path visited becomes an implicit signal to an ad network, which is materially different in risk from the same tag on a non-health vertical.

</details>

#### `GTM009` Request Appointment Existing - GA4, Request Appointment All - GA4

*tag · data quality · determined by rule*

2 GA4 event tags fire on trigger 'Request Appointment Existing Trigger' and send to the same destination G-DEMO111111. Events ['request_appointment_all', 'request_appointment_existing'] are all recorded for a single user action, inflating conversion counts and double-counting any of them marked as a key event.

**Business impact (rank 4).** When a user submits an appointment request, both 'request_appointment_all' and 'request_appointment_existing' fire, artificially doubling the conversion count and making cost-per-acquisition look half as expensive as it really is.

**Fix.** Keep one canonical event; differentiate with an event parameter instead of a second tag.

<details><summary>Evidence</summary>

  - Tags: `Request Appointment Existing - GA4`, `Request Appointment All - GA4`
  - Events: `request_appointment_all`, `request_appointment_existing`
  - Destination: G-DEMO111111
  - Shared trigger: Request Appointment Existing Trigger

</details>

#### `GTM009` Request Appointment New Trigger - GA4, Request Appointment All - GA4

*tag · data quality · determined by rule*

2 GA4 event tags fire on trigger 'Request Appointment New Trigger' and send to the same destination G-DEMO111111. Events ['request_appointment_all', 'request_appointment_new'] are all recorded for a single user action, inflating conversion counts and double-counting any of them marked as a key event.

**Business impact (rank 5).** When a new patient submits an appointment request, both 'request_appointment_all' and 'request_appointment_new' fire, doubling the recorded conversion and understating true ad-attributed cost-per-acquisition by roughly half.

**Fix.** Keep one canonical event; differentiate with an event parameter instead of a second tag.

<details><summary>Evidence</summary>

  - Tags: `Request Appointment New Trigger - GA4`, `Request Appointment All - GA4`
  - Events: `request_appointment_all`, `request_appointment_new`
  - Destination: G-DEMO111111
  - Shared trigger: Request Appointment New Trigger

</details>

#### `GTM006` All Page Views - UA

*tag · deprecation · determined by rule*

Tag 'All Page Views - UA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 9).** Universal Analytics stopped processing hits in July 2023, so the 'All Page Views - UA' tag has collected zero data for over a year, making any reports relying on UA pageview numbers complete blanks.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 5
  - Tag type: ua

</details>

#### `GTM006` Click to Call - GA

*tag · deprecation · determined by rule*

Tag 'Click to Call - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 10).** The 'Click to Call - GA' Universal Analytics tag has collected zero click-to-call events since July 2023, leaving the clinic without visibility into phone-call conversions from their website.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 15
  - Tag type: ua

</details>

#### `GTM006` Click to Email - GA

*tag · deprecation · determined by rule*

Tag 'Click to Email - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 11).** The 'Click to Email - GA' Universal Analytics tag has collected zero email-click events since July 2023, creating a blind spot in email-driven lead tracking.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 16
  - Tag type: ua

</details>

#### `GTM006` Newsletter Signup - GA

*tag · deprecation · determined by rule*

Tag 'Newsletter Signup - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 12).** The 'Newsletter Signup - GA' Universal Analytics tag has collected zero newsletter signup events since July 2023, making newsletter conversion reporting show only GA4 data and creating inconsistency across reports.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 22
  - Tag type: ua

</details>

#### `GTM006` Request Appointment All - GA

*tag · deprecation · determined by rule*

Tag 'Request Appointment All - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 13).** The 'Request Appointment All - GA' Universal Analytics tag has collected zero appointment events since July 2023, causing any executive report pulling from the UA property to show zero conversions.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 24
  - Tag type: ua

</details>

#### `GTM006` Request Appointment Existing - GA

*tag · deprecation · determined by rule*

Tag 'Request Appointment Existing - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 14).** The 'Request Appointment Existing - GA' tag has collected zero existing-patient appointment events since July 2023, making UA-based patient-journey analysis for returning patients completely empty.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 18
  - Tag type: ua

</details>

#### `GTM006` Request Appointment New - GA

*tag · deprecation · determined by rule*

Tag 'Request Appointment New - GA' is a Universal Analytics tag. UA stopped processing hits on 2023-07-01; this tag adds page weight and collects nothing.

**Business impact (rank 15).** The 'Request Appointment New - GA' tag has collected zero new-patient appointment events since July 2023, creating a total data gap in new-patient acquisition reporting within the UA property.

**Fix.** Delete the tag once GA4 coverage for this event is confirmed.

<details><summary>Evidence</summary>

  - Tag id: 17
  - Tag type: ua

</details>

#### `GTM014` Sign up for our newsletter Trigger 1

*trigger · correctness · determined by rule*

Trigger 'Sign up for our newsletter Trigger 1' uses CSS selector '.submitted-message hs-main-font-element hs-form-11111111-2222-3333-4444-555555555555 hs-form-11111111-2222-3333-4444-555555555555_66666666-7777-8888-9999-000000000000'. The space-separated token(s) ['hs-main-font-element', 'hs-form-11111111-2222-3333-4444-555555555555', 'hs-form-11111111-2222-3333-4444-555555555555_66666666-7777-8888-9999-000000000000'] have no leading '.', so CSS reads them as descendant element types rather than classes. This selector matches nothing.

**Business impact (rank 16).** The newsletter signup trigger's CSS selector lacks dots before class names, so it matches nothing, silently failing to ever fire the newsletter conversion tag — the clinic sees zero newsletter signups in analytics.

**Fix.** Prefix each class with '.' and remove spaces: .submitted-message.hs-main-font-element.hs-form-11111111-2222-3333-4444-555555555555.hs-form-11111111-2222-3333-4444-555555555555_66666666-7777-8888-9999-000000000000

<details><summary>Evidence</summary>

  - Selector: .submitted-message hs-main-font-element hs-form-11111111-2222-3333-4444-555555555555 hs-form-11111111-2222-3333-4444-555555555555_66666666-7777-8888-9999-000000000000
  - Unprefixed tokens: `hs-main-font-element`, `hs-form-11111111-2222-3333-4444-555555555555`, `hs-form-11111111-2222-3333-4444-555555555555_66666666-7777-8888-9999-000000000000`

</details>

#### `GTM006` Google Analytics Settings

*variable · deprecation · determined by rule*

Variable 'Google Analytics Settings' holds Universal Analytics settings (UA-11111111-3), which no longer collect data.

**Business impact (rank 18).** The 'Google Analytics Settings' variable still references the defunct UA-11111111-3 property, adding unnecessary code weight and confusing auditors reviewing the container's analytics infrastructure.

**Fix.** Remove after the dependent UA tags are deleted.

<details><summary>Evidence</summary>

  - Variable id: 4
  - Tracking id: UA-11111111-3

</details>

#### `LLM002` EXAMPLECARE

*container · privacy · determined by model judgment*

The only confirmed cross-domain data movement involving a third-party (non-first-party) vendor is in 'cHTML - Transfer Query Parameters'. Its domainsToDecorate array explicitly includes 'hipaa-submit.formvendor.com' alongside the two first-party properties ('examplecare.com', 'info.examplecare.com'). Passing utm_* between the first-party pair is normal attribution behavior and not a finding per se. However, the same decorateUrl() function indiscriminately also appends these parameters — including gclid, a Google Ads click identifier that can be resolved back to a specific ad interaction and, via Google Ads account access, to identifiable user/campaign data — to links pointing at a vendor whose hostname itself advertises HIPAA-related form submission. This creates a mechanism by which an advertising click identifier travels into a regulated health-intake funnel's URL, where it could be logged by the vendor alongside health-related form content, enabling linkage between an identifiable ad click and a patient's health inquiry. This is a confirmed code-level mechanism (the vendor domain is hardcoded into the decoration list and gclid/utm/rsicampaignid are hardcoded into the queryParams list); whether PHI is actually logged downstream depends on the vendor's server-side handling, which is outside this container's visibility. The 'CALLVENDOR Base Script & DNI' snippet only exposes a configuration object (campaign-to-phone-number mapping) via window.RSI_DNI; no PII/PHI collection or transmission is evidenced in the code shown, so it is not scored as a confirmed leak. The cross_domain_linker entry only links two first-party subdomains, which the rules classify as normal attribution continuity, not a finding.

**Business impact (rank 19).** While no confirmed PHI leak was found from this container alone, the CALLVENDOR configuration object + the cross-domain query-parameter transfer create an un-auditable data pathway to a third-party form vendor that a privacy reviewer would flag as a compliance gap.

**Fix.** Remove 'hipaa-submit.formvendor.com' from the domainsToDecorate array, or if cross-domain attribution to that vendor is required for legitimate marketing measurement, strip gclid (and ideally all UTM/campaign params) before decorating links to that specific domain and confirm via a signed BAA that the vendor does not log or persist query-string values alongside any submitted health information. Separately, obtain and review the actual CALLVENDOR plugin code (not included in this container) to confirm whether it collects caller phone numbers or transcripts and where that data is transmitted, since window.RSI_DNI alone does not demonstrate a leak but is the entry point a fuller audit should follow.

<details><summary>Evidence</summary>

  - Identifiers at risk: identifier: gclid (Google Ads click identifier), status: confirmed, mechanism: In 'cHTML - Transfer Query Parameters', 'hipaa-submit.formvendor.com' is included in domainsToDecorate: `var domainsToDecorate = ['examplecare.com', 'hipaa-submit.formvendor.com', 'info.examplecare.com'];` and decorateUrl() reads `gclid` from the page URL (`var queryParams = [...,'gclid',...]`) and appends it to any outbound link whose href matches that domain: `links[linkIndex].href = decorateUrl(links[linkIndex].href);`; identifier: utm_source, utm_medium, utm_campaign, utm_content, utm_term, status: confirmed, mechanism: Same decorateUrl() logic collects these query params from window.location.search and appends them to links pointing at 'hipaa-submit.formvendor.com', a form-submission vendor whose name signals regulated (HIPAA) data handling.; identifier: rsicampaignid, status: confirmed, mechanism: Included in the same queryParams array and transferred by the identical decorateUrl mechanism to hipaa-submit.formvendor.com links.; identifier: Caller phone number / call identity, status: potential, mechanism: 'CALLVENDOR Base Script & DNI' exposes `window.RSI_DNI` with campaign-to-phone-number mappings for dynamic number insertion; the actual capture of caller PII would happen inside the CALLVENDOR plugin itself, which is not shown here, so this is not confirmed from the given code.
  - Destinations of concern: `hipaa-submit.formvendor.com`

</details>

### Medium (7)

#### `LLM001` cHTML - Transfer Query Parameters

*tag · third party risk · determined by model judgment*

The script scans every anchor tag on the page and, if its href contains one of three listed domains, appends UTM parameters (source/medium/campaign/content/term), gclid, and rsicampaignid pulled from the current page's URL onto that link's href. It does not make any network call itself — it only rewrites outbound link URLs so the destination site receives these parameters when the user clicks. The tag only fires when a UTM parameter is already present on the page and only decorates links to the three listed domains, so it is not an unconditional, always-firing tracker — but it also has no consent gate (NOT_SET) before attaching an advertising click ID (gclid) to a link pointing at what is named as a HIPAA-related form vendor. If that vendor's form or backend logs the incoming query string alongside a health inquiry or patient intake submission, this creates a linkage between a Google Ads click identifier and health-related activity, which is the exact pattern regulators have scrutinized in health-system marketing pixel cases.

**Business impact (rank 1).** The 'cHTML - Transfer Query Parameters' tag appends Google Ads click identifiers (gclid) to links going to 'hipaa-submit.formvendor.com', coupling an ad click ID with a health-intake funnel — precisely the pattern that has triggered health-privacy regulatory actions.

**Fix.** Remove hipaa-submit.formvendor.com from the domainsToDecorate list, or confirm with the vendor that gclid/UTM parameters are not logged, stored, or associated with any patient-identifying or health-inquiry data on their end. If cross-domain ad attribution to that vendor is required, gate the decoration behind an explicit advertising-consent check rather than firing unconditionally on NOT_SET consent.

<details><summary>Evidence</summary>

  - Category: advertising
  - Third party hosts: `examplecare.com (appears to be the clinic's own domain)`, `info.examplecare.com (appears to be a clinic subdomain)`, `hipaa-submit.formvendor.com (external form vendor, name suggests it handles HIPAA-related intake forms)`
  - Data exposure: `utm_source, utm_medium, utm_campaign, utm_content, utm_term values from the visitor's landing URL`, `gclid (Google Ads click identifier) from the visitor's landing URL`, `rsicampaignid value from the visitor's landing URL`, `Implicit exposure at click-time to the destination domain: referrer URL, IP address, and any cookies set for that domain, now bundled with the click identifiers above`
  - Rationale: The mechanism itself (cross-domain UTM/gclid passthrough) is a routine, legitimate analytics/attribution pattern and is not inherently high-risk when limited to first-party domains like examplecare.com. The risk is specific to the inclusion of hipaa-submit.formvendor.com in the decoration list combined with zero consent gating on an advertising identifier (gclid), which is an inference based on the domain name suggesting PHI-adjacent form submissions rather than confirmed vendor behavior.

</details>

#### `GTM010` All Page Views - GA4, GA4 - All EXAMPLEGROUP Properties - All Page Views

*tag · data quality · determined by rule*

2 GA4 configuration tags fire on the same trigger (All Pages), sending duplicate page_view hits to ['G-DEMO111111', 'G-DEMO222222'].

**Business impact (rank 6).** Two GA4 config tags send duplicate page_view hits on every page load, doubling reported session counts and inflating all per-page-view engagement metrics (bounce rate, time-on-page averages) in both reporting properties.

**Fix.** Confirm this is an intentional roll-up property; otherwise remove the duplicate.

<details><summary>Evidence</summary>

  - Tags: `All Page Views - GA4`, `GA4 - All EXAMPLEGROUP Properties - All Page Views`
  - Destinations: `G-DEMO111111`, `G-DEMO222222`

</details>

#### `GTM011` Request Appointment All / Request Appointment New Trigger

*trigger · data quality · determined by rule*

Triggers 'Request Appointment All' and 'Request Appointment New Trigger' use overlapping CONTAINS conditions ('thank-you' also matches 'thank-you-new'), so both fire on the same pageview.

**Business impact (rank 7).** The 'Request Appointment All' and 'Request Appointment New Trigger' both fire when a URL contains 'thank-you' or 'thank-you-new', causing every new-patient thank-you page to double-fire two sets of events, inflating new-patient conversion counts.

**Fix.** Use EQUALS or a regex anchor so the conditions are mutually exclusive.

<details><summary>Evidence</summary>

  - Broad match: thank-you
  - Narrow match: thank-you-new
  - Variables: `{{Page Path}}`, `{{Page URL}}`

</details>

#### `GTM011` Request Appointment Existing Trigger / Request Appointment All

*trigger · data quality · determined by rule*

Triggers 'Request Appointment Existing Trigger' and 'Request Appointment All' use overlapping CONTAINS conditions ('thank-you' also matches 'thank-you-existing'), so both fire on the same pageview.

**Business impact (rank 8).** The 'Request Appointment Existing Trigger' and 'Request Appointment All' both fire when a URL contains 'thank-you' or 'thank-you-existing', causing every existing-patient thank-you page to double-fire two sets of events, inflating existing-patient conversion counts.

**Fix.** Use EQUALS or a regex anchor so the conditions are mutually exclusive.

<details><summary>Evidence</summary>

  - Broad match: thank-you
  - Narrow match: thank-you-existing
  - Variables: `{{Page Path}}`, `{{Page URL}}`

</details>

#### `GTM013` CALLVENDOR Base Script & DNI

*tag · maintainability · determined by rule*

Custom HTML tag 'CALLVENDOR Base Script & DNI' hardcodes 1 identifier(s) that should be variables: phone number: 555-010-0000

**Business impact (rank 17).** The CALLVENDOR tag hardcodes a phone number (555-010-0000) directly into the custom HTML, requiring a container republish whenever that number changes and creating risk of incorrect number display if the code is copied elsewhere.

**Fix.** Move each value into a GTM variable so staging and production can differ.

<details><summary>Evidence</summary>

  - Tag id: 31
  - Hardcoded: `phone number: 555-010-0000`

</details>

#### `GTM001` Request Appointment All

*trigger · reference integrity · determined by rule*

Trigger 'Request Appointment All' (PAGEVIEW) is not referenced by any tag.

**Business impact (rank 23).** The 'Request Appointment All' trigger exists but is not attached to any tag, wasting a line in the trigger list and confusing anyone auditing which events are actually being tracked.

**Fix.** Delete the trigger, or attach the tag it was built for.

<details><summary>Evidence</summary>

  - Trigger id: 23
  - Trigger type: PAGEVIEW

</details>

#### `GTM001` Sign up for our newsletter Trigger 1

*trigger · reference integrity · determined by rule*

Trigger 'Sign up for our newsletter Trigger 1' (ELEMENT_VISIBILITY) is not referenced by any tag.

**Business impact (rank 24).** The 'Sign up for our newsletter Trigger 1' exists but is not attached to any tag, leaving an unused element-visibility trigger that adds noise to the trigger inventory.

**Fix.** Delete the trigger, or attach the tag it was built for.

<details><summary>Evidence</summary>

  - Trigger id: 19
  - Trigger type: ELEMENT_VISIBILITY

</details>

### Low (6)

#### `LLM001` CALLVENDOR Base Script & DNI

*tag · third party risk · determined by model judgment*

This tag only declares a global JavaScript object (window.RSI_DNI) containing configuration values: a clientId, a phone number to be replaced, and campaign-ID mappings keyed to UTM parameters (e.g., campaign=gbp-listing, campaign=gbp-appt, source=chatgpt.com) and organic/default fallbacks. It does not load any script, make any network request, or reference any external host in the code shown — it is a configuration object intended to be read by a separately-loaded CALLVENDOR dynamic-number-insertion (DNI) script. Firing on All Pages with consent NOT_SET is a real gap, but it is only consequential if a companion script actually sends data using this config — which is not shown here. Because this snippet itself performs no network activity, the immediate risk from this specific tag is low; the risk is contingent on the (unseen) CALLVENDOR loader script that consumes window.RSI_DNI.

**Business impact (rank 20).** The CALLVENDOR configuration object fires on all pages with no consent gate, which is a compliance gap if a companion loader script consumes it — but since no network request was shown, the immediate risk is operational ambiguity that requires investigation.

**Fix.** Locate and audit the actual CALLVENDOR loader/plugin script that reads window.RSI_DNI, since that script — not this one — will determine what data (page URL, referrer, campaign tag, swapped number, call metadata) is sent to CALLVENDOR's servers. Given the healthcare context, ensure that companion script is consent-gated before firing, since it is the mechanism that would associate a visitor's marketing-source/session data with an inbound call, not this configuration tag.

<details><summary>Evidence</summary>

  - Category: call_tracking
  - Data exposure: `None directly from this code — no fetch/XHR/script tag is present, so this snippet transmits nothing on its own.`, `The values it stages (UTM campaign/source strings, clientId, phone number to swap) become available in global scope for a companion CALLVENDOR script to read and presumably transmit, but that transmission is not visible in this tag.`
  - Rationale: The code sets a global variable with campaign/UTM-to-phone-number mappings but contains no script src, fetch, or XHR call, so no third-party host is contacted and no data leaves the page as a result of this tag alone. The mapped UTM values (e.g., 'gbp-appt', 'bing-listing') suggest this config feeds a call-tracking DNI script that will later swap displayed phone numbers and attribute inbound calls to marketing sources — a plausible inference, not something this snippet does itself.

</details>

#### `LLM001` AccessiBe

*tag · third party risk · determined by model judgment*

Injects the AccessiBe accessibility overlay by dynamically loading a remote script from acsbapp.com and initializing it with UI configuration (widget position, colors, trigger icon, mobile behavior). It renders a visible accessibility toolbar/widget on every page but does not read or transmit any page content, form fields, or health-related data in the code shown. The tag fires unconditionally on all pages with consent NOT_SET, meaning the third-party script loads and can set cookies before any consent decision is recorded; on a healthcare site this is a minor privacy-hygiene gap (undisclosed third-party data flow) rather than a PHI/HIPAA exposure, since the code does not pass page content, search terms, or visitor identifiers tied to health conditions to an ad or analytics network.

**Business impact (rank 21).** The AccessiBe accessibility overlay loads on every page with no consent gate, creating a minor privacy-hygiene gap since it can set cookies before any consent decision, though the code shown does not transmit health-related data.

**Fix.** Confirm with AccessiBe what data their script collects (cookies, IP logging, usage analytics) and add this tag to the site's cookie/privacy disclosure; consider gating it behind at least a 'necessary/functional' consent category rather than leaving consent NOT_SET, since it still contacts a third-party host on every pageview.

<details><summary>Evidence</summary>

  - Category: accessibility
  - Third party hosts: `acsbapp.com (accessibility widget vendor, AccessiBe)`
  - Data exposure: `Page URL and referrer (implicitly collected by any script load)`, `Client IP address (implicit, via HTTP request to acsbapp.com)`, `Browser/device metadata and language setting (language: 'en' passed explicitly)`, `Likely a vendor-set cookie/local identifier to persist accessibility preferences (not visible in this snippet but standard for such widgets)`
  - Rationale: This is a legitimate ADA/WCAG accessibility tool, not a tracking or advertising pixel, and the visible code only configures UI appearance and loads the vendor script — no explicit collection of health-related browsing behavior is present. The residual risk is procedural: an unconditioned, unconsented third-party script load on a healthcare domain, which is a compliance-hygiene issue rather than a PHI-disclosure risk.

</details>

#### `GTM012` Request Appointment All

*trigger · data quality · determined by rule*

Trigger 'Request Appointment All' matches 'thank-you' against {{Page URL}}, which includes protocol, hostname and query string. Sibling triggers in this container match the same style of value against {{Page Path}}.

**Business impact (rank 22).** The 'Request Appointment All' trigger matches against the full Page URL while sibling triggers use Page Path, creating a silent maintenance trap if a URL parameter accidentally contains 'thank-you' and triggers a false positive.

**Fix.** Standardize on {{Page Path}} for path matching to avoid query-string false positives.

<details><summary>Evidence</summary>

  - Match value: thank-you

</details>

#### `GTM015` Click to Call Trigger - GA4, Click to Email Trigger - GA4, Request Appointment New Trigger - GA4

*tag · hygiene · determined by rule*

3 tag(s) have 'Trigger' in the name, which describes the wrong entity type and misleads anyone scanning the tag list.

**Business impact (rank 25).** Three tags contain 'Trigger' in their names, misleading anyone scanning the tag list into thinking they are triggers rather than tags, which causes confusion during audits or migrations.

**Fix.** Rename to describe what the tag sends, not what fires it.

<details><summary>Evidence</summary>

  - Tags: `Click to Call Trigger - GA4`, `Click to Email Trigger - GA4`, `Request Appointment New Trigger - GA4`

</details>

#### `GTM015` EXAMPLECARE

*container · hygiene · determined by rule*

Tag names mix platform-suffix conventions: dash_suffix (13 tags); paren_suffix (1 tags). Bulk find/replace and naming-based filters will miss tags.

**Business impact (rank 26).** Mixed naming conventions (dash_suffix vs. parentheses) make it harder to bulk-update or filter tags by platform, increasing the chance of missing a tag during cleanup and adding minutes to every container review.

**Fix.** Standardize on the majority convention; 1 tag(s) deviate.

<details><summary>Evidence</summary>

  - Dash suffix: `All Page Views - GA4`, `All Page Views - UA`, `Click to Call Trigger - GA4`, `Click to Email Trigger - GA4`, `Request Appointment New Trigger - GA4`, `Request Appointment Existing - GA4`, `Click to Call - GA`, `Click to Email - GA`, `Request Appointment New - GA`, `Request Appointment Existing - GA`, `Newsletter Signup - GA`, `Request Appointment All - GA`
  - Paren suffix: `Newsletter Signup (GA4)`

</details>

#### `LLM003` EXAMPLECARE

*container · hygiene · determined by model judgment*

Naming coherence scored 3/5. The container leans toward purpose-first naming with a platform suffix separated by a hyphen with spaces. Over half the tags follow this pattern (e.g., 'All Page Views - GA4', 'Newsletter Signup - GA'). The score is 3 because while a dominant system exists, it is undermined by several legacy names, inconsistent trigger naming (platform suffixes on some triggers, none on others), and cryptic vendor tags that appear added without renaming. A new maintainer could predict most GA4/UA tag names but would be confused by 'CALLVENDOR', 'cHTML', 'AccessiBe', and the numbering on newsletter triggers.

**Business impact (rank 27).** Naming coherence scored only 3/5, leaving cryptic names like 'CALLVENDOR' and numbered trigger names that force a new maintainer to reverse-engineer tag purposes rather than understanding them from the label.

**Fix.** {Purpose/Entity} – {Platform} (e.g., 'All Page Views – GA4') for tags; for triggers: '{Triggered Condition} – {Trigger Type}' (e.g., 'Click on Phone Link – Click Trigger').

<details><summary>Evidence</summary>

  - Observed conventions: `Most tags use a purpose-first name, e.g. 'All Page Views', 'Click to Call', 'Newsletter Signup'.`, `Tools (GA4, UA, GA) are appended after a separator: hyphen, hyphen-space, or parentheses.`, `Legacy/system tags like 'StackAdapt Script', 'AccessiBe', or 'CALLVENDOR Base Script & DNI' follow no internal pattern.`, `Trigger names sometimes mirror tag names ('Click to Call Trigger'), sometimes describe condition and type ('DOM Ready - UTM on Page'), sometimes use arbitrary numbering ('Sign up for our newsletter Trigger 1').`
  - Violations: name: Click to Call Trigger - GA4, issue: The suffix '- GA4' on a trigger is inconsistent; triggers are not tool-specific in this container (other triggers lack platform suffixes)., suggested: Click to Call Trigger; name: Click to Email Trigger - GA4, issue: Same as above – platform suffix on a trigger where no other trigger has one., suggested: Click to Email Trigger; name: Request Appointment New Trigger - GA4, issue: Platform suffix on a trigger breaks the trigger naming pattern., suggested: Request Appointment New Trigger; name: cHTML - Transfer Query Parameters, issue: A tag name starting with a cryptic abbreviation ('cHTML') that is not used elsewhere, making its purpose opaque., suggested: Transfer Query Parameters; name: CALLVENDOR Base Script & DNI, issue: Uses ALL CAPS, ampersand, and vendor-specific shorthand that is not part of any other name pattern., suggested: CALLVENDOR Base Script – DNI

</details>

## How this audit was produced

**21 findings from deterministic rules** — 16 rules evaluated against the container's reference graph. These are proven from the export: a tag either has a trigger or it doesn't. No model was involved.

**6 findings from model judgment** — applied only to questions with no deterministic answer: third-party risk in the site's context, PII exposure through generic data-moving code, naming coherence, and business-impact ranking. Every such finding is labelled above.

| Model | Calls | Tokens | Cost |
|---|---:|---:|---:|
| `anthropic/claude-sonnet-5` | 5 | 20,218 | $0.1275 |
| `deepseek/deepseek-v4-flash` | 2 | 7,591 | $0.0015 |
| **Total** | **7** | **27,809** | **$0.1289** |

Schema violation rate: 0.0% (malformed structured output, retried).

## Limitations

This audit reads a static container export. It establishes what the container is configured to do, not what happens in a browser. Specifically, it cannot determine:

- Whether a tag actually fires, or fires more than once per page
- What the dataLayer contains at runtime, or what values reach each tag
- Whether a consent platform blocks tags before they load, independently of the container's own consent settings
- What a third-party vendor does with data after it leaves the page
- Anything in a container version other than the one exported

Confirming those requires live testing against the running site.
