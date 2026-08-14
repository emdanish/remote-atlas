"""Jobicy jobLevel maps into source_level / intern stage."""

from app.collectors.jobicy import JobicyCollector


def test_jobicy_internship_level_maps_source_level():
    collector = JobicyCollector(client=None)
    job = collector._normalize(
        {
            "id": "1",
            "jobTitle": "Software Engineer Intern",
            "companyName": "Acme",
            "jobDescription": "Write Python services.",
            "jobGeo": "Remote",
            "jobIndustry": ["Software"],
            "jobType": "Internship",
            "jobLevel": "Internship",
            "url": "https://jobicy.com/jobs/1",
            "pubDate": "2026-08-01T00:00:00Z",
        }
    )
    assert job is not None
    assert job.source_level == "Internship"
    assert job.career_stage == "internship"


def test_jobicy_entry_level_maps_junior():
    collector = JobicyCollector(client=None)
    job = collector._normalize(
        {
            "id": "2",
            "jobTitle": "Backend Developer",
            "companyName": "Acme",
            "jobDescription": "Python APIs.",
            "jobGeo": "Remote",
            "jobIndustry": ["Software"],
            "jobType": "Full Time",
            "jobLevel": "Entry-Level",
            "url": "https://jobicy.com/jobs/2",
            "pubDate": "2026-08-01T00:00:00Z",
        }
    )
    assert job is not None
    assert job.source_level == "Entry-Level"
    assert job.career_stage == "junior"
