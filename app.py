from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
import pytz
import re
import requests
from sqlalchemy import JSON
import random

app = Flask(__name__)
app.secret_key = 'smartcv_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartcv.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/cv'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
mail = Mail(app)
PISTON_API_URL = "https://emkc.org/api/v2/piston/execute"

# ------------------- Models -------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80))
    phone = db.Column(db.String(80))
    education = db.Column(db.String(80))
    skills = db.Column(db.String(80))
    cv_path = db.Column(db.String(200))
    company_name = db.Column(db.String(80))
    industry = db.Column(db.String(80))
    role = db.Column(db.String(20))  # student/company/admin

class Job(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    cname = db.Column(db.String(100))
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    required_skills = db.Column(db.Text)  # A comma-separated list of required skills
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(pytz.timezone('Asia/Kolkata')))
    threshold_scores = db.Column(JSON)  # Store the threshold score per skill as JSON

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.threshold_scores:
            self.threshold_scores = {}  # Initialize empty dictionary if not set

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    application_date = db.Column(db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(pytz.timezone('Asia/Kolkata')))
    status = db.Column(db.String(50), default="Under Review")

    # Add the relationship to easily access the student object from an application
    student = db.relationship('User', backref='applications')  # Link to student
    job = db.relationship('Job', backref='applications')  # Link to job


class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    skill = db.Column(db.String(100))
    score = db.Column(db.Integer)
    test_type = db.Column(db.String(50))  # 'hard' or 'soft'
    test_date = db.Column(db.DateTime, default=lambda: datetime.now(pytz.utc).astimezone(pytz.timezone('Asia/Kolkata')))

@app.before_request
def setup():
    db.create_all()
    if not User.query.filter_by(email='admin@gmail.com').first():
        db.session.add(User(name='Admin', email='admin@gmail.com', password='admin123', role='admin'))
        db.session.commit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/run_code', methods=['POST'])
