# Owner Geolocation Annotation Policy v1

## Measurement target

Label the country explicitly supported by the owner’s **self-reported current GitHub profile evidence shown in the annotation pack**. This is not nationality, citizenship, legal residence, ethnicity, repository origin, or a claim about where work was performed.

Annotators must not search for the owner, inspect GitHub, use usernames, or consult resolver output. Only `raw_location`, the de-identified final `website_tld`, and `owner_type` shown in the blinded pack are permitted.

## Allowed labels

### `country`

Use when the permitted evidence supports exactly one ISO 3166-1 alpha-2 country.

Examples:

- `Berlin, Germany` → `DE`
- `Atlanta, GA` → `US`
- `Remote in Portugal` → `PT`
- `🇯🇵 Tokyo` → `JP`

### `multi-country`

Use when two or more countries are intentionally asserted and no single current base is identified.

Examples:

- `Berlin / NYC` → `DE`, `US`
- `France and Spain` → `FR`, `ES`

### `ambiguous`

Use when the text is geographic but supports more than one plausible country and the shown evidence cannot distinguish them.

Examples:

- `Georgia`
- `Cambridge`
- `San José`
- undiacritized Arabic `عمان` (Oman or Amman)

Possible country codes may be recorded when known, but are optional.

### `non-location`

Use for content that intentionally does not identify a terrestrial country.

Examples:

- `Remote`
- `The Internet`
- `Mars`
- jokes, slogans, contact details, or technology names without geographic evidence

### `insufficient`

Use when evidence is missing, corrupted, too vague, or cannot be interpreted under this policy.

Examples:

- empty location and no geographically meaningful website
- an unknown acronym without supporting context
- malformed or unreadable text

## Decision order

1. Identify explicit current-location language such as “based in,” “living in,” or a single unqualified place.
2. Record every intentionally asserted country. Do not silently select the first country in a list.
3. Use a subdivision or city only when its country is unambiguous from the shown evidence.
4. Treat a country flag as geographic evidence, but mark conflicting flag/text evidence `ambiguous`.
5. Treat `Remote, COUNTRY` and `Remote in COUNTRY` as that country; `Remote` alone is `non-location`.
6. A website ccTLD may corroborate other evidence. It must not establish a country by itself because personal and project domains are portable.
7. Organization labels follow the organization’s self-reported profile location, not incorporation jurisdiction or contributor locations.
8. Historical names may be mapped only when the present-day country is unambiguous and the text is being used as a location.
9. For disputed or cross-border places, use `ambiguous` unless the profile explicitly names an ISO country/territory represented by the allowed code set.
10. When evidence is not strong enough, abstain. Never infer from language, personal name, employer, technical interests, or presumed nationality.

## Certainty

- `certain`: the label follows directly from explicit evidence or an unambiguous place.
- `probable`: the interpretation is strong but requires a conventional abbreviation or contextual reading.
- `uncertain`: a policy-compliant choice was made but material uncertainty remains. Explain it in `rationale`.

## Recommended policy tags

Use concise tags to support error analysis:

- `flag`
- `country-name`
- `subdivision`
- `city`
- `native-script`
- `abbreviation`
- `multi-location`
- `remote`
- `contact-or-url`
- `fictional-or-joke`
- `disputed`
- `corrupt-text`
- `website-corroboration`

## Independence and adjudication

Two annotators label every case independently and remain blind to predictions and to each other. Exact agreements become provisional gold labels. Every disagreement is reviewed by a third adjudicator using this same policy. Policy changes require a new policy version and a new benchmark manifest hash.
