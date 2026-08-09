import httpx

base = "http://127.0.0.1:8000"
email = "demo@remoteatlas.dev"
password = "testpass123"

with httpx.Client(timeout=30) as c:
    print("health", c.get(f"{base}/health").json())
    # register or login
    r = c.post(f"{base}/auth/register", json={"email": email, "password": password, "full_name": "Demo User"})
    if r.status_code >= 400:
        r = c.post(f"{base}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    token = r.json()["access_token"]
    print("token ok")

    me = c.get(f"{base}/auth/me", headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    print("me", me.json()["email"])

    prof = c.put(
        f"{base}/auth/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "experience_level": "junior",
            "skills": ["python", "react"],
            "technologies": ["fastapi", "next.js"],
            "remote_preference": "remote",
            "pakistan_friendly": True,
            "headline": "Junior software engineer",
        },
    )
    prof.raise_for_status()
    print("profile", prof.json()["headline"])

    search = c.get(f"{base}/jobs/search", params={"q": "python", "workplace": "remote", "page_size": 3})
    search.raise_for_status()
    data = search.json()
    print("search total", data["total"])
    if data["results"]:
        job_id = data["results"][0]["id"]
        saved = c.post(
            f"{base}/saved-jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={"job_id": job_id},
        )
        saved.raise_for_status()
        print("saved", saved.json()["job_title"][:60])
        listed = c.get(f"{base}/saved-jobs", headers={"Authorization": f"Bearer {token}"})
        listed.raise_for_status()
        print("saved count", len(listed.json()))
print("OK")
