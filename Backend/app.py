import os
import uuid

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from ai_engine import calculate_match
from auth import hash_password, login_required, verify_password
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "resumes")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Runs on every import (not just `python app.py`), so it also works
# under `flask run` or a WSGI server like gunicorn.
init_db()
if ADMIN_PASSWORD == "admin123":
    print(
        "⚠  Using the default admin password (admin/admin123). Set "
        "ADMIN_USERNAME / ADMIN_PASSWORD environment variables before "
        "deploying anywhere real."
    )


def _allowed_resume(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RESUME_EXTENSIONS


def _save_resume(file_storage):
    """Save an uploaded resume with a collision-proof name. Returns the
    stored filename, or None if no file was provided."""
    if not file_storage or not file_storage.filename:
        return None

    if not _allowed_resume(file_storage.filename):
        raise ValueError("Resume must be a PDF or Word document.")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
    return stored_name


def _parse_float(value, field_label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} must be a number.")


def _parse_int(value, field_label):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} must be a whole number.")


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- STUDENT LOGIN ----------------
@app.route("/student", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM students WHERE lower(email) = ?", (email,)
            ).fetchone()

        if user and verify_password(user["password"], password):
            session.clear()
            session["student_id"] = user["id"]
            session["student_name"] = user["name"]
            return redirect(url_for("student_dashboard"))

        flash("That email and password don't match our records.", "error")

    return render_template("student_login.html")


# ---------------- STUDENT REGISTER ----------------
@app.route("/student-register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        form = request.form
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        department = form.get("department", "").strip()
        skills = form.get("skills", "").strip()
        preferred_location = form.get("preferred_location", "").strip()

        try:
            cgpa = _parse_float(form.get("cgpa"), "CGPA")
            if not (0 <= cgpa <= 10):
                raise ValueError("CGPA must be between 0 and 10.")

            resume_filename = _save_resume(request.files.get("resume"))

            with get_db() as conn:
                existing = conn.execute(
                    "SELECT id FROM students WHERE lower(email) = ?", (email,)
                ).fetchone()
                if existing:
                    raise ValueError("An account with that email already exists.")

                conn.execute(
                    """
                    INSERT INTO students
                    (name, email, password, department, cgpa,
                     skills, preferred_location, resume_filename)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        hash_password(password),
                        department,
                        cgpa,
                        skills,
                        preferred_location,
                        resume_filename,
                    ),
                )

            flash("Registration successful. You can log in now.", "success")
            return redirect(url_for("student_login"))

        except ValueError as err:
            flash(str(err), "error")

    return render_template("student_register.html")


# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student-dashboard")
@login_required("student")
def student_dashboard():
    return render_template("student_dashboard.html", student_name=session.get("student_name"))


# ---------------- COMPANY REGISTER ----------------
@app.route("/company-register", methods=["GET", "POST"])
def company_register():
    if request.method == "POST":
        form = request.form
        company_name = form.get("company_name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        industry = form.get("industry", "").strip()
        internship_role = form.get("internship_role", "").strip()
        required_skills = form.get("required_skills", "").strip()
        location = form.get("location", "").strip()

        try:
            minimum_cgpa = _parse_float(form.get("minimum_cgpa"), "Minimum CGPA")
            vacancies = _parse_int(form.get("vacancies"), "Vacancies")

            with get_db() as conn:
                existing = conn.execute(
                    "SELECT id FROM companies WHERE lower(email) = ?", (email,)
                ).fetchone()
                if existing:
                    raise ValueError("An account with that email already exists.")

                conn.execute(
                    """
                    INSERT INTO companies
                    (company_name, email, password, industry, location,
                     required_skills, minimum_cgpa, internship_role, vacancies)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_name,
                        email,
                        hash_password(password),
                        industry,
                        location,
                        required_skills,
                        minimum_cgpa,
                        internship_role,
                        vacancies,
                    ),
                )

            flash("Company registration successful. You can log in now.", "success")
            return redirect(url_for("company_login"))

        except ValueError as err:
            flash(str(err), "error")

    return render_template("company_register.html")


# ---------------- COMPANY LOGIN ----------------
@app.route("/company", methods=["GET", "POST"])
def company_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            company = conn.execute(
                "SELECT * FROM companies WHERE lower(email) = ?", (email,)
            ).fetchone()

        if company and verify_password(company["password"], password):
            session.clear()
            session["company_id"] = company["id"]
            session["company_name"] = company["company_name"]
            return redirect(url_for("company_dashboard"))

        flash("That email and password don't match our records.", "error")

    return render_template("company_login.html")


# ---------------- COMPANY DASHBOARD ----------------
@app.route("/company-dashboard")
@login_required("company")
def company_dashboard():
    return render_template("company_dashboard.html", company_name=session.get("company_name"))


