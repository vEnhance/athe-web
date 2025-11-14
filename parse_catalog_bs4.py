#!/usr/bin/env python3
"""Parse catalog HTML files and generate fixtures/courses.json using BeautifulSoup"""

import json
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup


def parse_html_file(file_path):
    """Parse a single HTML catalog file"""
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Extract semester name
    semester_name_div = soup.find("div", class_="catnav-curr")
    semester_name = semester_name_div.get_text(strip=True) if semester_name_div else None

    # Extract semester dates
    session_time_div = soup.find("div", class_="session-time")
    semester_dates = None
    if session_time_div:
        date_text = session_time_div.find("i")
        if date_text:
            semester_dates = date_text.get_text(strip=True)
            semester_dates = semester_dates.replace("Held ", "").replace(
                "Currently being held ", ""
            )

    # Extract courses
    courses = []
    course_divs = soup.find_all("div", class_="course", recursive=True)
    for course_div in course_divs:
        # Get course title
        title_elem = course_div.find("h3", class_="course-title")
        if not title_elem:
            continue
        course_name = title_elem.get_text(strip=True)

        # Get instructor
        instructor_elem = course_div.find("a", class_="course-teach")
        instructor = ""
        if instructor_elem:
            instructor = (
                instructor_elem.get_text(strip=True).replace("Instructor:", "").strip()
            )

        # Get description (all course-description paragraphs)
        description_parts = []
        desc_paragraphs = course_div.find_all("p", class_="course-description")
        for p in desc_paragraphs:
            text = p.get_text(strip=True)
            # Skip difficulty markers
            if not text.startswith("Difficulty:"):
                description_parts.append(text)
        description = "\n\n".join(description_parts)

        # Get lessons
        lessons = []
        lesson_paragraphs = course_div.find_all("p", class_="course-sched-text")
        for p in lesson_paragraphs:
            lesson_text = p.get_text(strip=True)
            # Clean up spacing
            lesson_text = re.sub(r"\s+", " ", lesson_text)
            lessons.append(lesson_text)

        courses.append(
            {
                "name": course_name,
                "instructor": instructor,
                "description": description,
                "lessons": lessons,
            }
        )

    return {
        "semester_name": semester_name,
        "semester_dates": semester_dates,
        "courses": courses,
    }


def parse_dates(date_str):
    """Parse date strings like 'March 6th, 2021—May 29th, 2021' or 'February 10th-May 18th, 2024'"""
    if not date_str:
        return None, None

    # Handle "Mid-Month through Mid-Month" format
    mid_match = re.match(r"Mid-(\w+)\s+through\s+Mid-(\w+),\s+(\d{4})", date_str)
    if mid_match:
        start_month = mid_match.group(1)
        end_month = mid_match.group(2)
        year = mid_match.group(3)
        # Use 15th as "mid" month
        start_date = datetime.strptime(f"{start_month} 15, {year}", "%B %d, %Y")
        end_date = datetime.strptime(f"{end_month} 15, {year}", "%B %d, %Y")
        return start_date, end_date

    # Remove ordinal suffixes (st, nd, rd, th)
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

    # Split on em dash, en dash, or hyphen (with or without spaces), or "through"
    parts = re.split(r"\s*(?:[—–\-]|through)\s*", date_str)
    if len(parts) != 2:
        return None, None

    start_str = parts[0].strip()
    end_str = parts[1].strip()

    # Extract year from end date if not in start date
    end_year_match = re.search(r", (\d{4})", end_str)
    if end_year_match:
        end_year = end_year_match.group(1)
        # If start date doesn't have a year, add it
        if ", " not in start_str:
            start_str = f"{start_str}, {end_year}"

    try:
        # Try to parse start date
        start_date = datetime.strptime(start_str, "%B %d, %Y")
    except ValueError as e:
        print(f"    Error parsing start date '{start_str}': {e}")
        return None, None

    try:
        # Try to parse end date
        end_date = datetime.strptime(end_str, "%B %d, %Y")
    except ValueError as e:
        print(f"    Error parsing end date '{end_str}': {e}")
        return None, None

    return start_date, end_date


def create_slug(semester_name):
    """Create a slug from semester name"""
    # Extract season and year
    match = re.search(r"(Spring|Fall)\s+Session\s+(\d{4})", semester_name)
    if match:
        season = match.group(1).lower()
        year = match.group(2)[-2:]  # Last 2 digits
        return f"{season}-{year}"
    return semester_name.lower().replace(" ", "-")


def load_staff_mapping():
    """Load staff name to PK mapping from staff-snapshot-fa25.json"""
    staff_file = Path("fixtures/staff-snapshot-fa25.json")
    with open(staff_file, "r", encoding="utf-8") as f:
        staff_data = json.load(f)

    mapping = {}
    for entry in staff_data:
        display_name = entry["fields"]["display_name"]
        pk = entry["pk"]
        mapping[display_name] = pk

    return mapping


def main():
    fixtures_dir = Path("fixtures")
    html_files = [
        "spring-21.html",
        "fall-21.html",
        "spring-22.html",
        "catalog-1.html",
        "catalog-2.html",
        "catalog-3.html",
        "catalog-4.html",
        "catalog-5.html",
        "catalog-6.html",
        "catalog-7.html",
    ]

    staff_mapping = load_staff_mapping()
    print(f"Loaded {len(staff_mapping)} staff members")

    all_data = []
    semester_pk = 1
    course_pk = 1

    for html_file in html_files:
        file_path = fixtures_dir / html_file
        if not file_path.exists():
            print(f"Warning: {html_file} not found")
            continue

        print(f"Parsing {html_file}...")
        data = parse_html_file(file_path)

        print(
            f"  Found: {data['semester_name']}, dates: {data['semester_dates']}, courses: {len(data['courses'])}"
        )

        # Create semester fixture
        slug = (
            create_slug(data["semester_name"]) if data["semester_name"] else None
        )
        start_date, end_date = parse_dates(data["semester_dates"])

        if start_date and end_date and data["semester_name"]:
            semester_fixture = {
                "model": "courses.semester",
                "pk": semester_pk,
                "fields": {
                    "name": data["semester_name"],
                    "slug": slug,
                    "start_date": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "end_date": end_date.strftime("%Y-%m-%dT23:59:59Z"),
                },
            }
            all_data.append(semester_fixture)
            print(f"  Semester: {data['semester_name']} ({slug})")

            # Create course fixtures
            for course in data["courses"]:
                instructor_name = course["instructor"]
                instructor_pk = staff_mapping.get(instructor_name)

                if not instructor_pk:
                    print(f"    Warning: No staff match for '{instructor_name}'")

                # Join lessons with newlines
                lesson_plan = "\n".join(course["lessons"])

                course_fixture = {
                    "model": "courses.course",
                    "pk": course_pk,
                    "fields": {
                        "name": course["name"],
                        "description": course["description"],
                        "semester": semester_pk,
                        "instructor": instructor_pk,
                        "difficulty": "",
                        "lesson_plan": lesson_plan,
                    },
                }
                all_data.append(course_fixture)
                print(
                    f"    Course: {course['name']} - {instructor_name} ({len(course['lessons'])} lessons)"
                )
                course_pk += 1

            semester_pk += 1

    # Write output
    output_file = fixtures_dir / "courses.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated {output_file} with {len(all_data)} fixtures")
    print(f"  {semester_pk - 1} semesters")
    print(f"  {course_pk - 1} courses")


if __name__ == "__main__":
    main()