def run_code():
    data = request.get_json()
    language = data.get('language')
    code = data.get('code')

    lang_mapping = {
        'python': 'python', 'java': 'java', 'javascript': 'js', 'js': 'js',
        'c++': 'cpp', 'cpp': 'cpp', 'c#': 'csharp', 'csharp': 'csharp', 'sql': 'sql'
    }
    api_lang = lang_mapping.get(language.lower(), language.lower())

    try:
        response = requests.post(PISTON_API_URL, json={
            "language": api_lang,
            "version": "*",
            "files": [{"name": f"main.{api_lang}", "content": code}],
            "stdin": "", "args": [],
            "compile_timeout": 10000,
            "run_timeout": 5000,
            "compile_memory_limit": -1,
            "run_memory_limit": -1
        })

        if response.ok:
            result = response.json()["run"]
            return {
                "output": result.get("output", ""),
                "error": result.get("stderr", "") if result.get("code", 0) != 0 else ""
            }
        else:
            return {"output": "", "error": f"Execution failed: {response.text}"}, 500

    except Exception as e:
        return {"output": "", "error": str(e)}, 500

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'GET':
        print("Login GET triggered")
        session.clear()  # Logs them out
        return render_template('login.html')

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()

        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name  # Optional
            flash("Login successful!", "success")
            return redirect('/dashboard')
        else:
            flash("Invalid credentials", "error")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        file = request.files.get('cv_file')
        filename = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filename = os.path.relpath(filepath, 'static').replace('\\', '/')

        if User.query.filter_by(email=data['email']).first():
            return render_template('register.html', error="Email already exists")

        new_user = User(
            name=data['name'],
            email=data['email'],
            password=data['password'],
            education=data['education'],
            skills=data['skills'],
            phone=data['phone'],
            role=data['role'],
            company_name=data.get('company_name'),
            industry=data.get('industry'),
            cv_path=filename
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if user.role == 'student':
        return render_template('student_dashboard.html', user=user)

    elif user.role == 'company':
        if request.method == 'POST':
            cname = request.form["cname"]
            title = request.form['title']
            description = request.form['description']
            skills = request.form['skills']
            threshold_scores = request.form['threshold_scores']  # New field for threshold score
            job = Job(cname=cname,title=title, description=description, required_skills=skills, company_id=user.id,
                      threshold_scores=threshold_scores)
            db.session.add(job)
            db.session.commit()
            return redirect('/dashboard')

        # Fetch jobs posted by the company and the applications for each job
        jobs = Job.query.filter_by(company_id=user.id).order_by(Job.id.desc()).all()

        # Get applications for each job
        applications = {}
        for job in jobs:
            applications[job.id] = Application.query.filter_by(job_id=job.id).all()

        return render_template('company_dashboard.html', user=user, jobs=jobs, applications=applications)

    elif user.role == 'admin':
        users = User.query.all()
        jobs = Job.query.all()
        applications = Application.query.all()
        return render_template('admin_dashboard.html', users=users, jobs=jobs, applications=applications)

    return redirect('/')

@app.route('/recommendations')
def view_recommendations():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    if not user.skills:
        return render_template('recommendations.html', user=user, jobs=[])

    user_skills = [skill.strip().lower() for skill in user.skills.split(',')]
    matching_jobs = []
    all_jobs = Job.query.all()
    for job in all_jobs:
        job_skills = [skill.strip().lower() for skill in job.required_skills.split(',')]
        if any(skill in job_skills for skill in user_skills):
            matching_jobs.append(job)
    # Fetch the jobs posted by the companies
    # jobs = Job.query.all()  # You can also add filters to show relevant jobs based on student skills
    applied_job_ids = {
        app.job_id for app in Application.query.filter_by(student_id=user.id).all()
    }

    return render_template('recommendations.html', user=user, jobs=matching_jobs, applied_job_ids=applied_job_ids)

@app.route('/apply_job/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    job = Job.query.get(job_id)
    existing_application = Application.query.filter_by(student_id=user.id, job_id=job.id).first()

    if existing_application:
        return render_template('apply_job.html', job=job, already_applied=True)

    if request.method == 'POST':
        # Handle the application process here
        application = Application(
            student_id=user.id,
            job_id=job.id,
            application_date=datetime.utcnow(),
            status="Under Review"
        )
        db.session.add(application)
        db.session.commit()
        return redirect('/recommendations')  # Redirect after application submission

    return render_template('apply_job.html', job=job, already_applied=False)

@app.route('/update_application/<int:application_id>', methods=['GET', 'POST'])
def update_application(application_id):
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    application = Application.query.get(application_id)

    # Ensure the company is only updating their own applications
    if application.job.company_id != user.id:
        return redirect('/dashboard')

    if request.method == 'POST':
        status = request.form['status']
        application.status = status
        db.session.commit()
        return redirect('/dashboard')

    return render_template('update_application.html', application=application)

@app.route('/profile/<int:student_id>')
def student_profile(student_id):
    # Fetch the student user by id
    student = User.query.get_or_404(student_id)

    # Fetch test results for the student
    test_scores = TestResult.query.filter_by(student_id=student.id).all()
    score_by_skill = {}
    for result in test_scores:
        if result.skill not in score_by_skill:
            score_by_skill[result.skill] = 0
        score_by_skill[result.skill] += result.score

    # Render the student's profile page with all the data
    return render_template('profile.html',user=User, student=student, test_scores=score_by_skill.items())

@app.route('/coding-test', methods=['GET', 'POST'])
def coding_test():
    if 'user_id' not in session:
        return redirect('/login')

    selected_skill = request.args.get('skill')
    if not selected_skill:
        return redirect(url_for('select_skill'))

    skill_problems = {
        'python': [
            {"problem": "Write a Python function to check if a number is prime."},
            {"problem": "Write a Python program to reverse a string."},
            {"problem": "Write a Python function to return the factorial of a number."},
            {"problem": "Write a Python program to find the largest number in a list."},
            {"problem": "Write a Python function to check if a string is a palindrome."},
            {"problem": "Write a Python function to count vowels in a string."},
            {"problem": "Write a Python function to calculate the sum of digits of a number."},
            {"problem": "Write a Python function to check if a number is even or odd."},
            {"problem": "Write a Python function to generate the Fibonacci sequence up to n terms."},
            {"problem": "Write a Python program to count the frequency of characters in a string."},
            {"problem": "Write a Python function to remove duplicates from a list."},
            {"problem": "Write a Python program to find the GCD of two numbers."},
            {"problem": "Write a Python function to find the second largest number in a list."},
            {"problem": "Write a Python program to check if a year is a leap year."},
            {"problem": "Write a Python function to convert Celsius to Fahrenheit."},
            {"problem": "Write a Python function to find the length of a list without using len()."},
            {"problem": "Write a Python function to merge two dictionaries."},
            {"problem": "Write a Python function to find all even numbers in a list."},
            {"problem": "Write a Python function to check if a list is sorted."},
            {"problem": "Write a Python program to find common elements in two lists."}
        ],
        'java': [
            {"problem": "Write a Java method to check if a number is prime."},
            {"problem": "Write a Java program to reverse a string."},
            {"problem": "Write a Java method to calculate factorial of a number."},
            {"problem": "Write a Java method to find the largest number in an array."},
            {"problem": "Write a Java method to check if a string is a palindrome."},
            {"problem": "Write a Java method to count vowels in a string."},
            {"problem": "Write a Java program to sum the digits of a number."},
            {"problem": "Write a Java method to check if a number is even or odd."},
            {"problem": "Write a Java program to generate the Fibonacci sequence up to n terms."},
            {"problem": "Write a Java program to count character frequency in a string."},
            {"problem": "Write a Java method to remove duplicates from an array."},
            {"problem": "Write a Java method to find the GCD of two numbers."},
            {"problem": "Write a Java method to find the second largest number in an array."},
            {"problem": "Write a Java program to check if a year is a leap year."},
            {"problem": "Write a Java method to convert Celsius to Fahrenheit."},
            {"problem": "Write a Java method to find length of an array without using length property."},
            {"problem": "Write a Java method to merge two arrays."},
            {"problem": "Write a Java method to extract all even numbers from an array."},
            {"problem": "Write a Java method to check if an array is sorted."},
            {"problem": "Write a Java program to find common elements in two arrays."}
        ],
        'javascript': [
            {"problem": "Write a JavaScript function to check if a number is prime."},
            {"problem": "Write a JavaScript function to reverse a string."},
            {"problem": "Write a JavaScript function to calculate factorial of a number."},
            {"problem": "Write a JavaScript function to check if a string is a palindrome."},
            {"problem": "Write a JavaScript function to find the largest number in an array."},
            {"problem": "Write a JavaScript function to count vowels in a string."},
            {"problem": "Write a JavaScript function to sum the digits of a number."},
            {"problem": "Write a JavaScript function to check if a number is even or odd."},
            {"problem": "Write a JavaScript function to generate Fibonacci series up to n terms."},
            {"problem": "Write a JavaScript function to find the GCD of two numbers."},
            {"problem": "Write a JavaScript function to find the second largest number in an array."},
            {"problem": "Write a JavaScript function to check if a year is a leap year."},
            {"problem": "Write a JavaScript function to convert Celsius to Fahrenheit."},
            {"problem": "Write a JavaScript function to remove duplicates from an array."},
            {"problem": "Write a JavaScript function to count character frequency in a string."},
            {"problem": "Write a JavaScript function to find the sum of all even numbers in an array."},
            {"problem": "Write a JavaScript function to check if an array is sorted."},
            {"problem": "Write a JavaScript function to merge two arrays."},
            {"problem": "Write a JavaScript function to return the longest word in a string."},
            {"problem": "Write a JavaScript function to capitalize the first letter of each word in a sentence."}
        ],
        'sql': [
            {"problem": "Write a SQL query to fetch the top 5 highest salaries from an employee table."},
            {"problem": "Write a SQL query to find the second highest salary from an employee table."}
        ],
        'c++': [
            {"problem": "Write a C++ function to check if a number is prime."},
            {"problem": "Write a C++ function to find the factorial of a number using recursion."},
            {"problem": "Write a C++ program to reverse a given string."},
            {"problem": "Write a C++ program to check if a string is a palindrome."},
            {"problem": "Write a C++ program to find the GCD of two numbers."},
            {"problem": "Write a C++ program to find the maximum of three numbers."},
            {"problem": "Write a C++ program to print the Fibonacci series up to n terms."},
            {"problem": "Write a C++ function to count vowels in a string."},
            {"problem": "Write a C++ program to sort an array using bubble sort."},
            {"problem": "Write a C++ program to find the sum of digits of a number."},
            {"problem": "Write a C++ program to swap two numbers without using a third variable."},
            {"problem": "Write a C++ program to check whether a number is even or odd."},
            {"problem": "Write a C++ function to convert a decimal number to binary."},
            {"problem": "Write a C++ program to calculate the sum of an array."},
            {"problem": "Write a C++ program to find the second largest element in an array."},
            {"problem": "Write a C++ program to implement a simple calculator (add, subtract, multiply, divide)."},
            {"problem": "Write a C++ program to check if a character is a vowel or consonant."},
            {"problem": "Write a C++ program to count the number of words in a string."},
            {"problem": "Write a C++ program to find the length of a string without using built-in functions."},
            {"problem": "Write a C++ function to reverse the elements of an array."}
        ],
        'c#': [
            {"problem": "Write a C# method to check if a string is a palindrome."},
            {"problem": "Create a C# program to find the maximum value in an integer array."}
        ]
    }

    default_problems = [
        {"problem": f"Write a function in {selected_skill} to reverse a string."},
        {"problem": f"Implement a basic algorithm in {selected_skill} to check if a number is prime."}
    ]

    # test_problems = skill_problems.get(selected_skill.lower(), default_problems)
    all_problems = skill_problems.get(selected_skill.lower(), default_problems)
    test_problems = random.sample(all_problems, min(len(all_problems), 10))
    total_possible = len(test_problems) * 10
    if request.method == "GET":
        all_problems = skill_problems.get(selected_skill.lower(), default_problems)
        test_problems = random.sample(all_problems, min(len(all_problems), 10))
        session['test_problems'] = test_problems
    else:
        test_problems = session.get('test_problems', default_problems)

    if 'last_score' in session:
        results = session['last_score']['results']
        scores = session['last_score']['scores']
        feedback = session['last_score']['feedback']
        total_score = session['last_score']['total_score']
        session.pop('last_score', None)
        return render_template("coding_test.html",
                               test_problems=test_problems,
                               results=results,
                               scores=scores,
                               feedback=feedback,
                               total_score=total_score,
                               total_possible=total_possible,
                               selected_skill=selected_skill)

    if request.method == "POST":
        results, scores, feedback = [], [], []
        total_score = 0

        for i in range(1, len(test_problems) + 1):
            code = request.form.get(f"code-{i}")
            lang = request.form.get(f"language-{i}", selected_skill.lower())

            lang_mapping = {
                'python': 'python', 'java': 'java', 'javascript': 'js', 'js': 'js',
                'c++': 'cpp', 'cpp': 'cpp', 'c#': 'csharp', 'csharp': 'csharp', 'sql': 'sql'
            }
            api_lang = lang_mapping.get(lang.lower(), lang.lower())

            if not code or not lang:
                results.append("No code submitted or language specified.")
                scores.append(0)
                feedback.append("No solution provided.")
                continue

            try:
                response = requests.post(PISTON_API_URL, json={
                    "language": api_lang,
                    "version": "*",
                    "files": [{"name": f"main.{api_lang}", "content": code}],
                    "stdin": "", "args": [],
                    "compile_timeout": 10000,
                    "run_timeout": 5000,
                    "compile_memory_limit": -1,
                    "run_memory_limit": -1
                })

                if response.ok:
                    result_data = response.json()
                    output = result_data["run"].get("output", "No output generated.")
                    stderr = result_data["run"].get("stderr", "")
                    exit_code = result_data["run"].get("code", 0)

                    if stderr or exit_code != 0:
                        results.append(f"Execution Error:\n{stderr}\nOutput:\n{output}")
                        current_score = 2
                        current_feedback = "Code has errors. Fix syntax issues to earn more points."
                    else:
                        results.append(output)
                        current_score, current_feedback = score_solution(code, output, test_problems[i - 1], api_lang)

                    scores.append(current_score)
                    feedback.append(current_feedback)
                    total_score += current_score

                else:
                    results.append(f"API Error: {response.status_code}, {response.text}")
                    scores.append(0)
                    feedback.append("System error occurred.")

            except Exception as e:
                results.append(f"Exception: {str(e)}")
                scores.append(0)
                feedback.append("System error occurred.")

        try:
            db.session.add(TestResult(
                student_id=session['user_id'],
                skill=selected_skill,
                score=total_score,
                test_type='hard'))
            db.session.commit()
        except Exception as e:
            print("Database commit failed:", str(e))

        session['last_score'] = {
            'results': results,
            'scores': scores,
            'feedback': feedback,
            'total_score': total_score
        }
        return redirect(url_for('coding_test', skill=selected_skill))

    return render_template("coding_test.html",
                           test_problems=test_problems,
                           results=[],
                           scores=[],
                           feedback=[],
                           total_score=0,
                           total_possible=total_possible,
                           selected_skill=selected_skill)

def score_solution(code, result, problem, language):
    """
    Simple scoring logic for code solutions
    Returns: (score, feedback)
    """
    # Initialize score
    score = 0

    # Check if code is empty or unchanged from template
    if not code or "Your code here" in code or "# Write your" in code:
        return 0, "No solution provided."

    # Add points for code presence
    score += 2

    # Check for syntax errors in result
    if "Error" in result or "Exception" in result:
        return score, "Code has errors. Fix syntax issues to earn more points."

    # Add points for code that runs
    score += 3

    # Simple pattern checks based on expected output or patterns
    # This is a simplified implementation - adapt for your specific problems
    expected_patterns = get_expected_patterns(problem)

    correct_output = any(re.search(pattern, result) for pattern in expected_patterns)
    if correct_output:
        score += 3
        feedback = "Solution passes basic tests."
    else:
        feedback = "Solution runs but doesn't produce expected output."

    # Check code quality (very basic)
    quality_score = check_code_quality(code, language)
    score += quality_score

    if score >= 8:
        feedback += " Good code quality!"
    elif quality_score > 0:
        feedback += " Some good practices found."

    # Cap score at 10
    score = min(score, 10)

    return score, feedback


def get_expected_patterns(problem):
    """
    Returns regex patterns for expected output based on problem
    This is simplified - in a real application, you'd have actual test cases
    """
    problem_text = problem["problem"].lower()

    # Extract expected patterns from problem description
    if "prime" in problem_text:
        return [r"[Tt]rue.*[7|11|13]", r"[Ff]alse.*[4|6|8|9]", r"prime"]
    elif "longest word" in problem_text:
        return [r"longest", r"character", r"length"]
    elif "reverse" in problem_text and "string" in problem_text:
        return [r"olleh", r"dlrow", r"esrever", r"gnirts"]
    elif "palindrome" in problem_text:
        return [r"[Tt]rue.*radar", r"[Tt]rue.*level", r"[Ff]alse.*hello"]
    elif "factorial" in problem_text:
        return [r"120", r"720", r"24"]
    elif "gcd" in problem_text:
        return [r"[1-9][0-9]*"]
    elif "salaries" in problem_text:
        return [r"SELECT", r"ORDER BY", r"DESC", r"LIMIT"]
    elif "maximum" in problem_text:
        return [r"[0-9]+", r"max"]
    else:
        # Default pattern - just check if there's any output
        return [r"\w+"]

def check_code_quality(code, language):

    quality_score = 0

    # Check for comments
    if "#" in code or "//" in code or "/*" in code:
        quality_score += 1

    # Different languages have different function definition syntax
    if language == "python" and "def " in code:
        quality_score += 1
    elif language in ["js", "javascript"] and ("function " in code or "=> {" in code):
        quality_score += 1
    elif language in ["java", "csharp"] and ("class " in code or "void " in code or "public " in code):
        quality_score += 1
    elif language in ["cpp", "c++"] and ("void " in code or "int " in code or "class " in code):
        quality_score += 1
    elif language == "sql" and "SELECT " in code.upper():
        quality_score += 1

    return quality_score

@app.route('/select-skill', methods=['GET'])
def select_skill():
    if 'user_id' not in session:
        return redirect('/login')

    # Get the current user
    user = User.query.get(session['user_id'])

    if not user:
        return redirect('/login')

    # Get user skills - split the skills string by comma and strip whitespace
    if user.skills:
        user_skills = [skill.strip() for skill in user.skills.split(',')]
    else:
        user_skills = []

    return render_template('select_skill.html', skills=user_skills)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.phone = request.form['phone']
        user.education = request.form['education']
        user.skills = request.form['skills']

        # Handle CV upload
        cv_file = request.files.get('cv_file')
        if cv_file:
            filename = secure_filename(cv_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            cv_file.save(filepath)
            user.cv_path = os.path.relpath(filepath, 'static').replace('\\', '/')

        # Update the profile information in the database
        db.session.commit()
        return redirect('/profile')

    return render_template('edit_profile.html', user=user)

@app.route('/profile')
def profilestud():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    test_results = TestResult.query.filter_by(student_id=user.id).order_by(TestResult.test_date.desc()).all()

    return render_template('profile_stud.html', user=user, test_results=test_results)

@app.route('/MyApplications')
def my_applications():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    # Fetch all applications submitted by the student
    applications = Application.query.filter_by(student_id=user.id).all()

    return render_template('my_applications.html', user=user, applications=applications)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
@app.after_request
def add_header(response):

    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

if __name__ == '__main__':
    app.run(debug=True)


