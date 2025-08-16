from biomni.tool.database import query_clinicaltrials
# Fetch a small page of studies for a simple demo (no API key needed)
res = query_clinicaltrials(term="type 2 diabetes", page_size=3, max_pages=1, verbose=True)

studies = (res.get("result") or {}).get("studies", [])
for s in studies:
    proto = (s.get("protocolSection") or {})
    idm = (proto.get("identificationModule") or {})
    status_module = (proto.get("statusModule") or {})
    nct_id = idm.get("nctId")
    title = idm.get("officialTitle") or idm.get("briefTitle")
    status = status_module.get("overallStatus")
    url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "N/A"

    print(f"Title:  {title}")
    print(f"Status: {status}")
    print(f"URL:    {url}")
    print("-" * 60)