# ---------------- POST INTERNSHIP ----------------
@app.route("/post-internship", methods=["GET", "POST"])
@login_required("company")
def post_internship():
    if request.method == "POST":
        form = request.form
        internship_title = form.get("internship_title", "").strip()
        role = form.get("role", "").strip()
        required_skills = form.get("required_skills", "").strip()
        location = form.get("location", "").strip()

        try:
            minimum_cgpa = _parse_float(form.get("minimum_cgpa"), "Minimum CGPA")
            vacancies = _parse_int(form.get("vacancies"), "Vacancies")

            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO internships
                    (company_id, company_name, internship_title, role,
                     required_skills, minimum_cgpa, location, vacancies)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session["company_id"],
                        session["company_name"],
                        internship_title,
                        role,
                        required_skills,
                        minimum_cgpa,
                        location,
                        vacancies,
                    ),
                )

            flash("Internship posted successfully.", "success")
            return redirect(url_for("internships"))

        except ValueError as err:
            flash(str(err), "error")

    return render_template("internship_post.html")


# ---------------- VIEW INTERNSHIPS ----------------
@app.route("/internships")
def internships():
    search = request.args.get("search", "").strip()

    with get_db() as conn:
        if search:
            like = f"%{search}%"
            rows = conn.execute(
                """
                SELECT * FROM internships
                WHERE company_name LIKE ? OR internship_title LIKE ? OR role LIKE ?
                ORDER BY created_at DESC
                """,
                (like, like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM internships ORDER BY created_at DESC"
            ).fetchall()

        scores_by_id = {}
        if session.get("student_id"):
            student = conn.execute(
                "SELECT * FROM students WHERE id = ?", (session["student_id"],)
            ).fetchone()
            if student:
                for row in rows:
                    scores_by_id[row["id"]] = calculate_match(student, row)["score"]

    return render_template(
        "internship_list.html",
        internships=rows,
        search=search,
        current_company_id=session.get("company_id"),
        scores_by_id=scores_by_id,
    )


# ---------------- AI MATCHING (current logged-in student) ----------------
@app.route("/student-matches")
@login_required("student")
def student_matches():
    with get_db() as conn:
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?", (session["student_id"],)
        ).fetchone()
        internship_rows = conn.execute("SELECT * FROM internships").fetchall()

    matches = []
    for internship in internship_rows:
        result = calculate_match(student, internship)
        matches.append({
            "company": internship["company_name"],
            "title": internship["internship_title"],
            "role": internship["role"],
            "location": internship["location"],
            "score": result["score"],
            "reasons": result["reasons"],
        })

    matches.sort(key=lambda m: m["score"], reverse=True)

    return render_template("student_matches.html", matches=matches)


# ---------------- VIEW STUDENTS (admin) ----------------
@app.route("/students")
@login_required("admin")
def students():
    search = request.args.get("search", "").strip()

    with get_db() as conn:
        if search:
            like = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM students WHERE name LIKE ? OR department LIKE ?",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM students").fetchall()

    return render_template("students.html", students=rows, search=search)


# ---------------- VIEW COMPANIES (admin) ----------------
@app.route("/companies")
@login_required("admin")
def companies():
    search = request.args.get("search", "").strip()

    with get_db() as conn:
        if search:
            like = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM companies WHERE company_name LIKE ? OR industry LIKE ?",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM companies").fetchall()

    return render_template("companies.html", companies=rows, search=search)


# ---------------- AI ALLOCATION REPORT (admin) ----------------
@app.route("/allocation-report")
@login_required("admin")
def allocation_report():
    with get_db() as conn:
        student_rows = conn.execute("SELECT * FROM students").fetchall()
        internship_rows = conn.execute("SELECT * FROM internships").fetchall()

    results = []
    for student in student_rows:
        best = {"score": -1, "company": "—", "role": "—"}
        for internship in internship_rows:
            result = calculate_match(student, internship)
            if result["score"] > best["score"]:
                best = {
                    "score": result["score"],
                    "company": internship["company_name"],
                    "role": internship["role"],
                }
        results.append({
            "student": student["name"],
            "company": best["company"],
            "role": best["role"],
            "score": max(best["score"], 0),
        })

    results.sort(key=lambda r: r["score"], reverse=True)

    return render_template("allocation_report.html", results=results)


# ---------------- DELETE INTERNSHIP ----------------
@app.route("/delete-internship/<int:internship_id>", methods=["POST"])
def delete_internship(internship_id):
    if not (session.get("company_id") or session.get("is_admin")):
        flash("Please log in to do that.", "error")
        return redirect(url_for("internships"))

    with get_db() as conn:
        internship = conn.execute(
            "SELECT * FROM internships WHERE id = ?", (internship_id,)
        ).fetchone()

        if not internship:
            flash("That internship no longer exists.", "error")
            return redirect(url_for("internships"))

        is_owner = internship["company_id"] == session.get("company_id")
        if not (is_owner or session.get("is_admin")):
            flash("You can only delete internships your own company posted.", "error")
            return redirect(url_for("internships"))

        conn.execute("DELETE FROM internships WHERE id = ?", (internship_id,))

    flash("Internship deleted.", "success")
    return redirect(url_for("internships"))


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    with get_db() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        total_internships = conn.execute("SELECT COUNT(*) FROM internships").fetchone()[0]

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_companies=total_companies,
        total_internships=total_internships,
    )


# ---------------- LOGOUT (shared) ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("home"))


# ---------------- ERROR HANDLERS ----------------
@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def too_large(_error):
    flash("That file is too large (5 MB max).", "error")
    return redirect(request.referrer or url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
