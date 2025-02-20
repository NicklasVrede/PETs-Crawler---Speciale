# Privacy Analysis Web Crawler

A sophisticated web crawler built with Playwright to analyze tracking behaviors across websites, comparing GDPR opt-outs versus Privacy-Enhancing Technologies (PETs).

## Project Requirements

### Core Functionality
- Non-headless browser operation to simulate real user behavior
- Automated GDPR consent handling via browser extensions
- Network request monitoring and analysis
- Cookie and storage tracking
- Support for Privacy-Enhancing Technologies (PETs)
- Link decoration and CNAME cloaking detection using existing databases
- Scalable data collection system

### Tracking Detection
The crawler must monitor and log:
- Network requests
- Cookies
- LocalStorage data
- Fingerprinting scripts
- Link decoration (fbclid, gclid, utm_parameters)
- CNAME cloaking attempts via WhoTracks.Me database

### Data Collection Scope
- Target: 100 websites
- Subpages per site: 20
- Data storage: JSON format

### Data Organization
data/
├── baseline/
│   └── {domain}.json
├── consent-o-matic/
│   ├── no_pets/
│   │   └── {domain}.json
│   ├── ublock/
│   │   └── {domain}.json
│   └── privacy_badger/
│       └── {domain}.json
├── ninja_cookie/
│   ├── no_pets/
│   │   └── {domain}.json
│   ├── ublock/
│   │   └── {domain}.json
│   └── privacy_badger/
│       └── {domain}.json
└── consent_manager/
    ├── no_pets/
    │   └── {domain}.json
    ├── ublock/
    │   └── {domain}.json
    └── privacy_badger/
        └── {domain}.json

### JSON Structure
Each {domain}.json contains:
json
{
"domain": "example.com",
"rank": 1,
"timestamp": "2024-01-01T12:00:00",
"pages": [
"https://example.com/page1",
"https://example.com/page2"
],
"requests": [
{
"url": "https://analytics.com/track",
"method": "GET",
"headers": {},
"timestamp": "2024-01-01T12:00:01",
"resource_type": "script"
}
],
"cookies": [
{
"name": "tracking_id",
"value": "123",
"domain": "example.com",
"expires": "2025-01-01T12:00:00"
}
],
"statistics": {
"total_requests": 100,
"request_types": {
"script": 20,
"image": 30
},
"total_cookies": 5,
"cookie_domains": {
"example.com": 3,
"analytics.com": 2
}
}
}