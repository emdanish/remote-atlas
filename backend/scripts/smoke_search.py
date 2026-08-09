import httpx

base = "http://127.0.0.1:8000"
with httpx.Client(timeout=30) as c:
    print("health", c.get(f"{base}/health").json())
    cases = [
        ("python remote", {"q": "python engineer", "workplace": "remote", "page_size": 5}),
        ("junior", {"q": "software engineer", "career_stage": "junior", "page_size": 5}),
        ("react skills", {"skills": "react,typescript", "page_size": 5}),
        ("lahore", {"city": "Lahore", "page_size": 5}),
        ("pakistan friendly", {"workplace": "remote", "pakistan_friendly": True, "page_size": 5}),
        ("careem/motive", {"q": "engineer", "page_size": 5, "source": "greenhouse"}),
    ]
    for label, params in cases:
        r = c.get(f"{base}/jobs/search", params=params).json()
        print(f"\n=== {label} total={r['total']} ===")
        for j in r["results"][:5]:
            print(
                f"- {j['title'][:70]} | {j['company_name']} | {j['source']} | "
                f"{j['workplace_type']} | {j['career_stage']} | apply={bool(j.get('apply_url'))}"
            )
        if r["results"]:
            detail = c.get(f"{base}/jobs/{r['results'][0]['id']}").json()
            print(f"  detail ok id={detail['id']} skills={detail.get('skills')[:5]}")
